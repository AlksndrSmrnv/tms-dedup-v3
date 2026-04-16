import json
from pathlib import Path

from tms_dedup import cluster
from tms_dedup.io_utils import write_json


def _write_features(path: Path, ids: list[str], tt_set: list[str]):
    write_json(
        path,
        {
            "_meta": {"stage": "test", "input_hash": "x", "lexicon_hash": ""},
            "count": len(ids),
            "tests": [
                {
                    "id": i,
                    "name": i,
                    "section": "x",
                    "section_category": "feature",
                    "name_lemmas": [],
                    "name_lemma_text": "",
                    "stripped_name": "",
                    "transfer_type_set": tt_set,
                    "feature_block_key": "x",
                }
                for i in ids
            ],
        },
    )


def _write_verdicts(path: Path, edges: list[tuple[str, str, str]]):
    verdicts = [
        {
            "pair_id": f"p_{a}__{b}",
            "verdict": v,
            "reason": "",
            "a_id": a,
            "b_id": b,
            "score": 0.9,
            "tier": "high_confidence",
        }
        for a, b, v in edges
    ]
    write_json(
        path,
        {
            "_meta": {"stage": "test", "input_hash": "x", "lexicon_hash": ""},
            "count": len(verdicts),
            "verdicts": verdicts,
            "missing_batches": [],
        },
    )


def test_transitive_duplicate_cluster(tmp_path: Path):
    features_path = tmp_path / "features.json"
    verdicts_path = tmp_path / "verdicts.json"
    out = tmp_path / "clusters.json"

    _write_features(features_path, ["A", "B", "C", "D"], ["phone"])
    _write_verdicts(
        verdicts_path,
        [("A", "B", "duplicate"), ("B", "C", "duplicate"), ("C", "D", "different_functionality")],
    )

    cluster.run(verdicts_in=verdicts_path, features_in=features_path, out=out)

    data = json.loads(out.read_text())
    groups = data["groups"]
    # ABC are connected via duplicate edges; D should NOT join (different_functionality).
    assert any(set(g["member_ids"]) == {"A", "B", "C"} for g in groups)
    assert not any("D" in g["member_ids"] for g in groups)


def test_different_transfer_type_does_not_cluster(tmp_path: Path):
    features_path = tmp_path / "features.json"
    verdicts_path = tmp_path / "verdicts.json"
    out = tmp_path / "clusters.json"

    _write_features(features_path, ["A", "B"], ["phone"])
    _write_verdicts(verdicts_path, [("A", "B", "different_transfer_type")])

    cluster.run(verdicts_in=verdicts_path, features_in=features_path, out=out)
    data = json.loads(out.read_text())
    assert data["group_count"] == 0
