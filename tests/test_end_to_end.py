"""End-to-end pipeline test.

Runs every stage on `tests/fixtures/sample_tests.tsv`. Stages 2b and 5 (which
normally require the qwen LLM) are stubbed using a rule-based fake arbiter:
- 2b: any ambiguous section is treated as `feature` with no transfer types
  (matches the fixture, which has no genuinely ambiguous sections).
- 5:  verdicts are computed from the blocking information — pairs within the
  same block get `duplicate` when the combined score is >= 0.65, else
  `different_functionality`. Cross-block pairs never reach this stage.

Asserts that the expected duplicate groups from the fixture are found and
that different-transfer-type tests never end up in the same cluster.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tms_dedup import (
    batch_pairs,
    candidates,
    classify_heuristic,
    classify_merge,
    cluster,
    config,
    features,
    merge_verdicts,
    parse,
    report,
)
from tms_dedup.io_utils import read_json, write_json


FIXTURE = Path(__file__).parent / "fixtures" / "sample_tests.tsv"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Redirect all config paths into tmp_path so the test is hermetic."""
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(config, "BATCHES_DIR", tmp_path / "artifacts" / "batches")
    monkeypatch.setattr(config, "VERDICTS_DIR", tmp_path / "artifacts" / "verdicts")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "report")
    monkeypatch.setattr(config, "INPUT_TSV", tmp_path / "data" / "input.tsv")
    monkeypatch.setattr(config, "TESTS_JSON", tmp_path / "artifacts" / "01_tests.json")
    monkeypatch.setattr(config, "SECTIONS_JSON", tmp_path / "artifacts" / "01_sections.json")
    monkeypatch.setattr(
        config, "SECTIONS_CLASSIFIED_JSON", tmp_path / "artifacts" / "02a_sections_classified.json"
    )
    monkeypatch.setattr(
        config, "SECTIONS_AMBIGUOUS_JSON", tmp_path / "artifacts" / "02a_sections_ambiguous.json"
    )
    monkeypatch.setattr(
        config, "SECTIONS_LLM_JSON", tmp_path / "artifacts" / "02b_llm_classified.json"
    )
    monkeypatch.setattr(
        config, "SECTIONS_FINAL_JSON", tmp_path / "artifacts" / "02b_sections_final.json"
    )
    monkeypatch.setattr(
        config, "TEST_FEATURES_JSON", tmp_path / "artifacts" / "03_test_features.json"
    )
    monkeypatch.setattr(config, "CANDIDATES_JSON", tmp_path / "artifacts" / "04_candidates.json")
    monkeypatch.setattr(config, "VERDICTS_JSON", tmp_path / "artifacts" / "05_verdicts.json")
    monkeypatch.setattr(config, "CLUSTERS_JSON", tmp_path / "artifacts" / "06_clusters.json")
    monkeypatch.setattr(config, "REPORT_MD", tmp_path / "report" / "duplicates_report.md")
    monkeypatch.setattr(config, "LEMMA_CACHE_JSON", tmp_path / "artifacts" / "lemma_cache.json")
    monkeypatch.setattr(
        config, "BATCHES_PROGRESS_JSON", tmp_path / "artifacts" / "batches" / "_progress.json"
    )
    config.ensure_dirs()
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "input.tsv").write_bytes(FIXTURE.read_bytes())
    return tmp_path


def _fake_llm_classify_sections():
    """Stub Stage 2b: classify every ambiguous entry as feature-no-tt."""
    data = read_json(config.SECTIONS_AMBIGUOUS_JSON)
    if data["count"] == 0:
        return
    sections = []
    for s in data["sections"]:
        # Preserve any transfer types the heuristic already matched.
        tts = s["transfer_types"]
        if s["category"] == "mixed":
            cat = "mixed"
        elif tts:
            cat = "transfer-type"
        else:
            cat = "feature"
        sections.append(
            {
                "section_path": s["section_path"],
                "category": cat,
                "transfer_types": tts,
                "confidence": 0.9,
                "reason": "stubbed fake arbiter for e2e test",
            }
        )
    write_json(config.SECTIONS_LLM_JSON, {"sections": sections})


_NEGATIVE_MARKERS = (
    "ошибк", "отмен", "негативн", "превышен", "несуществ", "лимит", "неверн",
)


def _is_negative(name: str) -> bool:
    low = name.lower()
    return any(m in low for m in _NEGATIVE_MARKERS)


def _fake_llm_arbitrate_pairs():
    """Stub Stage 5: mark high-score same-block happy-path pairs as duplicates.

    Negative/limits/errors are distinguished from happy-path tests, so tests
    that differ on negativity are correctly tagged `different_functionality`
    even when their classical similarity is high.
    """
    progress = read_json(config.BATCHES_PROGRESS_JSON)
    features = read_json(config.TEST_FEATURES_JSON)["tests"]
    names = {t["id"]: t["name"] for t in features}
    for b in progress["batches"]:
        batch = read_json(config.ROOT / b["file"])
        verdict_path = config.ROOT / b["verdict_file"]
        verdict_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for pair in batch["pairs"]:
            a_neg = _is_negative(names.get(pair["a"]["id"], ""))
            b_neg = _is_negative(names.get(pair["b"]["id"], ""))
            if a_neg != b_neg:
                v, reason = "different_functionality", "один happy-path, другой негатив"
            elif pair["score"] >= 0.55:
                v, reason = "duplicate", "идентичный смысл"
            else:
                v, reason = "different_functionality", "смысловое расхождение"
            lines.append(
                json.dumps({"pair_id": pair["pair_id"], "verdict": v, "reason": reason}, ensure_ascii=False)
            )
        verdict_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pipeline_end_to_end(isolated):
    parse.run(input_path=config.INPUT_TSV)
    classify_heuristic.run()
    _fake_llm_classify_sections()
    classify_merge.run()
    features.run()
    candidates.run()
    batch_pairs.run()
    _fake_llm_arbitrate_pairs()
    merge_verdicts.run()
    cluster.run()
    report.run()

    clusters = read_json(config.CLUSTERS_JSON)
    groups = {frozenset(g["member_ids"]) for g in clusters["groups"]}

    # Expected duplicate pairs from the fixture (happy-path SBP, happy-path card internal,
    # QR happy-path, limits, requisites, self, login).
    expected_pairs = [
        ("T-001", "T-002"),  # same SBP phone happy path
        ("T-004", "T-005"),  # card internal happy path
        ("T-009", "T-010"),  # daily limit main screen
        ("T-011", "T-012"),  # requisites transfer to juridical entity
        ("T-013", "T-014"),  # between own accounts
        ("T-015", "T-016"),  # login happy path
        ("T-019", "T-020"),  # QR payment happy path
    ]
    for a, b in expected_pairs:
        assert any({a, b}.issubset(g) for g in groups), (
            f"Expected pair ({a}, {b}) to be clustered, groups={groups}"
        )

    # Cross-transfer-type tests must never be grouped together.
    forbidden_pairs = [
        ("T-001", "T-004"),  # phone vs card
        ("T-001", "T-019"),  # phone vs qr
        ("T-004", "T-019"),  # card vs qr
        ("T-017", "T-018"),  # SBP limit vs card limit
    ]
    for a, b in forbidden_pairs:
        assert not any({a, b}.issubset(g) for g in groups), (
            f"Pair ({a}, {b}) must not be clustered (different transfer types); groups={groups}"
        )

    # Report exists and contains a summary.
    text = config.REPORT_MD.read_text(encoding="utf-8")
    assert "Duplicate tests report" in text
    assert "Summary" in text
