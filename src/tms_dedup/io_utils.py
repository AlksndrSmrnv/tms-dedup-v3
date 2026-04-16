"""JSON I/O helpers with deterministic output and a stage-cache mechanism."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson


def read_json(path: Path) -> Any:
    with path.open("rb") as f:
        return orjson.loads(f.read())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = orjson.dumps(data, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    path.write_bytes(payload)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def make_meta(stage: str, input_hash: str, lexicon_hash: str = "") -> dict[str, str]:
    return {
        "stage": stage,
        "input_hash": input_hash,
        "lexicon_hash": lexicon_hash,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def cache_hit(output_path: Path, input_hash: str, lexicon_hash: str = "") -> bool:
    """Return True when the existing output is valid for the given inputs."""
    if not output_path.exists():
        return False
    try:
        data = read_json(output_path)
    except Exception:
        return False
    meta = data.get("_meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        return False
    if meta.get("input_hash") != input_hash:
        return False
    if lexicon_hash and meta.get("lexicon_hash") != lexicon_hash:
        return False
    return True
