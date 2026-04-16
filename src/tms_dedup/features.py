"""Stage 3: per-test feature extraction.

For each test compute:
- lemmatized, stopword-stripped normalized name (for TF-IDF);
- a compact "stripped_name" with transfer-type components removed (avoids
  double-counting the channel signal that blocking already uses);
- the combined transfer_type_set (section's types ∪ types found in the name).
"""

from __future__ import annotations

from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, sha256_file, write_json, read_json
from tms_dedup.lexicon import extract_transfer_types, lexicon_hash, yo_to_e
from tms_dedup.normalize import (
    Lemmatizer,
    normalize_to_lemmas,
    strip_transfer_type_tokens,
)
from tms_dedup.stopwords import stopwords_hash


def run(
    tests_in: Path | None = None,
    sections_final_in: Path | None = None,
    out: Path | None = None,
    force: bool = False,
) -> None:
    tests_in = tests_in or config.TESTS_JSON
    sections_final_in = sections_final_in or config.SECTIONS_FINAL_JSON
    out = out or config.TEST_FEATURES_JSON
    input_hash = sha256_file(tests_in) + sha256_file(sections_final_in)
    lex_hash = lexicon_hash() + "-" + stopwords_hash()
    if not force and cache_hit(out, input_hash, lex_hash):
        return

    tests = read_json(tests_in)["tests"]
    section_rows = read_json(sections_final_in)["sections"]
    sections_by_path: dict[str, dict] = {s["section_path"]: s for s in section_rows}

    lemmatizer = Lemmatizer(cache_path=config.LEMMA_CACHE_JSON)
    features: list[dict] = []

    for t in tests:
        section = t["section"]
        sect = sections_by_path.get(section, {})
        section_category = sect.get("category", "other")
        section_types = set(sect.get("transfer_types", []) or [])

        name_lemmas = normalize_to_lemmas(t["name"], lemmatizer)
        name_lemma_str = yo_to_e(" ".join(name_lemmas))

        types_from_name = extract_transfer_types(name_lemma_str)
        transfer_type_set = sorted(section_types | types_from_name)

        stripped = strip_transfer_type_tokens(name_lemmas)
        stripped_name = " ".join(stripped)

        # Feature-only tests also get a secondary block key (last meaningful
        # section segment) so we don't compare every feature test with every
        # other feature test globally.
        segments = t.get("section_segments", []) or []
        feature_block_key = segments[-1].lower() if segments else ""

        features.append(
            {
                "id": t["id"],
                "name": t["name"],
                "section": section,
                "section_category": section_category,
                "name_lemmas": name_lemmas,
                "name_lemma_text": name_lemma_str,
                "stripped_name": stripped_name,
                "transfer_type_set": transfer_type_set,
                "feature_block_key": feature_block_key,
            }
        )

    lemmatizer.save()

    features.sort(key=lambda f: f["id"])
    write_json(
        out,
        {
            "_meta": make_meta("03_features", input_hash, lex_hash),
            "tests": features,
            "count": len(features),
        },
    )
