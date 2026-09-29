"""Spending insights (P6 lite).

Reads verified debits (obligations with signal_debit and status='verified')
and rolls them up into three views the /insights page renders:
    - by_category    ({category: total_inr})
    - top_vendors    (top 5 by total)
    - buffer_touch   (min projected balance vs. hard floor for the next 45 days)

Only aggregations. No ML. No prediction. Advice, not automation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.clock import today as clock_today
from app.db.models import Obligation
from app.money.forecast import forecast_daily


def _debit_date(o: Obligation) -> date | None:
    sig = o.signal_debit or {}
    raw = sig.get("date")
    if not raw:
        return o.resolved_at.date() if o.resolved_at else None
    try:
        return date.fromisoformat(raw[:10])
    except (TypeError, ValueError):
        return None


def _in_window(d: date | None, cutoff: date) -> bool:
    return d is not None and d >= cutoff


def summarize(db: Session, user_id: str, *, window_days: int = 60) -> dict[str, Any]:
    today = clock_today()
    cutoff = today - timedelta(days=window_days)

    obligations = db.query(Obligation).filter(Obligation.user_id == user_id).all()
    verified = [o for o in obligations if (o.signal_debit or o.status == "verified") and o.amount]

    by_category: dict[str, float] = defaultdict(float)
    by_vendor: dict[str, float] = defaultdict(float)
    dead_subs: list[dict[str, Any]] = []
    total_verified = 0.0
    count_in_window = 0

    for o in verified:
        d = _debit_date(o)
        if not _in_window(d, cutoff):
            continue
        amt = float(o.amount or 0)
        by_category[(o.category or "uncategorized")] += amt
        by_vendor[(o.vendor or "unknown")] += amt
        total_verified += amt
        count_in_window += 1

    for o in obligations:
        if o.category != "subscription" or o.status in ("verified", "paid", "resolved", "paused"):
            continue
        d = _debit_date(o)
        if d is None or d < today - timedelta(days=window_days):
            dead_subs.append(
                {
                    "id": o.id,
                    "title": o.title,
                    "vendor": o.vendor,
                    "amount_inr": float(o.amount) if o.amount is not None else None,
                    "last_debit": d.isoformat() if d else None,
                }
            )

    points, prefs = forecast_daily(db, user_id)
    min_bal = min((p.closing_balance for p in points), default=float(prefs.starting_balance_inr))
    closest_to_floor = float(min_bal) - float(prefs.hard_floor_inr)

    top_vendors = sorted(
        ({"vendor": v, "total_inr": round(t, 2)} for v, t in by_vendor.items()),
        key=lambda r: -r["total_inr"],
    )[:5]

    return {
        "window_days": window_days,
        "as_of": today.isoformat(),
        "totals": {
            "spent_inr": round(total_verified, 2),
            "verified_count": count_in_window,
        },
        "by_category": [
            {"category": k, "total_inr": round(v, 2)} for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        "top_vendors": top_vendors,
        "dead_subscriptions": dead_subs,
        "buffer_touch": {
            "min_balance_inr": round(float(min_bal), 2),
            "floor_inr": float(prefs.hard_floor_inr),
            "cushion_inr": float(prefs.soft_cushion_inr),
            "closest_gap_to_floor_inr": round(closest_to_floor, 2),
        },
    }
