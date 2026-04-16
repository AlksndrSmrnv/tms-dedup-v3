"""Stage 2a: heuristic section classifier.

Each unique section is classified based on keyword matching against the
lexicon. Confidently classified sections go to 02a_sections_classified.json;
everything else — including mixed (transfer+feature) and weak matches —
goes to 02a_sections_ambiguous.json for the qwen LLM to arbitrate.
"""

from __future__ import annotations

from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, sha256_file, write_json, read_json
from tms_dedup.lexicon import (
    count_feature_markers,
    extract_transfer_types,
    lexicon_hash,
    yo_to_e,
)
from tms_dedup.normalize import Lemmatizer, normalized_text_for_matching
from tms_dedup.stopwords import stopwords_hash


def classify_one(section_path: str, lemmatizer: Lemmatizer) -> dict:
    norm = normalized_text_for_matching(section_path, lemmatizer)
    norm = yo_to_e(norm)
    transfer_types = sorted(extract_transfer_types(norm))
    feature_score = count_feature_markers(norm)

    if transfer_types and feature_score == 0:
        category = "transfer-type"
        confidence = 0.9
    elif feature_score >= 1 and not transfer_types:
        category = "feature"
        confidence = 0.9
    elif transfer_types and feature_score >= 1:
        category = "mixed"
        confidence = 0.55
    else:
        category = "unknown"
        confidence = 0.0

    return {
        "section_path": section_path,
        "category": category,
        "transfer_types": transfer_types,
        "feature_score": feature_score,
        "confidence": confidence,
    }


def run(
    sections_in: Path | None = None,
    classified_out: Path | None = None,
    ambiguous_out: Path | None = None,
    confidence_threshold: float = config.CLASSIFIER_CONFIDENCE_THRESHOLD,
    force: bool = False,
) -> None:
    sections_in = sections_in or config.SECTIONS_JSON
    classified_out = classified_out or config.SECTIONS_CLASSIFIED_JSON
    ambiguous_out = ambiguous_out or config.SECTIONS_AMBIGUOUS_JSON
    input_hash = sha256_file(sections_in)
    lex_hash = lexicon_hash() + "-" + stopwords_hash()
    if (
        not force
        and cache_hit(classified_out, input_hash, lex_hash)
        and cache_hit(ambiguous_out, input_hash, lex_hash)
    ):
        return

    sections_data = read_json(sections_in)
    lemmatizer = Lemmatizer(cache_path=config.LEMMA_CACHE_JSON)

    classified: list[dict] = []
    ambiguous: list[dict] = []

    for s in sections_data["sections"]:
        result = classify_one(s["section"], lemmatizer)
        # Attach a few sample names so the LLM has context when arbitrating.
        result["sample_names"] = s.get("sample_names", [])
        result["segments"] = s.get("segments", [])
        result["count"] = s.get("count", 0)
        if result["confidence"] >= confidence_threshold and result["category"] != "unknown":
            classified.append(result)
        else:
            ambiguous.append(result)

    lemmatizer.save()

    classified.sort(key=lambda r: r["section_path"])
    ambiguous.sort(key=lambda r: r["section_path"])

    write_json(
        classified_out,
        {
            "_meta": make_meta("02a_classify_heuristic", input_hash, lex_hash),
            "sections": classified,
            "count": len(classified),
        },
    )
    write_json(
        ambiguous_out,
        {
            "_meta": make_meta("02a_classify_heuristic_ambiguous", input_hash, lex_hash),
            "sections": ambiguous,
            "count": len(ambiguous),
        },
    )
