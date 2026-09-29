"""45-day daily balance forecast.

balance[d+1] = balance[d] + income[d] - sum(debits[d])

Income: the monthly allowance/salary on prefs.salary_day_of_month, plus any
obligation_type="income" rows (e.g. an expected freelance payment).
Debits: every active obligation with an amount, on its planned_on date (falls
back to due_date). `overrides` lets the fix search and the consent loop simulate
moving ({id: date}) or pausing ({id: None}) obligations without touching the DB.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.clock import today as clock_today
from app.db.models import Obligation, UserPreferences
from app.schemas.money import DayPoint, DebitEntry

INACTIVE_STATUSES = {"resolved", "paid", "verified", "paused", "pause_requested", "dismissed"}


def is_active(o: Obligation) -> bool:
    return (o.status or "upcoming") not in INACTIVE_STATUSES


def effective_date(o: Obligation) -> date | None:
    return o.planned_on or o.due_date


def _get_or_default_prefs(db: Session, user_id: str) -> UserPreferences:
    prefs = db.get(UserPreferences, user_id)
    if prefs:
        return prefs
    prefs = UserPreferences(user_id=user_id)
    db.add(prefs)
    db.commit()
    return prefs


def _month_end_day(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _salary_day_for(d: date, target_day: int | None) -> bool:
    if target_day is None:
        return False
    # If the target day exceeds this month's length, credit on the last day
    return d.day == min(target_day, _month_end_day(d))


def _entry(o: Obligation, amount: float) -> DebitEntry:
    p = o.penalty or {}
    return DebitEntry(
        obligation_id=o.id,
        title=o.title,
        amount=amount,
        category=o.category,
        flexibility_window_days=o.flexibility_window or 0,
        penalty_amount=float(p.get("amount") or 0),
    )


def _cash_events(
    db: Session,
    user_id: str,
    start: date,
    end: date,
    overrides: dict[str, date | None],
) -> tuple[dict[date, list[DebitEntry]], dict[date, list[DebitEntry]]]:
    rows = (
        db.query(Obligation)
        .filter(Obligation.user_id == user_id, Obligation.amount.isnot(None))
        .all()
    )
    debits: dict[date, list[DebitEntry]] = {}
    credits: dict[date, list[DebitEntry]] = {}
    for r in rows:
        if not is_active(r):
            continue
        amount = float(r.amount or 0)
        if amount <= 0:
            continue
        if r.id in overrides:
            eff = overrides[r.id]
            if eff is None:
                continue
        else:
            eff = effective_date(r)
        if eff is None or not (start <= eff <= end):
            continue
        bucket = credits if r.obligation_type == "income" else debits
        bucket.setdefault(eff, []).append(_entry(r, amount))
    return debits, credits


def forecast_daily(
    db: Session,
    user_id: str,
    horizon_days: int = 45,
    today: date | None = None,
    overrides: dict[str, date | None] | None = None,
) -> tuple[list[DayPoint], UserPreferences]:
    today = today or clock_today()
    prefs = _get_or_default_prefs(db, user_id)
    end = today + timedelta(days=horizon_days - 1)
    debits, credits = _cash_events(db, user_id, today, end, overrides or {})

    hard = float(prefs.hard_floor_inr)
    cushion = float(prefs.soft_cushion_inr)
    income_per = float(prefs.estimated_monthly_income_inr)
    salary_day = prefs.salary_day_of_month
    balance = float(prefs.starting_balance_inr)

    points: list[DayPoint] = []
    cur = today
    for _ in range(horizon_days):
        opening = balance
        day_credits = credits.get(cur, [])
        income = (income_per if _salary_day_for(cur, salary_day) else 0.0) + sum(
            c.amount for c in day_credits
        )
        entries = debits.get(cur, [])
        total_debit = sum(e.amount for e in entries)
        closing = opening + income - total_debit

        if closing < hard:
            breach = "floor"
            depth = hard - closing
        elif closing < hard + cushion:
            breach = "cushion"
            depth = (hard + cushion) - closing
        else:
            breach = "none"
            depth = 0.0

        points.append(
            DayPoint(
                date=cur,
                opening_balance=opening,
                income=income,
                debits=entries,
                credits=day_credits,
                total_debit=total_debit,
                closing_balance=closing,
                breach_type=breach,
                breach_depth_inr=depth,
            )
        )
        balance = closing
        cur += timedelta(days=1)

    return points, prefs
