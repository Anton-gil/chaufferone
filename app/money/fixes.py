"""Candidate fixes for a cash clash, each verified by re-running the forecast.

Kinds:
    defer              - move a movable payment later, but still before its deadline
                         (due + grace - lead time) and before anything that depends on it.
                         Skips income days so we never plan to pay on the same day money
                         is only *expected* to land.
    pause_mandate      - an auto-debit (UPI AutoPay / e-mandate). Only the customer can pause
                         it (RBI E-mandate Framework 2026), in their own UPI app, before the
                         24h pre-debit window closes. We only advise.
    pause_subscription - skip a low-penalty, non-mandate subscription this cycle.

A fix resolves the clash only if the re-simulated forecast has no floor breach anywhere in
the horizon. Ranked: resolves > stays out of the cushion > added penalty > disruption.
The top-k get option ids A, B, C.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.clock import today as clock_today
from app.db.models import Obligation
from app.graph.dag import blocking_subgraph, build_graph
from app.money.clash import detect_clashes
from app.money.forecast import effective_date, forecast_daily, is_active
from app.schemas.money import Clash, DayPoint, Fix

OPTION_IDS = ["A", "B", "C"]


def latest_allowed(o: Obligation, today: date) -> date | None:
    """Last day this obligation can be acted on and still meet its deadline.

    Overdue items (due already passed) have no due-date bound - sooner is always better.
    """
    if not o.due_date or o.due_date < today:
        return None
    return o.due_date + timedelta(days=o.flexibility_window or 0) - timedelta(
        days=max(o.lead_time_days or 0, 0)
    )


def _min_balance(points: list[DayPoint]) -> float:
    return min(p.closing_balance for p in points) if points else 0.0


def _simulate(
    db: Session, user_id: str, overrides: dict[str, date | None], horizon_days: int, today: date
) -> tuple[list[DayPoint], list[Clash]]:
    points, _ = forecast_daily(db, user_id, horizon_days, today, overrides)
    return points, detect_clashes(points)


def _score(fix: Fix, points: list[DayPoint], clashes: list[Clash]) -> None:
    fix.resulting_min_balance_inr = _min_balance(points)
    fix.resolves_clash = not any(c.tier == "floor" for c in clashes)
    fix.touches_cushion = any(c.tier == "cushion" for c in clashes)


def _expected_income_between(
    incomes: list[Obligation], after: date, upto: date
) -> Obligation | None:
    for inc in sorted(incomes, key=lambda o: effective_date(o) or date.max):
        d = effective_date(inc)
        if d and after < d <= upto:
            return inc
    return None


def propose_fixes(
    db: Session,
    user_id: str,
    clash: Clash,
    horizon_days: int = 45,
    top_k: int = 3,
) -> list[Fix]:
    today = clock_today()
    end = today + timedelta(days=horizon_days - 1)
    base_points, _ = forecast_daily(db, user_id, horizon_days, today)
    income_days = {p.date for p in base_points if p.income > 0}

    active = [
        o
        for o in db.query(Obligation).filter(Obligation.user_id == user_id).all()
        if is_active(o)
    ]
    planned = {o.id: effective_date(o) for o in active}
    incomes = [o for o in active if o.obligation_type == "income"]
    sub = blocking_subgraph(build_graph(db, user_id))

    candidates: list[Fix] = []

    # 1. Defer a movable payment to the earliest later day that clears the floor.
    for o in active:
        if o.obligation_type == "income" or o.auto_pay_enabled:
            continue
        if not o.amount or float(o.amount) <= 0:
            continue
        cur = planned.get(o.id)
        if cur is None or cur < today or cur > clash.last_breach_date:
            continue
        latest = latest_allowed(o, today) or end
        if o.id in sub:
            dependents = [planned[d] for d in sub.successors(o.id) if planned.get(d)]
            if dependents:
                latest = min(latest, min(dependents) - timedelta(days=1))
        d = cur + timedelta(days=1)
        while d <= min(latest, end):
            if d in income_days:  # never plan a payment on the day money is only expected
                d += timedelta(days=1)
                continue
            points, clashes = _simulate(db, user_id, {o.id: d}, horizon_days, today)
            if not any(c.tier == "floor" for c in clashes):
                inc = _expected_income_between(incomes, cur, d)
                fix = Fix(
                    kind="defer",
                    obligation_id=o.id,
                    obligation_title=o.title,
                    description=f"Pay {o.title} on {d:%a %d %b} instead of {cur:%a %d %b}"
                    + (f", after {inc.title} lands" if inc else "")
                    + (f" (still before the {o.due_date:%d %b} deadline)" if o.due_date else ""),
                    old_date=cur,
                    new_date=d,
                    disruption_score=10,
                    depends_on_income=inc.title if inc else None,
                    income_date=effective_date(inc) if inc else None,
                )
                _score(fix, points, clashes)
                candidates.append(fix)
                break
            d += timedelta(days=1)

    # 2. Pause an auto-debit mandate (user action in their UPI app, 24h before the debit).
    for o in active:
        if not o.auto_pay_enabled or o.obligation_type == "income":
            continue
        cur = planned.get(o.id)
        if cur is None or cur <= today or cur > clash.last_breach_date:
            continue
        deadline = cur - timedelta(days=1)
        name = o.vendor or o.title
        fix = Fix(
            kind="pause_mandate",
            obligation_id=o.id,
            obligation_title=o.title,
            description=(
                f"Pause the {name} auto-debit in your UPI app before {deadline:%a %d %b} "
                f"(saves Rs{float(o.amount or 0):,.0f} this cycle)"
            ),
            old_date=cur,
            deadline=deadline,
            disruption_score=30,
            requires_user_action=True,
        )
        points, clashes = _simulate(db, user_id, {o.id: None}, horizon_days, today)
        _score(fix, points, clashes)
        candidates.append(fix)

    # 3. Skip a low-penalty, non-mandate subscription due before the clash ends.
    for o in active:
        if o.auto_pay_enabled or o.obligation_type == "income":
            continue
        if o.category != "subscription":
            continue
        cur = planned.get(o.id)
        if cur is None or cur < today or cur > clash.last_breach_date:
            continue
        pen = float((o.penalty or {}).get("amount") or 0)
        if pen > 200:
            continue
        fix = Fix(
            kind="pause_subscription",
            obligation_id=o.id,
            obligation_title=o.title,
            description=f"Skip {o.title} this cycle (frees Rs{float(o.amount or 0):,.0f}, penalty Rs{pen:,.0f})",
            old_date=cur,
            added_penalty_inr=pen,
            disruption_score=30,
            requires_user_action=True,
        )
        points, clashes = _simulate(db, user_id, {o.id: None}, horizon_days, today)
        _score(fix, points, clashes)
        candidates.append(fix)

    candidates.sort(
        key=lambda f: (
            not f.resolves_clash,
            f.touches_cushion,
            f.added_penalty_inr,
            f.disruption_score,
            -f.resulting_min_balance_inr,
        )
    )
    resolving = [f for f in candidates if f.resolves_clash]
    top = (resolving or candidates)[:top_k]
    for fix, oid in zip(top, OPTION_IDS, strict=False):
        fix.id = oid
    return top
