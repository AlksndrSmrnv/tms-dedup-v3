"""Split candidate pairs into batches for qwen LLM arbitration and track progress."""

from __future__ import annotations

from pathlib import Path

from tms_dedup import config
from tms_dedup.io_utils import read_json, write_json


def run(
    candidates_in: Path | None = None,
    features_in: Path | None = None,
    batches_dir: Path | None = None,
    verdicts_dir: Path | None = None,
    progress_out: Path | None = None,
    batch_size: int = config.PAIRS_PER_BATCH,
) -> None:
    candidates_in = candidates_in or config.CANDIDATES_JSON
    features_in = features_in or config.TEST_FEATURES_JSON
    batches_dir = batches_dir or config.BATCHES_DIR
    verdicts_dir = verdicts_dir or config.VERDICTS_DIR
    progress_out = progress_out or config.BATCHES_PROGRESS_JSON
    batches_dir.mkdir(parents=True, exist_ok=True)
    verdicts_dir.mkdir(parents=True, exist_ok=True)

    tests_by_id = {t["id"]: t for t in read_json(features_in)["tests"]}
    pairs = read_json(candidates_in)["pairs"]

    # Wipe existing batch files so we never mix stale batches with new ones.
    for p in batches_dir.glob("batch_*.json"):
        p.unlink()

    batches: list[dict] = []
    for idx, start in enumerate(range(0, len(pairs), batch_size), start=1):
        chunk = pairs[start : start + batch_size]
        out_pairs = []
        for p in chunk:
            a = tests_by_id[p["a_id"]]
            b = tests_by_id[p["b_id"]]
            out_pairs.append(
                {
                    "pair_id": p["pair_id"],
                    "score": p["score"],
                    "tier": p["tier"],
                    "a": {
                        "id": a["id"],
                        "section": a["section"],
                        "name": a["name"],
                        "transfer_types": a["transfer_type_set"],
                    },
                    "b": {
                        "id": b["id"],
                        "section": b["section"],
                        "name": b["name"],
                        "transfer_types": b["transfer_type_set"],
                    },
                }
            )
        batch_file = batches_dir / f"batch_{idx:04d}.json"
        write_json(batch_file, {"batch_id": idx, "pairs": out_pairs})
        batches.append(
            {
                "batch_id": idx,
                "file": str(batch_file.relative_to(config.ROOT)),
                "verdict_file": str(
                    (verdicts_dir / f"batch_{idx:04d}.jsonl").relative_to(config.ROOT)
                ),
                "count": len(out_pairs),
            }
        )

    progress = {
        "total_batches": len(batches),
        "total_pairs": len(pairs),
        "batches": batches,
    }
    write_json(progress_out, progress)
