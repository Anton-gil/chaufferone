"""Deduplicate obligations that arrive from multiple channels (email + SMS + reminder)."""

from datetime import date, timedelta

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.db.models import Obligation


def normalize_vendor(vendor: str | None) -> str | None:
    if not vendor:
        return None
    v = vendor.lower().strip()
    for suffix in (" ltd", " limited", " pvt", " private", " inc", ".com"):
        v = v.replace(suffix, "")
    return " ".join(v.split())


def find_duplicate(
    db: Session,
    user_id: str,
    vendor: str | None,
    amount: float | None,
    due_date: date | None,
) -> Obligation | None:
    """Merge score threshold from he.md §Extraction Stage 4."""
    if not vendor:
        return None
    vn = normalize_vendor(vendor)
    date_lo = due_date - timedelta(days=5) if due_date else None
    date_hi = due_date + timedelta(days=5) if due_date else None

    q = db.query(Obligation).filter(Obligation.user_id == user_id)
    if date_lo and date_hi:
        q = q.filter(Obligation.due_date.between(date_lo, date_hi))

    for cand in q.limit(50).all():
        cand_vn = cand.vendor_normalized or normalize_vendor(cand.vendor)
        if not cand_vn:
            continue
        vendor_score = fuzz.token_set_ratio(vn, cand_vn) / 100.0
        amount_score = 1.0
        if amount and cand.amount:
            diff = abs(float(cand.amount) - amount) / max(amount, float(cand.amount))
            amount_score = max(0.0, 1.0 - diff * 10)
        merge_score = 0.6 * vendor_score + 0.4 * amount_score
        if merge_score >= 0.7:
            return cand
    return None
