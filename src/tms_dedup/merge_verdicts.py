"""Collect per-batch JSONL verdicts written by the qwen agent into a single file.

If some batches lack verdicts, their pairs are emitted as `uncertain` so the
pipeline can still produce a report. Progress is reported on stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import make_meta, read_json, sha256_file, write_json

VALID_VERDICTS = {
    "duplicate",
    "different_transfer_type",
    "different_functionality",
    "uncertain",
}


def _parse_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("pair_id"):
            out.append(obj)
    return out


def run(
    candidates_in: Path | None = None,
    progress_in: Path | None = None,
    verdicts_dir: Path | None = None,
    out: Path | None = None,
) -> None:
    candidates_in = candidates_in or config.CANDIDATES_JSON
    progress_in = progress_in or config.BATCHES_PROGRESS_JSON
    verdicts_dir = verdicts_dir or config.VERDICTS_DIR
    out = out or config.VERDICTS_JSON
    candidates = read_json(candidates_in)["pairs"]
    pair_map = {p["pair_id"]: p for p in candidates}

    verdicts_by_pair: dict[str, dict] = {}
    missing_batches: list[int] = []

    if progress_in.exists():
        progress = read_json(progress_in)
        for b in progress.get("batches", []):
            verdict_path = config.ROOT / b["verdict_file"]
            if not verdict_path.exists():
                missing_batches.append(b["batch_id"])
                continue
            for v in _parse_jsonl(verdict_path):
                if v.get("verdict") not in VALID_VERDICTS:
                    continue
                verdicts_by_pair[v["pair_id"]] = {
                    "pair_id": v["pair_id"],
                    "verdict": v["verdict"],
                    "reason": v.get("reason", ""),
                }

    if missing_batches:
        print(
            f"[merge_verdicts] WARNING: {len(missing_batches)} batch(es) without verdicts "
            f"(first few: {missing_batches[:5]}). Missing pairs marked uncertain.",
            file=sys.stderr,
        )

    verdicts: list[dict] = []
    for p in candidates:
        pid = p["pair_id"]
        v = verdicts_by_pair.get(pid)
        if v is None:
            v = {"pair_id": pid, "verdict": "uncertain", "reason": "no verdict from LLM"}
        verdicts.append(
            {
                **v,
                "a_id": p["a_id"],
                "b_id": p["b_id"],
                "score": p["score"],
                "tier": p["tier"],
            }
        )

    verdicts.sort(key=lambda v: v["pair_id"])
    input_hash = sha256_file(candidates_in)
    write_json(
        out,
        {
            "_meta": make_meta("05_verdicts", input_hash),
            "verdicts": verdicts,
            "count": len(verdicts),
            "missing_batches": missing_batches,
        },
    )
