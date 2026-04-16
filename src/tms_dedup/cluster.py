"""Stage 6a: cluster tests by connected components over `duplicate`-verdicts."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from tms_dedup import config
from tms_dedup.io_utils import cache_hit, make_meta, read_json, sha256_file, write_json


def run(
    verdicts_in: Path | None = None,
    features_in: Path | None = None,
    out: Path | None = None,
    force: bool = False,
) -> None:
    verdicts_in = verdicts_in or config.VERDICTS_JSON
    features_in = features_in or config.TEST_FEATURES_JSON
    out = out or config.CLUSTERS_JSON
    input_hash = sha256_file(verdicts_in) + sha256_file(features_in)
    if not force and cache_hit(out, input_hash):
        return

    verdicts = read_json(verdicts_in)["verdicts"]
    tests = {t["id"]: t for t in read_json(features_in)["tests"]}

    g: nx.Graph = nx.Graph()
    # Only `duplicate` edges form clusters; other verdicts are informational.
    for v in verdicts:
        if v["verdict"] == "duplicate":
            g.add_edge(v["a_id"], v["b_id"], score=v["score"], reason=v.get("reason", ""))

    groups: list[dict] = []
    for comp in nx.connected_components(g):
        members = sorted(comp)
        # Gather pairwise evidence for the group.
        pair_edges = []
        for a, b in [(a, b) for a in members for b in members if a < b]:
            if g.has_edge(a, b):
                d = g.get_edge_data(a, b)
                pair_edges.append(
                    {"a_id": a, "b_id": b, "score": d["score"], "reason": d.get("reason", "")}
                )
        # Representative transfer_type_set (expect equal across the group).
        tt_sets = {tuple(sorted(tests[m]["transfer_type_set"])) for m in members if m in tests}
        groups.append(
            {
                "size": len(members),
                "member_ids": members,
                "transfer_type_sets": [list(s) for s in sorted(tt_sets)],
                "pair_edges": pair_edges,
            }
        )

    groups.sort(key=lambda g: (-g["size"], g["member_ids"]))
    write_json(
        out,
        {
            "_meta": make_meta("06_clusters", input_hash),
            "groups": groups,
            "group_count": len(groups),
            "duplicate_pair_count": sum(len(g["pair_edges"]) for g in groups),
        },
    )
