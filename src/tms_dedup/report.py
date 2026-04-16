"""Stage 6b: render the final Markdown report."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from tms_dedup import config
from tms_dedup.io_utils import read_json
from tms_dedup.lexicon import lexicon_hash
from tms_dedup.stopwords import stopwords_hash

TEMPLATE = Template(
    """# Duplicate tests report

Generated: {{ generated_at }}
Lexicon hash: `{{ lexicon_hash }}`
Thresholds: LOWER={{ cfg.lower_threshold }}, UPPER={{ cfg.upper_threshold }}, TOP_K={{ cfg.top_k }}

## Summary

- Total tests analyzed: **{{ total_tests }}**
- Candidate pairs: **{{ candidate_count }}**
- Verdicts: duplicate = {{ counts.duplicate }}, different_transfer_type = {{ counts.different_transfer_type }}, different_functionality = {{ counts.different_functionality }}, uncertain = {{ counts.uncertain }}
- Duplicate groups: **{{ group_count }}** (largest size: {{ largest_size }})
- Ambiguous sections: {{ ambiguous_count }}

## Duplicate groups

{% if groups %}{% for g in groups %}### Group #{{ loop.index }} — size {{ g.size }}, transfer types: {{ g.tt_repr }}

| ID | Section | Name |
|----|---------|------|
{% for m in g.members %}| `{{ m.id }}` | {{ m.section }} | {{ m.name }} |
{% endfor %}
Pair evidence:
{% for e in g.pair_edges %}- `{{ e.a_id }}` ↔ `{{ e.b_id }}` — score {{ "%.3f"|format(e.score) }}: {{ e.reason or "(no reason provided)" }}
{% endfor %}

{% endfor %}{% else %}_No duplicate groups found._
{% endif %}

## Uncertain pairs (need human review)

{% if uncertain %}| a_id | b_id | score | a name | b name | reason |
|------|------|-------|--------|--------|--------|
{% for u in uncertain %}| `{{ u.a_id }}` | `{{ u.b_id }}` | {{ "%.3f"|format(u.score) }} | {{ u.a_name }} | {{ u.b_name }} | {{ u.reason }} |
{% endfor %}{% else %}_None._
{% endif %}

## Different-transfer-type lookalikes (informational)

{% if diff_type %}| a_id | b_id | score | a | b | reason |
|------|------|-------|---|---|--------|
{% for u in diff_type %}| `{{ u.a_id }}` | `{{ u.b_id }}` | {{ "%.3f"|format(u.score) }} | {{ u.a_name }} ({{ u.a_types }}) | {{ u.b_name }} ({{ u.b_types }}) | {{ u.reason }} |
{% endfor %}{% else %}_None._
{% endif %}

## Ambiguous sections

{% if ambiguous_sections %}| Section | Final category | Transfer types | Source |
|---------|----------------|----------------|--------|
{% for s in ambiguous_sections %}| {{ s.section_path }} | {{ s.category }} | {{ ", ".join(s.transfer_types) if s.transfer_types else "—" }} | {{ s.source }} |
{% endfor %}{% else %}_All sections classified by heuristics alone._
{% endif %}

## Methodology

Two tests are flagged as duplicates when (1) they share the same transfer-type set (extracted from the section path and the test name) and (2) the qwen-coder LLM confirms that their semantic intent is identical. Candidate pairs are produced by TF-IDF (char_wb 3–5 + word 1–2) combined with `rapidfuzz.token_set_ratio`, weighted as char={{ cfg.w_tfidf_char }} / word={{ cfg.w_tfidf_word }} / fuzz={{ cfg.w_fuzz }}. Blocking ensures that tests with different transfer-type sets are never compared.

Stopwords hash: `{{ stopwords_hash }}`.
"""
)


def run(
    clusters_in: Path | None = None,
    verdicts_in: Path | None = None,
    features_in: Path | None = None,
    candidates_in: Path | None = None,
    sections_final_in: Path | None = None,
    out: Path | None = None,
) -> None:
    clusters_in = clusters_in or config.CLUSTERS_JSON
    verdicts_in = verdicts_in or config.VERDICTS_JSON
    features_in = features_in or config.TEST_FEATURES_JSON
    candidates_in = candidates_in or config.CANDIDATES_JSON
    sections_final_in = sections_final_in or config.SECTIONS_FINAL_JSON
    out = out or config.REPORT_MD
    clusters = read_json(clusters_in)
    verdicts = read_json(verdicts_in)["verdicts"]
    features = read_json(features_in)
    candidates = read_json(candidates_in)
    sections = read_json(sections_final_in)["sections"]

    tests_by_id = {t["id"]: t for t in features["tests"]}

    counts = {"duplicate": 0, "different_transfer_type": 0, "different_functionality": 0, "uncertain": 0}
    for v in verdicts:
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1

    def _hydrate_group(g: dict) -> dict:
        members = [
            {
                "id": mid,
                "section": tests_by_id[mid]["section"] if mid in tests_by_id else "?",
                "name": tests_by_id[mid]["name"] if mid in tests_by_id else "?",
            }
            for mid in g["member_ids"]
        ]
        tt_repr = (
            " | ".join("{" + ", ".join(t) + "}" for t in g["transfer_type_sets"])
            or "{∅}"
        )
        return {
            "size": g["size"],
            "members": members,
            "pair_edges": g["pair_edges"],
            "tt_repr": tt_repr,
        }

    groups = [_hydrate_group(g) for g in clusters["groups"]]

    uncertain = []
    diff_type = []
    for v in verdicts:
        if v["verdict"] == "uncertain":
            a = tests_by_id.get(v["a_id"], {})
            b = tests_by_id.get(v["b_id"], {})
            uncertain.append(
                {
                    "a_id": v["a_id"],
                    "b_id": v["b_id"],
                    "score": v["score"],
                    "a_name": a.get("name", "?"),
                    "b_name": b.get("name", "?"),
                    "reason": v.get("reason", ""),
                }
            )
        elif v["verdict"] == "different_transfer_type":
            a = tests_by_id.get(v["a_id"], {})
            b = tests_by_id.get(v["b_id"], {})
            diff_type.append(
                {
                    "a_id": v["a_id"],
                    "b_id": v["b_id"],
                    "score": v["score"],
                    "a_name": a.get("name", "?"),
                    "b_name": b.get("name", "?"),
                    "a_types": ",".join(a.get("transfer_type_set", [])) or "∅",
                    "b_types": ",".join(b.get("transfer_type_set", [])) or "∅",
                    "reason": v.get("reason", ""),
                }
            )

    ambiguous_sections = [s for s in sections if s.get("source") != "heuristic"]

    largest_size = max((g["size"] for g in clusters["groups"]), default=0)

    text = TEMPLATE.render(
        generated_at=datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        lexicon_hash=lexicon_hash(),
        stopwords_hash=stopwords_hash(),
        cfg=candidates["config"],
        total_tests=features["count"],
        candidate_count=candidates["count"],
        counts=counts,
        group_count=clusters["group_count"],
        largest_size=largest_size,
        ambiguous_count=len(ambiguous_sections),
        groups=groups,
        uncertain=uncertain,
        diff_type=diff_type,
        ambiguous_sections=ambiguous_sections,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
