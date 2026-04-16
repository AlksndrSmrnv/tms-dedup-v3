"""Paths, thresholds, and constants for the pipeline."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np

# --- Paths -----------------------------------------------------------------

ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT / "data"
ARTIFACTS_DIR: Path = ROOT / "artifacts"
BATCHES_DIR: Path = ARTIFACTS_DIR / "batches"
VERDICTS_DIR: Path = ARTIFACTS_DIR / "verdicts"
REPORT_DIR: Path = ROOT / "report"
PROMPTS_DIR: Path = ROOT / "prompts"

# --- Default input/output filenames ---------------------------------------

INPUT_TSV: Path = DATA_DIR / "input.tsv"
SECTION_SEP: str = " / "

TESTS_JSON: Path = ARTIFACTS_DIR / "01_tests.json"
SECTIONS_JSON: Path = ARTIFACTS_DIR / "01_sections.json"
SECTIONS_CLASSIFIED_JSON: Path = ARTIFACTS_DIR / "02a_sections_classified.json"
SECTIONS_AMBIGUOUS_JSON: Path = ARTIFACTS_DIR / "02a_sections_ambiguous.json"
SECTIONS_LLM_JSON: Path = ARTIFACTS_DIR / "02b_llm_classified.json"
SECTIONS_FINAL_JSON: Path = ARTIFACTS_DIR / "02b_sections_final.json"
TEST_FEATURES_JSON: Path = ARTIFACTS_DIR / "03_test_features.json"
CANDIDATES_JSON: Path = ARTIFACTS_DIR / "04_candidates.json"
VERDICTS_JSON: Path = ARTIFACTS_DIR / "05_verdicts.json"
CLUSTERS_JSON: Path = ARTIFACTS_DIR / "06_clusters.json"
REPORT_MD: Path = REPORT_DIR / "duplicates_report.md"
LEMMA_CACHE_JSON: Path = ARTIFACTS_DIR / "lemma_cache.json"
BATCHES_PROGRESS_JSON: Path = BATCHES_DIR / "_progress.json"

# --- Similarity thresholds ------------------------------------------------

LOWER_THRESHOLD: float = 0.55  # minimum combined score to consider a candidate
UPPER_THRESHOLD: float = 0.85  # above this -> high_confidence tier
TOP_K_PER_TEST: int = 5  # cap on candidates per test

# Weights tuned on a 25-test fixture of Russian banking test titles.
# token_set_ratio dominates for short strings, so it gets a meaningful slice.
W_TFIDF_CHAR: float = 0.40
W_TFIDF_WORD: float = 0.25
W_FUZZ: float = 0.35

# --- Section-classifier heuristics ----------------------------------------

CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.7

# --- Stage 5 batching ------------------------------------------------------

PAIRS_PER_BATCH: int = 25

# --- Reproducibility -------------------------------------------------------

SEED: int = 42


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)


def ensure_dirs() -> None:
    for p in (DATA_DIR, ARTIFACTS_DIR, BATCHES_DIR, VERDICTS_DIR, REPORT_DIR):
        p.mkdir(parents=True, exist_ok=True)
