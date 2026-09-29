"""Candidate fix generator for a clash.

Kinds:
    - defer: push a clash-contributing obligation to a later date within its flexibility_window
    - pause_subscription: skip a zero/low-penalty subscription due between today and the clash start
    - pull_forward: pay an obligation earlier (before a later income event) to smooth cash flow

Each fix is simulated by re-running the forecast with the change applied, scored by
resolves_clash + resulting_min_balance - added_penalty - disruption. Return top-k.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models import Obligation, UserPreferences
from app.money.clash import detect_clashes
from app.money.forecast import forecast_daily
from app.schemas.money import Clash, DayPoint, DebitEntry, Fix


def _min_balance_after(points: list[DayPoint]) -> float:
    return min(p.closing_balance for p in points) if points else 0.0


def _obligations_by_id(db: Session, ids: list[str]) -> dict[str, Obligation]:
    if not ids:
        return {}
    return {o.id: o for o in db.query(Obligation).filter(Obligation.id.in_(ids)).all()}


def _horizon_obligations(db: Session, user_id: str, today: date, end: date) -> list[Obligation]:
    return (
        db.query(Obligation)
        .filter(
            Obligation.user_id == user_id,
            Obligation.due_date.isnot(None),
            Obligation.due_date >= today,
            Obligation.due_date <= end,
            Obligation.status != "resolved",
            Obligation.amount.isnot(None),
        )
        .all()
    )


def _simulate_with_override(
    db: Session,
    user_id: str,
    override: dict[str, date | None],
    horizon_days: int,
) -> tuple[list[DayPoint], list[Clash]]:
    """Simulate the forecast with per-obligation date overrides (None = paused/skipped)."""
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:
        return [], []
    hard = float(prefs.hard_floor_inr)
    cushion = float(prefs.soft_cushion_inr)
    income_per = float(prefs.estimated_monthly_income_inr)
    salary_day = prefs.salary_day_of_month
    balance = float(prefs.starting_balance_inr)
    today = date.today()
    end = today + timedelta(days=horizon_days - 1)

    rows = (
        db.query(Obligation)
        .filter(
            Obligation.user_id == user_id,
            Obligation.due_date.isnot(None),
            Obligation.status != "resolved",
            Obligation.amount.isnot(None),
        )
        .all()
    )

    grouped: dict[date, list[tuple[Obligation, float]]] = {}
    for r in rows:
        if r.id in override:
            new_date = override[r.id]
            if new_date is None:
                continue
            eff = new_date
        else:
            eff = r.due_date
        if not (today <= eff <= end):
            continue
        amt = float(r.amount or 0)
        if amt <= 0:
            continue
        grouped.setdefault(eff, []).append((r, amt))

    def _is_salary(d: date) -> bool:
        if salary_day is None:
            return False
        month_end = calendar.monthrange(d.year, d.month)[1]
        return d.day == min(salary_day, month_end)

    points: list[DayPoint] = []
    cur = today
    for _ in range(horizon_days):
        opening = balance
        income = income_per if _is_salary(cur) else 0.0
        day = grouped.get(cur, [])
        entries = [
            DebitEntry(
                obligation_id=o.id,
                title=o.title,
                amount=amt,
                category=o.category,
                flexibility_window_days=o.flexibility_window or 0,
                penalty_amount=float((o.penalty or {}).get("amount") or 0),
            )
            for o, amt in day
        ]
        total_debit = sum(e.amount for e in entries)
        closing = opening + income - total_debit
        if closing < hard:
            breach = "floor"; depth = hard - closing
        elif closing < hard + cushion:
            breach = "cushion"; depth = (hard + cushion) - closing
        else:
            breach = "none"; depth = 0.0
        points.append(
            DayPoint(
                date=cur, opening_balance=opening, income=income,
                debits=entries, total_debit=total_debit,
                closing_balance=closing, breach_type=breach, breach_depth_inr=depth,
            )
        )
        balance = closing
        cur += timedelta(days=1)

    return points, detect_clashes(points)


def _next_salary_after(prefs: UserPreferences, after: date, horizon_end: date) -> date | None:
    if not prefs.salary_day_of_month:
        return None
    cur = after + timedelta(days=1)
    while cur <= horizon_end:
        month_end = calendar.monthrange(cur.year, cur.month)[1]
        if cur.day == min(prefs.salary_day_of_month, month_end):
            return cur
        cur += timedelta(days=1)
    return None


def _defer_candidates_for_clash(
    clash: Clash,
    obs: dict[str, Obligation],
    prefs: UserPreferences,
    horizon_end: date,
) -> list[Fix]:
    fixes: list[Fix] = []
    for oid in clash.obligations_involved:
        o = obs.get(oid)
        if not o or not o.due_date:
            continue
        window = o.flexibility_window or 0

        if window > 0:
            candidate_date = o.due_date + timedelta(days=window)
            fixes.append(
                Fix(
                    kind="defer",
                    obligation_id=oid,
                    obligation_title=o.title,
                    description=f"Defer {o.title} to {candidate_date.isoformat()} (end of {window}-day grace, no late fee)",
                    new_date=candidate_date,
                    added_penalty_inr=0,
                    disruption_score=15,
                    resolves_clash=False,
                    resulting_min_balance_inr=0,
                )
            )
            if window >= 2:
                half = o.due_date + timedelta(days=window // 2)
                fixes.append(
                    Fix(
                        kind="defer",
                        obligation_id=oid,
                        obligation_title=o.title,
                        description=f"Defer {o.title} to {half.isoformat()} (halfway through grace)",
                        new_date=half,
                        added_penalty_inr=0,
                        disruption_score=10,
                        resolves_clash=False,
                        resulting_min_balance_inr=0,
                    )
                )

        next_sal = _next_salary_after(prefs, o.due_date, horizon_end)
        if next_sal:
            late_target = next_sal + timedelta(days=1)
            penalty_amt = float((o.penalty or {}).get("amount") or 0)
            fixes.append(
                Fix(
                    kind="defer",
                    obligation_id=oid,
                    obligation_title=o.title,
                    description=(
                        f"Defer {o.title} to {late_target.isoformat()} "
                        f"(after {next_sal.isoformat()} salary; accepts Rs{penalty_amt:.0f} late fee)"
                    ),
                    new_date=late_target,
                    added_penalty_inr=penalty_amt,
                    disruption_score=25,
                    resolves_clash=False,
                    resulting_min_balance_inr=0,
                )
            )
    return fixes


def _pause_candidates_in_horizon(
    horizon_obs: list[Obligation],
    clash: Clash,
) -> list[Fix]:
    """Any zero/low-penalty subscription-like obligation due before clash starts frees cash."""
    fixes: list[Fix] = []
    for o in horizon_obs:
        if not o.due_date or o.due_date > clash.first_breach_date:
            continue
        if o.obligation_type not in {"renewal", "subscription"} and o.category != "subscription":
            continue
        pen = float((o.penalty or {}).get("amount") or 0)
        if pen > 200:
            continue
        fixes.append(
            Fix(
                kind="pause_subscription",
                obligation_id=o.id,
                obligation_title=o.title,
                description=f"Pause {o.title} this cycle (frees Rs{float(o.amount or 0):.0f}, penalty Rs{pen:.0f})",
                new_date=None,
                added_penalty_inr=pen,
                disruption_score=30,
                resolves_clash=False,
                resulting_min_balance_inr=0,
            )
        )
    return fixes


def propose_fixes(
    db: Session,
    user_id: str,
    clash: Clash,
    horizon_days: int = 45,
    top_k: int = 3,
) -> list[Fix]:
    today = date.today()
    end = today + timedelta(days=horizon_days - 1)
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:
        return []
    clash_obs = _obligations_by_id(db, list(clash.obligations_involved))
    horizon_obs = _horizon_obligations(db, user_id, today, end)

    candidates = (
        _defer_candidates_for_clash(clash, clash_obs, prefs, end)
        + _pause_candidates_in_horizon(horizon_obs, clash)
    )

    baseline_points, _ = forecast_daily(db, user_id, horizon_days=horizon_days)
    baseline_min = _min_balance_after(baseline_points)

    scored: list[tuple[float, Fix]] = []
    for fix in candidates:
        override: dict[str, date | None] = {fix.obligation_id: fix.new_date}
        points, new_clashes = _simulate_with_override(db, user_id, override, horizon_days)
        new_min = _min_balance_after(points)
        fix.resulting_min_balance_inr = new_min
        # Honest: a fix truly resolves the clash iff the resulting forecast has NO floor breach.
        fix.resolves_clash = not any(c.tier == "floor" for c in new_clashes)

        score = 100.0
        score -= min((new_min - baseline_min) / 100.0, 200)  # bigger balance improvement = better
        if fix.resolves_clash:
            score -= 80
        score += fix.added_penalty_inr / 100
        score += fix.disruption_score
        scored.append((score, fix))

    scored.sort(key=lambda t: t[0])
    return [f for _, f in scored[:top_k]]
