"""Act on bank SMS signals from the regex fast path (handoff-v2 §3 VERIFY).

    pre_debit_notice -> the RBI-mandated >=24h notice: attach to a matching obligation, or
                        create a fixed-date auto-debit obligation (the clash trigger)
    debit            -> match an active planned payment by amount (+ payee, + date) and
                        mark it verified: the bank's own debit SMS is the proof
    credit / salary  -> mark a matching expected income as received
Unmatched debits/credits are history, not obligations, and are left alone.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app import events
from app.clock import today as clock_today
from app.db.models import Obligation, UserPreferences
from app.extract.dedup import normalize_vendor
from app.money.forecast import effective_date, is_active


def _amount_close(a: float | None, b: float | None, pct: float) -> bool:
    if not a or not b:
        return False
    return abs(float(a) - float(b)) <= max(1.0, pct * max(float(a), float(b)))


def _name_score(payee: str | None, *names: str | None) -> float:
    if not payee:
        return 0.0
    p = payee.lower()
    best = 0.0
    for n in names:
        if not n:
            continue
        n = n.lower()
        if "@" in p and p == n:
            return 1.0
        best = max(best, fuzz.token_set_ratio(p.split("@")[0], n) / 100.0)
    return best


def _source(source_type: str, source_ref: str, label: str) -> dict[str, Any]:
    return {"type": source_type, "ref": source_ref, "label": label}


def _note_trigger(user_id: str, obligation_id: str) -> None:
    from app.planner import note_trigger

    note_trigger(user_id, obligation_id)


def _pre_debit(db: Session, user_id: str, sig: dict[str, Any], *, source_type: str, source_ref: str):
    amount, debit_on, payee = sig.get("amount"), sig.get("due_date"), sig.get("payee")
    if not amount or not debit_on:
        return None, "pre_debit_incomplete"
    signal = {"amount": amount, "date": str(debit_on), "payee": payee, "source_ref": source_ref}

    for o in db.query(Obligation).filter(Obligation.user_id == user_id).all():
        if not is_active(o) or o.obligation_type == "income":
            continue
        d = effective_date(o)
        if not d or abs((d - debit_on).days) > 3 or not _amount_close(o.amount, amount, 0.05):
            continue
        if payee and _name_score(payee, o.vendor, o.payee, o.title) < 0.6:
            continue
        o.signal_pre_debit = signal
        o.auto_pay_enabled = True
        o.planned_on = debit_on
        o.verification_state = "pre_debit_seen"
        o.sources = (o.sources or []) + [_source(source_type, source_ref, "Bank pre-debit notice")]
        db.commit()
        _note_trigger(user_id, o.id)
        return o.id, "pre_debit_matched"

    name = payee or "Upcoming auto-debit"
    ob = Obligation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=f"{name} renewal (AutoPay)" if payee else name,
        vendor=payee,
        vendor_normalized=normalize_vendor(payee),
        category="subscription",
        obligation_type="renewal",
        amount=amount,
        currency="INR",
        amount_confidence=0.95,
        due_date=debit_on,
        planned_on=debit_on,
        lead_time_days=0,
        penalty={
            "type": "none",
            "amount": 0,
            "description": "Auto-debit by mandate. Only you can pause it, in your UPI app, "
            "before the 24h notice window ends.",
        },
        resources={"inr": amount},
        auto_pay_enabled=True,
        confidence=0.9,
        verification_state="pre_debit_seen",
        signal_pre_debit=signal,
        sources=[_source(source_type, source_ref, "Bank pre-debit notice")],
        urgency_tier="amber",
    )
    db.add(ob)
    db.commit()
    events.publish("obligation_created", {"obligation_id": ob.id, "title": ob.title, "amount": amount})
    _note_trigger(user_id, ob.id)
    return ob.id, "pre_debit_created"


def _debit(db: Session, user_id: str, sig: dict[str, Any], *, source_type: str, source_ref: str,
           received_at: date | None):
    amount = sig.get("amount")
    if not amount:
        return None, "debit_incomplete"
    txn_on: date = sig.get("txn_date") or received_at or clock_today()
    payee = sig.get("vpa") or sig.get("payee")

    best: tuple[float, Obligation] | None = None
    for o in db.query(Obligation).filter(Obligation.user_id == user_id).all():
        if not is_active(o) or o.obligation_type == "income":
            continue
        if not _amount_close(o.amount, amount, 0.01):
            continue
        d = effective_date(o)
        if d is None or abs((d - txn_on).days) > 10:
            continue
        score = 0.0
        if o.status == "approved" or o.verification_state in ("approved", "pay_link_shown"):
            score += 2
        score += 2 * _name_score(payee, o.payee, o.vendor, o.title)
        score -= abs((d - txn_on).days) / 10
        if best is None or score > best[0]:
            best = (score, o)
    if best is None:
        return None, "debit_unmatched"

    o = best[1]
    was_future = (effective_date(o) or txn_on) >= clock_today()
    o.signal_debit = {
        "amount": amount,
        "date": str(txn_on),
        "payee": payee,
        "ref": sig.get("ref"),
        "source_ref": source_ref,
    }
    o.status = "verified"
    o.verification_state = "verified"
    o.resolved_at = datetime.now()
    o.sources = (o.sources or []) + [_source(source_type, source_ref, "Bank debit SMS (proof of payment)")]
    if was_future:
        # The forecast anchors on a starting balance; money that just left must come off it.
        prefs = db.get(UserPreferences, user_id)
        if prefs is not None:
            prefs.starting_balance_inr = float(prefs.starting_balance_inr) - float(amount)
    db.commit()
    events.publish(
        "verified",
        {"obligation_id": o.id, "title": o.title, "amount": amount, "ref": sig.get("ref")},
    )
    return o.id, "debit_verified"


def _credit(db: Session, user_id: str, sig: dict[str, Any], *, source_type: str, source_ref: str,
            received_at: date | None):
    amount = sig.get("amount")
    on: date = sig.get("txn_date") or received_at or clock_today()
    for o in db.query(Obligation).filter(Obligation.user_id == user_id).all():
        if o.obligation_type != "income" or not is_active(o):
            continue
        d = effective_date(o)
        if d and abs((d - on).days) <= 5 and _amount_close(o.amount, amount, 0.05):
            o.status = "verified"
            o.verification_state = "verified"
            o.resolved_at = datetime.now()
            o.sources = (o.sources or []) + [_source(source_type, source_ref, "Bank credit SMS")]
            db.commit()
            events.publish("verified", {"obligation_id": o.id, "title": o.title, "amount": amount})
            return o.id, "credit_matched"
    return None, "credit_unmatched"


def handle_signal(
    db: Session,
    user_id: str,
    sig: dict[str, Any],
    *,
    source_type: str,
    source_ref: str,
    received_at: date | None = None,
) -> tuple[str | None, str]:
    kind = sig.get("signal_type")
    if kind == "pre_debit_notice":
        return _pre_debit(db, user_id, sig, source_type=source_type, source_ref=source_ref)
    if kind == "debit":
        return _debit(db, user_id, sig, source_type=source_type, source_ref=source_ref,
                      received_at=received_at)
    if kind in ("credit", "salary_credit"):
        return _credit(db, user_id, sig, source_type=source_type, source_ref=source_ref,
                       received_at=received_at)
    return None, "ignored"
