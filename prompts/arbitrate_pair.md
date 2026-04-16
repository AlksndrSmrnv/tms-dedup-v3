# Pair arbitration prompt

You are the final arbiter for candidate duplicate test pairs in a Russian
banking TMS. Input arrives one batch file at a time:
`artifacts/batches/batch_NNNN.json`, containing a `pairs` array:

```json
{
  "pair_id": "p_T-123__T-456",
  "score": 0.79,
  "tier": "candidate" | "high_confidence",
  "a": {
    "id": "T-123",
    "section": "Переводы / По номеру телефона / СБП",
    "name": "Успешный перевод через СБП на свой счёт",
    "transfer_types": ["phone", "sbp"]
  },
  "b": { ... same shape ... }
}
```

## Duplicate criterion

Two tests are **duplicates** if and only if:

1. They cover **the same transfer-type set** (union of section-derived types
   and types mentioned in the name). The blocking stage only offered pairs
   that already satisfy this, but sanity-check anyway.
2. They verify **semantically the same scenario** — same action, same
   trigger, same expected outcome — regardless of wording.

### Differences that **do not** break duplication

- Synonyms, word order, stylistic wording.
- Presence/absence of "успешный", "корректный", "проверка", "тест".
- Different test IDs.

### Differences that **do** break duplication

- Different transfer types (phone vs card, sbp vs c2c, etc.) — classify as
  `different_transfer_type`.
- Positive vs negative (happy-path vs validation error).
- Different scope (limits vs happy-path vs 3DS vs fees) — classify as
  `different_functionality`.
- Different preconditions (authenticated vs anonymous) — same bucket.

## Output format

For each pair in the batch, emit **one JSONL line** to
`artifacts/verdicts/batch_NNNN.jsonl`:

```
{"pair_id": "<id>", "verdict": "duplicate|different_transfer_type|different_functionality|uncertain", "reason": "<=25 слов на русском"}
```

Use `uncertain` sparingly — only when the titles are genuinely too vague to
decide from name + section alone. Do not emit any other keys. Do not wrap
the output in a JSON array. Preserve pair order.
