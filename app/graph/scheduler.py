"""Backward scheduling - MRP-style start-by dates.

For each obligation:
    start_by = due_date - own_lead_time - longest_prereq_chain_lead - safety_margin

Walks the DAG backwards from due dates. Uses the blocking subgraph so soft
edges (shares_money, shares_time) don't inflate lead time.
"""

from __future__ import annotations

from datetime import date, timedelta

import networkx as nx

from app.graph.dag import NodeData, blocking_subgraph


SAFETY_MARGIN_DAYS = 2


def _node(g: nx.DiGraph, nid: str) -> NodeData:
    return g.nodes[nid]["data"]


def _edge_lead(g: nx.DiGraph, u: str, v: str) -> int:
    d = g.get_edge_data(u, v) or {}
    return int(d.get("lead_time_days", 0))


def longest_prereq_chain_days(g: nx.DiGraph, node_id: str) -> int:
    """Sum of lead times along the longest path from a source-ancestor to node_id."""
    sub = blocking_subgraph(g)
    if node_id not in sub:
        return 0
    ancestors = nx.ancestors(sub, node_id) | {node_id}
    ancestor_sub = sub.subgraph(ancestors).copy()

    # weight each incoming edge by its lead time, plus the target node's own lead
    for u, v, d in ancestor_sub.edges(data=True):
        d["weight"] = int(d.get("lead_time_days", 0)) + _node(ancestor_sub, v).lead_time_days

    best = 0
    for src in [n for n in ancestor_sub.nodes if ancestor_sub.in_degree(n) == 0]:
        if src == node_id:
            continue
        try:
            path_len = nx.dag_longest_path_length(
                ancestor_sub.subgraph(nx.descendants(ancestor_sub, src) | {src}),
                weight="weight",
            )
            best = max(best, path_len + _node(ancestor_sub, src).lead_time_days)
        except nx.NetworkXError:
            continue
    return best


def compute_start_by(g: nx.DiGraph, node_id: str, margin: int = SAFETY_MARGIN_DAYS) -> date | None:
    node = _node(g, node_id)
    if not node.due_date:
        return None
    prereq_days = longest_prereq_chain_days(g, node_id)
    total = node.lead_time_days + prereq_days + margin
    return node.due_date - timedelta(days=total)


def schedule_all(g: nx.DiGraph, margin: int = SAFETY_MARGIN_DAYS) -> dict[str, date | None]:
    return {n: compute_start_by(g, n, margin) for n in g.nodes}
