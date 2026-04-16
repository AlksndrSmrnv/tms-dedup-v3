"""Stage 4: find candidate duplicate pairs via blocking + similarity."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, sha256_file, write_json, read_json
from tms_dedup.lexicon import lexicon_hash
from tms_dedup.stopwords import stopwords_hash


def _block_key(test: dict) -> tuple[str, ...]:
    """Primary block key — frozenset of transfer types as a stable tuple.

    Feature-only tests (empty set) get a secondary segment-based key so we
    don't compare every feature test with every other.
    """
    ttset = tuple(sorted(test.get("transfer_type_set") or []))
    if not ttset:
        return ("__feature__", test.get("feature_block_key") or "")
    return ttset


def _combined_score(char_sim: float, word_sim: float, fuzz_sim: float) -> float:
    return (
        config.W_TFIDF_CHAR * char_sim
        + config.W_TFIDF_WORD * word_sim
        + config.W_FUZZ * fuzz_sim
    )


def _top_pairs_within_block(
    block_tests: list[dict],
    lower: float,
    upper: float,
    top_k: int,
) -> list[dict]:
    if len(block_tests) < 2:
        return []

    # Use the full lemmatized name (not the stripped one) as the similarity
    # input. Stripping transfer-type components removes genuinely shared
    # structural words ("банк", "карта") and hurts recall; TF-IDF's IDF
    # weighting already damps common terms, and blocking has already
    # separated tests by transfer-type set, so over-counting is not a risk.
    texts: list[str] = []
    for t in block_tests:
        text = (t.get("name_lemma_text") or "").strip()
        if not text:
            text = t.get("name") or ""
        texts.append(text)

    # char_wb TF-IDF
    char_vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
    )
    try:
        char_m = char_vec.fit_transform(texts)
        char_sim = cosine_similarity(char_m)
    except ValueError:
        char_sim = np.zeros((len(texts), len(texts)))

    # word TF-IDF
    word_vec = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        token_pattern=r"(?u)\b\w+\b",
    )
    try:
        word_m = word_vec.fit_transform(texts)
        word_sim = cosine_similarity(word_m)
    except ValueError:
        word_sim = np.zeros((len(texts), len(texts)))

    n = len(block_tests)
    rows_top: dict[int, list[tuple[int, float]]] = defaultdict(list)

    for i in range(n):
        for j in range(i + 1, n):
            c = float(char_sim[i, j])
            w = float(word_sim[i, j])
            # rapidfuzz is computed lazily only for high-ish candidates, to save CPU.
            if max(c, w) < lower * 0.6:
                continue
            f = float(fuzz.token_set_ratio(texts[i], texts[j])) / 100.0
            score = _combined_score(c, w, f)
            if score < lower:
                continue
            rows_top[i].append((j, score))
            rows_top[j].append((i, score))

    keep_pairs: set[tuple[int, int]] = set()
    for i, cands in rows_top.items():
        cands.sort(key=lambda p: -p[1])
        for j, _ in cands[:top_k]:
            keep_pairs.add((min(i, j), max(i, j)))

    results: list[dict] = []
    for i, j in sorted(keep_pairs):
        c = float(char_sim[i, j])
        w = float(word_sim[i, j])
        f = float(fuzz.token_set_ratio(texts[i], texts[j])) / 100.0
        score = _combined_score(c, w, f)
        tier = "high_confidence" if score >= upper else "candidate"
        a = block_tests[i]
        b = block_tests[j]
        results.append(
            {
                "pair_id": f"p_{a['id']}__{b['id']}",
                "a_id": a["id"],
                "b_id": b["id"],
                "score": round(score, 4),
                "tfidf_char": round(c, 4),
                "tfidf_word": round(w, 4),
                "fuzz": round(f, 4),
                "tier": tier,
                "block_key": list(_block_key(a)),
            }
        )
    return results


def run(
    features_in: Path | None = None,
    out: Path | None = None,
    lower: float = config.LOWER_THRESHOLD,
    upper: float = config.UPPER_THRESHOLD,
    top_k: int = config.TOP_K_PER_TEST,
    force: bool = False,
) -> None:
    features_in = features_in or config.TEST_FEATURES_JSON
    out = out or config.CANDIDATES_JSON
    input_hash = sha256_file(features_in)
    lex_hash = lexicon_hash() + "-" + stopwords_hash()
    if not force and cache_hit(out, input_hash, lex_hash):
        return

    tests = read_json(features_in)["tests"]

    blocks: dict[tuple, list[dict]] = defaultdict(list)
    for t in tests:
        blocks[_block_key(t)].append(t)

    all_pairs: list[dict] = []
    for key, members in blocks.items():
        pairs = _top_pairs_within_block(members, lower=lower, upper=upper, top_k=top_k)
        all_pairs.extend(pairs)

    all_pairs.sort(key=lambda p: (-p["score"], p["pair_id"]))

    write_json(
        out,
        {
            "_meta": make_meta("04_candidates", input_hash, lex_hash),
            "pairs": all_pairs,
            "count": len(all_pairs),
            "config": {
                "lower_threshold": lower,
                "upper_threshold": upper,
                "top_k": top_k,
                "w_tfidf_char": config.W_TFIDF_CHAR,
                "w_tfidf_word": config.W_TFIDF_WORD,
                "w_fuzz": config.W_FUZZ,
            },
        },
    )
