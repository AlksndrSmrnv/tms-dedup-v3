# Section classification prompt

You are classifying a TMS section path from a Russian-language banking test
management system. The product area is money transfers (переводы).

Input for each ambiguous section is provided in `artifacts/02a_sections_ambiguous.json`
as an array of objects with the following fields:

- `section_path` — full folder path, segments joined with ` / ` (example:
  `Переводы / По номеру телефона / СБП`).
- `segments` — array of path segments.
- `sample_names` — up to five real test titles that live in this section.
- `transfer_types` — canonical transfer-type tokens the heuristic already
  matched (may be empty).
- `feature_score` — heuristic feature-marker count.
- `confidence` — heuristic confidence (the reason you are seeing this entry).

## Decision rules

For every section, output **one** of these categories:

- `transfer-type` — the section groups tests strictly by money-transfer
  channel (phone, sbp, card, c2c, account/requisites, wallet, self,
  internal, external, international, qr, template, recurring). Tests in
  different transfer-type sections **cannot** be duplicates of each other.
- `feature` — the section groups tests by a functional area (limits, fees,
  validation, 3DS, notifications, templates-as-feature, history, drafts,
  favorites, recipient search, etc.). Tests from feature sections may be
  duplicates of tests from other sections as long as the transfer-type set
  matches.
- `mixed` — the section narrows a transfer-type **and** scopes a feature
  (e.g. "Переводы / СБП / Лимиты"). Treat the transfer-type narrowing as
  authoritative for blocking.
- `other` — neither applies (e.g. smoke/regression/archive catch-alls).

Also list `transfer_types` present in the path using canonical tokens from
this vocabulary only:

```
phone, sbp, card, c2c, account, wallet, self, internal, external,
international, qr, template, recurring
```

Empty array if the section carries no transfer-type signal.

## Output format

Write the combined result to `artifacts/02b_llm_classified.json` as:

```json
{
  "sections": [
    {
      "section_path": "<verbatim>",
      "category": "transfer-type" | "feature" | "mixed" | "other",
      "transfer_types": ["phone", "sbp"],
      "confidence": 0.0-1.0,
      "reason": "<=20 words explaining the decision, in Russian"
    }
  ]
}
```

Process the whole ambiguous list in one pass. Do not invent transfer-type
tokens outside the vocabulary above. Keep reasons short.
