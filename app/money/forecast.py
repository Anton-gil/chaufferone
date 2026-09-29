"""45-day daily balance forecast.

balance[d+1] = balance[d] + income[d] - sum(planned_debits[d])

Income: monthly salary/allowance on prefs.salary_day_of_month.
Debits: obligations with due_date in window and status != resolved.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models import Obligation, UserPreferences
from app.schemas.money import DayPoint, DebitEntry


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


def _debits_on(
    db: Session,
    user_id: str,
    start: date,
    end: date,
) -> dict[date, list[Obligation]]:
    rows = (
        db.query(Obligation)
        .filter(
            Obligation.user_id == user_id,
            Obligation.due_date.isnot(None),
            Obligation.due_date >= start,
            Obligation.due_date <= end,
            Obligation.status != "resolved",
            Obligation.amount.isnot(None),
        )
        .all()
    )
    grouped: dict[date, list[Obligation]] = {}
    for r in rows:
        if float(r.amount or 0) <= 0:
            continue
        grouped.setdefault(r.due_date, []).append(r)
    return grouped


def _debit_entry(o: Obligation) -> DebitEntry:
    p = o.penalty or {}
    return DebitEntry(
        obligation_id=o.id,
        title=o.title,
        amount=float(o.amount or 0),
        category=o.category,
        flexibility_window_days=o.flexibility_window or 0,
        penalty_amount=float(p.get("amount") or 0),
    )


def forecast_daily(
    db: Session,
    user_id: str,
    horizon_days: int = 45,
    today: date | None = None,
) -> tuple[list[DayPoint], UserPreferences]:
    today = today or date.today()
    prefs = _get_or_default_prefs(db, user_id)
    end = today + timedelta(days=horizon_days - 1)
    debits = _debits_on(db, user_id, today, end)

    hard = float(prefs.hard_floor_inr)
    cushion = float(prefs.soft_cushion_inr)
    income_per = float(prefs.estimated_monthly_income_inr)
    salary_day = prefs.salary_day_of_month
    balance = float(prefs.starting_balance_inr)

    points: list[DayPoint] = []
    cur = today
    for _ in range(horizon_days):
        opening = balance
        income = income_per if _salary_day_for(cur, salary_day) else 0.0
        day_debits = debits.get(cur, [])
        entries = [_debit_entry(o) for o in day_debits]
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
                total_debit=total_debit,
                closing_balance=closing,
                breach_type=breach,
                breach_depth_inr=depth,
            )
        )
        balance = closing
        cur += timedelta(days=1)

    return points, prefs
