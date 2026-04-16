"""Stage 1: parse input TSV into canonical JSON (tests + unique sections)."""

from __future__ import annotations

import csv
from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, sha256_file, write_json


def run(
    input_path: Path | None = None,
    tests_out: Path | None = None,
    sections_out: Path | None = None,
    section_sep: str = config.SECTION_SEP,
    force: bool = False,
) -> None:
    input_path = input_path or config.INPUT_TSV
    tests_out = tests_out or config.TESTS_JSON
    sections_out = sections_out or config.SECTIONS_JSON
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. "
            f"Expected TSV with columns id, section, name."
        )

    input_hash = sha256_file(input_path)
    if not force and cache_hit(tests_out, input_hash) and cache_hit(sections_out, input_hash):
        return

    tests: list[dict] = []
    section_paths: dict[str, dict] = {}
    seen_ids: set[str] = set()

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"id", "section", "name"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Input TSV missing required columns: {sorted(missing)}")
        for row in reader:
            tid = (row["id"] or "").strip()
            section = (row["section"] or "").strip()
            name = (row["name"] or "").strip()
            if not tid or not name:
                continue
            if tid in seen_ids:
                raise ValueError(f"Duplicate test id in input: {tid!r}")
            seen_ids.add(tid)
            segments = [s.strip() for s in section.split(section_sep) if s.strip()]
            tests.append(
                {
                    "id": tid,
                    "section": section,
                    "section_segments": segments,
                    "name": name,
                }
            )
            if section not in section_paths:
                section_paths[section] = {
                    "section": section,
                    "segments": segments,
                    "count": 0,
                    "sample_names": [],
                }
            entry = section_paths[section]
            entry["count"] += 1
            if len(entry["sample_names"]) < 5:
                entry["sample_names"].append(name)

    tests.sort(key=lambda t: t["id"])
    sections = sorted(section_paths.values(), key=lambda s: s["section"])

    write_json(
        tests_out,
        {"_meta": make_meta("01_parse", input_hash), "tests": tests, "count": len(tests)},
    )
    write_json(
        sections_out,
        {
            "_meta": make_meta("01_parse_sections", input_hash),
            "sections": sections,
            "count": len(sections),
        },
    )
