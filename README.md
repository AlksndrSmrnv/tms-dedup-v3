# tms-dedup-v3

Autonomous qwen CLI skill that finds semantic duplicate tests in a TMS Test IT test model (~2500 tests). Compares by section path and test name only (no steps). Classical NLP does the heavy lifting; the qwen-coder LLM (inside the interactive qwen CLI session) acts as (a) an arbiter for ambiguous folder classifications and (b) the final arbiter for candidate duplicate pairs.

## Quickstart

```bash
uv sync
# Put your tests export at data/input.tsv (columns: id<TAB>section<TAB>name, see below)
uv run tms-dedup run-all        # or launch qwen CLI and type /dedup
```

Result: `report/duplicates_report.md`.

## Input format

TSV, UTF-8, header row required:

```
id	section	name
T-1001	Переводы / По номеру телефона / СБП	Успешный перевод по номеру телефона через СБП на свой счёт
T-1002	Переводы / На карту / Внутренний	Перевод на карту другого клиента банка
```

- `id` — unique string identifier.
- `section` — folder path from the TMS, segments joined by ` / ` (configurable via `--section-sep`).
- `name` — test title.

## Pipeline

1. **parse** — TSV → `artifacts/01_tests.json` + `01_sections.json`.
2. **classify-auto** (2a) — keyword heuristics classify each unique section as `transfer-type` / `feature` / `mixed` / `ambiguous`.
3. **qwen classifies ambiguous** (2b) — the qwen agent reads `02a_sections_ambiguous.json`, applies `prompts/classify_section.md`, writes `02b_llm_classified.json`. Then `classify-merge` produces `02b_sections_final.json`.
4. **features** — lemmatize names (pymorphy3), extract `transfer_type_set` from section + name.
5. **candidates** — block by `frozenset(transfer_type_set)` (feature-only block sub-blocked by last section segment). Inside each block: TF-IDF (char_wb 3-5 + word 1-2) + rapidfuzz `token_set_ratio`, combined, top-K=5, threshold `LOWER=0.60`.
6. **qwen arbitrates pairs** (5) — the qwen agent processes batches of 25 pairs, writing JSONL verdicts (`duplicate` / `different_transfer_type` / `different_functionality` / `uncertain`).
7. **cluster + report** — connected components on `duplicate`-edges → `report/duplicates_report.md`.

## Running via qwen CLI

Open qwen CLI inside this project directory:

```
/dedup
```

The agent auto-runs every stage, pausing only when LLM work is required (Stage 2b and Stage 5). If a run is interrupted, rerun with `/dedup-resume`.

## Idempotency

Each stage caches by `(input_hash, lexicon_hash)` in the artifact's `_meta` block. Changes to `lexicon.py` or `stopwords.py` automatically invalidate downstream stages. Reset with `uv run tms-dedup clean` (or `clean --deep` to drop the lemma cache too).
