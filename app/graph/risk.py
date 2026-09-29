"""Risk scoring - per-factor decomposition (from he.md).

Score 0-100, tier bands: green 0-30, amber 31-60, red 61-100.
Each factor is capped so the score is auditable, not a black box.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import networkx as nx

from app.clock import today as clock_today
from app.graph.dag import blocking_subgraph
from app.graph.scheduler import compute_start_by


@dataclass
class RiskBreakdown:
    obligation_id: str
    score: int
    tier: str
    time_urgency: int      # 0-30
    penalty_severity: int  # 0-25
    prerequisite_risk: int # 0-20
    cash_flow_risk: int    # 0-15
    historical_miss: int   # 0-10
    cascade_exposure_inr: float
    start_by: date | None


def _tier(score: int) -> str:
    if score <= 30:
        return "green"
    if score <= 60:
        return "amber"
    return "red"


def _time_urgency(node_data, start_by: date | None, today: date) -> int:
    if not node_data.due_date:
        return 5
    days_to_due = (node_data.due_date - today).days
    if days_to_due <= 0:
        return 30
    if start_by:
        days_to_start = (start_by - today).days
        if days_to_start <= 0:
            return 28
        if days_to_start <= 3:
            return 22
        if days_to_start <= 7:
            return 15
    if days_to_due <= 3:
        return 25
    if days_to_due <= 7:
        return 18
    if days_to_due <= 14:
        return 10
    return 4


def _penalty_severity(node_data) -> int:
    p = node_data.penalty_amount or 0
    if p <= 0:
        return 0
    if p >= 100000:
        return 25
    if p >= 20000:
        return 20
    if p >= 5000:
        return 15
    if p >= 500:
        return 8
    return 3


def _prerequisite_risk(g: nx.DiGraph, obligation_id: str) -> int:
    sub = blocking_subgraph(g)
    if obligation_id not in sub:
        return 0
    ancestors = nx.ancestors(sub, obligation_id)
    if not ancestors:
        return 0
    unresolved = 0
    for a in ancestors:
        n = g.nodes[a]["data"]
        if n.status not in {"resolved", "completed", "verified"} and n.verification_state != "receipt_confirmed":
            unresolved += 1
    if unresolved == 0:
        return 0
    return min(20, 5 + unresolved * 4)


def _cash_flow_risk(node_data, upcoming_debits_inr: float, salary_buffer_inr: float) -> int:
    amount = node_data.amount or 0
    if amount <= 0:
        return 0
    demand_ratio = (amount + upcoming_debits_inr) / max(salary_buffer_inr, 1)
    if demand_ratio >= 1.0:
        return 15
    if demand_ratio >= 0.75:
        return 11
    if demand_ratio >= 0.5:
        return 7
    if demand_ratio >= 0.25:
        return 3
    return 0


def _historical_miss(miss_rate: float) -> int:
    if miss_rate >= 0.5:
        return 10
    if miss_rate >= 0.25:
        return 6
    if miss_rate >= 0.1:
        return 3
    return 0


def compute_risk(
    g: nx.DiGraph,
    obligation_id: str,
    *,
    today: date | None = None,
    upcoming_debits_inr: float = 0,
    salary_buffer_inr: float = 30000,
    vendor_miss_rate: float = 0,
    cascade_exposure_inr: float | None = None,
) -> RiskBreakdown:
    today = today or clock_today()
    node = g.nodes[obligation_id]["data"]
    start_by = compute_start_by(g, obligation_id)

    tu = _time_urgency(node, start_by, today)
    ps = _penalty_severity(node)
    pr = _prerequisite_risk(g, obligation_id)
    cf = _cash_flow_risk(node, upcoming_debits_inr, salary_buffer_inr)
    hm = _historical_miss(vendor_miss_rate)

    score = min(100, tu + ps + pr + cf + hm)
    return RiskBreakdown(
        obligation_id=obligation_id,
        score=score,
        tier=_tier(score),
        time_urgency=tu,
        penalty_severity=ps,
        prerequisite_risk=pr,
        cash_flow_risk=cf,
        historical_miss=hm,
        cascade_exposure_inr=cascade_exposure_inr or 0,
        start_by=start_by,
    )
