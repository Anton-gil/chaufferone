"""Cascade simulator - 'if I miss this, what breaks?'

Forward walk over the blocking subgraph, summing penalty amounts of every
downstream obligation that becomes unactionable.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from app.graph.dag import blocking_subgraph


@dataclass
class CascadeStep:
    obligation_id: str
    title: str
    direct_penalty: float
    reason: str


@dataclass
class CascadeResult:
    root_id: str
    total_exposure_inr: float
    step_count: int
    steps: list[CascadeStep]


def _penalty(g: nx.DiGraph, nid: str) -> float:
    d = g.nodes[nid]["data"]
    return float(d.penalty_amount or 0)


def simulate_miss(g: nx.DiGraph, obligation_id: str) -> CascadeResult:
    if obligation_id not in g:
        raise KeyError(obligation_id)
    sub = blocking_subgraph(g)

    root_data = g.nodes[obligation_id]["data"]
    total = _penalty(g, obligation_id)
    steps: list[CascadeStep] = [
        CascadeStep(
            obligation_id=obligation_id,
            title=root_data.title,
            direct_penalty=total,
            reason="direct_penalty",
        )
    ]

    if obligation_id in sub:
        downstream = nx.descendants(sub, obligation_id)
        for dep_id in downstream:
            dep_data = g.nodes[dep_id]["data"]
            dep_penalty = _penalty(g, dep_id)
            total += dep_penalty
            steps.append(
                CascadeStep(
                    obligation_id=dep_id,
                    title=dep_data.title,
                    direct_penalty=dep_penalty,
                    reason=f"blocked_by_{obligation_id}",
                )
            )

    return CascadeResult(
        root_id=obligation_id,
        total_exposure_inr=total,
        step_count=len(steps),
        steps=steps,
    )
