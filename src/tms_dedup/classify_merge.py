"""Merge heuristic classification with the qwen-produced classification.

If the LLM output file is absent or empty, ambiguous sections are passed
through with their heuristic guess (or `other` fallback) so the pipeline can
still finish in testing/offline scenarios.
"""

from __future__ import annotations

from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, sha256_file, write_json, read_json
from tms_dedup.lexicon import lexicon_hash

VALID_CATEGORIES = {"transfer-type", "feature", "mixed", "other"}


def _load_llm(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = read_json(path)
    entries = data.get("sections") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict] = {}
    for e in entries:
        sp = e.get("section_path")
        cat = e.get("category")
        if not sp or cat not in VALID_CATEGORIES:
            continue
        tts = e.get("transfer_types") or []
        if not isinstance(tts, list):
            tts = []
        result[sp] = {
            "category": cat,
            "transfer_types": sorted({str(t).strip().lower() for t in tts if t}),
            "reason": e.get("reason", ""),
            "source": "llm",
        }
    return result


def run(
    classified_in: Path | None = None,
    ambiguous_in: Path | None = None,
    llm_in: Path | None = None,
    final_out: Path | None = None,
    force: bool = False,
) -> None:
    classified_in = classified_in or config.SECTIONS_CLASSIFIED_JSON
    ambiguous_in = ambiguous_in or config.SECTIONS_AMBIGUOUS_JSON
    llm_in = llm_in or config.SECTIONS_LLM_JSON
    final_out = final_out or config.SECTIONS_FINAL_JSON
    input_hash = sha256_file(classified_in) + sha256_file(ambiguous_in)
    if llm_in.exists():
        input_hash += sha256_file(llm_in)
    lex_hash = lexicon_hash()
    if not force and cache_hit(final_out, input_hash, lex_hash):
        return

    classified = read_json(classified_in)["sections"]
    ambiguous = read_json(ambiguous_in)["sections"]
    llm_map = _load_llm(llm_in)

    final: dict[str, dict] = {}

    for s in classified:
        final[s["section_path"]] = {
            "section_path": s["section_path"],
            "category": s["category"],
            "transfer_types": s["transfer_types"],
            "source": "heuristic",
        }

    for s in ambiguous:
        path = s["section_path"]
        if path in llm_map:
            merged = llm_map[path].copy()
            merged["section_path"] = path
            final[path] = merged
        else:
            # Fallback: use heuristic category if not "unknown"; otherwise mark "other".
            fallback_cat = s["category"] if s["category"] in VALID_CATEGORIES else "other"
            final[path] = {
                "section_path": path,
                "category": fallback_cat,
                "transfer_types": s["transfer_types"],
                "source": "fallback",
            }

    sections = sorted(final.values(), key=lambda r: r["section_path"])
    write_json(
        final_out,
        {
            "_meta": make_meta("02b_classify_merge", input_hash, lex_hash),
            "sections": sections,
            "count": len(sections),
        },
    )
