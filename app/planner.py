"""Planner: due dates + the prerequisite graph -> planned action dates, then a cash check.

planned_on rules (handoff-v2 §3):
    - payments are planned just-in-time: due - lead_time - MARGIN_DAYS
    - a prerequisite must finish before the thing that needs it:
      planned(prereq) <= planned(dependent) - edge lead time
    - "needs a free afternoon" categories (PUC test, vehicle service) snap to a weekend day;
      if already overdue, the next weekend day from today
    - auto-debit mandates and expected income are fixed on their date
    - dates the user chose by voice (plan_locked) are never overwritten
After planning, a floor clash in the 45-day forecast opens a voice-consent proposal.
"""

from __future__ import annotations

import threading
from datetime import date, timedelta

import networkx as nx
from sqlalchemy.orm import Session

from app import events
from app.clock import today as clock_today
from app.db.models import Obligation
from app.graph.dag import blocking_subgraph, build_graph
from app.money.clash import detect_clashes
from app.money.forecast import effective_date, forecast_daily, is_active

MARGIN_DAYS = 2
WEEKEND_CATEGORIES = {"puc_certificate", "vehicle_service"}

_trigger_lock = threading.Lock()
_last_trigger: dict[str, str] = {}


def note_trigger(user_id: str, obligation_id: str) -> None:
    """Remember which new obligation (e.g. a pre-debit notice) may have caused a clash."""
    with _trigger_lock:
        _last_trigger[user_id] = obligation_id


def _pop_trigger(user_id: str) -> str | None:
    with _trigger_lock:
        return _last_trigger.pop(user_id, None)


def _latest_weekend_on_or_before(d: date, not_before: date) -> date | None:
    for wd in (5, 6):  # prefer Saturday, then Sunday
        cur = d - timedelta(days=(d.weekday() - wd) % 7)
        if cur >= not_before:
            return cur
    return None


def _first_weekend_on_or_after(d: date) -> date:
    while d.weekday() < 5:
        d += timedelta(days=1)
    return d


def plan_dates(db: Session, user_id: str) -> int:
    """Recompute planned_on for every active, unlocked obligation. Returns #changed."""
    today = clock_today()
    graph = build_graph(db, user_id)
    sub = blocking_subgraph(graph)
    obs = {o.id: o for o in db.query(Obligation).filter(Obligation.user_id == user_id).all()}
    planned: dict[str, date | None] = {}
    changed = 0

    # Dependents first, so each prerequisite can be bounded by what needs it.
    for oid in reversed(list(nx.topological_sort(sub))):
        o = obs.get(oid)
        if o is None:
            continue
        if not is_active(o) or (o.plan_locked and o.planned_on):
            planned[oid] = effective_date(o)
            continue

        if o.obligation_type == "income" or o.auto_pay_enabled:
            new = o.due_date
        else:
            bounds: list[date] = []
            if o.due_date:
                bounds.append(o.due_date - timedelta(days=(o.lead_time_days or 0) + MARGIN_DAYS))
            for dep in sub.successors(oid):
                dep_date = planned.get(dep)
                if dep_date:
                    lead = int((sub.get_edge_data(oid, dep) or {}).get("lead_time_days", 0))
                    bounds.append(dep_date - timedelta(days=max(lead, 1)))
            if not bounds:
                new = None
            else:
                latest = min(bounds)
                if o.category in WEEKEND_CATEGORIES:
                    if latest < today:
                        new = _first_weekend_on_or_after(today)
                    else:
                        new = _latest_weekend_on_or_before(latest, today) or latest
                else:
                    new = max(latest, today)

        planned[oid] = new
        if new != o.planned_on:
            o.planned_on = new
            changed += 1

    if changed:
        db.commit()
    return changed


def replan_and_check(db: Session, user_id: str) -> dict[str, object]:
    changed = plan_dates(db, user_id)
    points, _ = forecast_daily(db, user_id)
    clashes = detect_clashes(points)
    floor = [c for c in clashes if c.tier == "floor"]
    out: dict[str, object] = {
        "replanned": changed,
        "clashes": len(clashes),
        "floor_clash": floor[0].model_dump(mode="json") if floor else None,
    }
    if changed:
        events.publish("plan_changed", {"replanned": changed})

    from app import consent

    trigger = _pop_trigger(user_id)
    if floor:
        proposal = consent.open_proposal_for(db, user_id, floor[0], trigger_id=trigger)
        out["proposal_id"] = proposal.id if proposal else None
    else:
        consent.clear_proposal(user_id)
    return out
