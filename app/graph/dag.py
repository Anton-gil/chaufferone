"""DAG construction from obligation rows + edges.

Wraps networkx.DiGraph. Nodes = obligation ids. Edges = "needs_first" (default),
plus soft edges (shares_money, shares_time, same_trip).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import networkx as nx
from sqlalchemy.orm import Session

from app.db.models import Obligation, PrerequisiteEdge


@dataclass
class NodeData:
    id: str
    title: str
    category: str | None
    due_date: date | None
    lead_time_days: int
    amount: float | None
    penalty_amount: float | None
    status: str
    verification_state: str
    risk_score: int
    urgency_tier: str


def _to_node(ob: Obligation) -> NodeData:
    p = ob.penalty or {}
    return NodeData(
        id=ob.id,
        title=ob.title,
        category=ob.category,
        due_date=ob.due_date,
        lead_time_days=ob.lead_time_days or 0,
        amount=float(ob.amount) if ob.amount is not None else None,
        penalty_amount=float(p.get("amount")) if p.get("amount") is not None else None,
        status=ob.status,
        verification_state=ob.verification_state,
        risk_score=ob.risk_score or 0,
        urgency_tier=ob.urgency_tier,
    )


def build_graph(db: Session, user_id: str) -> nx.DiGraph:
    """Blocking edge direction: prerequisite -> obligation (A must finish before B)."""
    g = nx.DiGraph()
    obs = db.query(Obligation).filter(Obligation.user_id == user_id).all()
    id_set = {o.id for o in obs}
    for o in obs:
        g.add_node(o.id, data=_to_node(o))

    edges = (
        db.query(PrerequisiteEdge)
        .filter(
            PrerequisiteEdge.obligation_id.in_(id_set),
            PrerequisiteEdge.prerequisite_id.in_(id_set),
        )
        .all()
    )
    for e in edges:
        g.add_edge(
            e.prerequisite_id,
            e.obligation_id,
            lead_time_days=e.lead_time_days,
            kind=e.edge_kind,
            is_blocking=e.is_blocking,
            legal_basis=e.legal_basis,
            confidence=float(e.confidence) if e.confidence is not None else None,
        )

    if not nx.is_directed_acyclic_graph(g):
        cycles = list(nx.simple_cycles(g))
        raise ValueError(f"prerequisite graph has {len(cycles)} cycle(s); first: {cycles[0]}")
    return g


def blocking_subgraph(g: nx.DiGraph) -> nx.DiGraph:
    """Only 'needs_first' + is_blocking edges."""
    keep = [
        (u, v)
        for u, v, d in g.edges(data=True)
        if d.get("kind", "needs_first") == "needs_first" and d.get("is_blocking", True)
    ]
    sub = g.edge_subgraph(keep).copy()
    for n in g.nodes:
        if n not in sub:
            sub.add_node(n, **g.nodes[n])
    return sub
