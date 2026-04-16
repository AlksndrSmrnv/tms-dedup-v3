# QWEN.md — tms-dedup-v3 skill

You are operating inside the `tms-dedup-v3` project. The goal is to detect
semantic duplicate tests in a TMS Test IT test model using only the section
path and the test name (no steps). Classical NLP (TF-IDF, rapidfuzz,
pymorphy3) does the heavy lifting; you act as the LLM arbiter at two
well-defined points of the pipeline.

Python runs via `uv` in the project `.venv`. Always invoke Python code
through `uv run ...` so the lockfile governs the environment.

## Input

- `data/input.tsv` — UTF-8 TSV with header `id\tsection\tname`. The user
  puts their TMS export here. Section segments are joined with ` / `.

## Pipeline stages and commands

Run these in order. Every stage is idempotent — a cached run is skipped
unless `--force` is passed.

1. `uv sync` — install deps (once).
2. `uv run tms-dedup parse` — TSV → `artifacts/01_tests.json`,
   `artifacts/01_sections.json`.
3. `uv run tms-dedup classify-auto` — heuristic section classifier.
   Produces `artifacts/02a_sections_classified.json` and
   `artifacts/02a_sections_ambiguous.json`.
4. **LLM step (Stage 2b).** If the ambiguous file is non-empty, read it,
   apply `prompts/classify_section.md`, and write your classifications to
   `artifacts/02b_llm_classified.json` in the schema documented in that
   prompt. Skip this step if the ambiguous file is empty.
5. `uv run tms-dedup classify-merge` — merge heuristic + LLM into
   `artifacts/02b_sections_final.json`.
6. `uv run tms-dedup features` — normalize names + compute
   `transfer_type_set` per test. Writes `artifacts/03_test_features.json`.
7. `uv run tms-dedup candidates` — TF-IDF + rapidfuzz over blocked pairs.
   Writes `artifacts/04_candidates.json`.
8. `uv run tms-dedup batch-pairs` — splits candidate pairs into batches of
   25 under `artifacts/batches/batch_NNNN.json` and records a progress
   manifest at `artifacts/batches/_progress.json`.
9. **LLM step (Stage 5).** For every `batch_NNNN.json` that does not yet
   have a `artifacts/verdicts/batch_NNNN.jsonl` counterpart, read the batch,
   apply `prompts/arbitrate_pair.md`, and write one JSONL line per pair to
   the corresponding verdicts file. Preserve the `pair_id`s exactly.
10. `uv run tms-dedup merge-verdicts` — concatenate verdicts into
    `artifacts/05_verdicts.json`.
11. `uv run tms-dedup cluster` — connected components over `duplicate`
    edges. Writes `artifacts/06_clusters.json`.
12. `uv run tms-dedup report` — renders `report/duplicates_report.md`.

Or in one go: `uv run tms-dedup run-all`. The orchestrator will halt and
print instructions when it reaches Stage 2b or Stage 5. Resume by rerunning
`run-all`.

## Operating rules

- Treat `artifacts/` as disposable; it can be regenerated from scratch.
- Never modify files under `data/`, `src/`, `prompts/`, `.qwen/` unless
  asked by the user.
- Keep LLM outputs strictly in the schema defined by the prompt files.
- If a batch's verdict JSONL already exists, do not overwrite it.
- If the input file is missing, tell the user and stop.
