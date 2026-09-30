"""DPDP-compliant data export and erasure (§7.4).

Export: one-tap JSON dump of everything Chaufferone knows about the user.
Erase:  wipes obligations, edges, signals, documents, history, consent log
        and preferences. Keeps outbound_log (server-side operational record,
        not user data) so users can still audit what happened before erasure.

Erasure is destructive and irreversible - the API requires a confirmation
sentinel in the request body, not just an approve-once-remember button.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    ConsentLog,
    Document,
    Obligation,
    ObligationHistory,
    PrerequisiteEdge,
    ProcessedSignal,
    UserPreferences,
    VendorPattern,
)

ERASE_CONFIRM = "YES-DELETE-EVERYTHING"


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _row_dict(row: Any) -> dict[str, Any]:
    return {c.name: _jsonable(getattr(row, c.name)) for c in row.__table__.columns}


def export_all(db: Session, user_id: str) -> dict[str, Any]:
    obligations = db.query(Obligation).filter(Obligation.user_id == user_id).all()
    ob_ids = {o.id for o in obligations}
    edges = [
        e
        for e in db.query(PrerequisiteEdge).all()
        if e.obligation_id in ob_ids or e.prerequisite_id in ob_ids
    ]
    return {
        "product": "chaufferone",
        "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "user_id": user_id,
        "notice": "This file contains everything Chaufferone stored about you. Keep it safe.",
        "obligations": [_row_dict(o) for o in obligations],
        "prerequisite_edges": [_row_dict(e) for e in edges],
        "processed_signals": [
            _row_dict(s)
            for s in db.query(ProcessedSignal).filter(ProcessedSignal.user_id == user_id).all()
        ],
        "documents": [
            _row_dict(d) for d in db.query(Document).filter(Document.user_id == user_id).all()
        ],
        "consent_log": [
            _row_dict(c) for c in db.query(ConsentLog).filter(ConsentLog.user_id == user_id).all()
        ],
        "vendor_patterns": [
            _row_dict(v)
            for v in db.query(VendorPattern).filter(VendorPattern.user_id == user_id).all()
        ],
        "obligation_history": [
            _row_dict(h)
            for h in db.query(ObligationHistory).filter(ObligationHistory.user_id == user_id).all()
        ],
        "user_preferences": (
            _row_dict(prefs)
            if (prefs := db.get(UserPreferences, user_id)) is not None
            else None
        ),
    }


def erase_all(db: Session, user_id: str) -> dict[str, int]:
    obligations = db.query(Obligation).filter(Obligation.user_id == user_id).all()
    ob_ids = {o.id for o in obligations}
    edges_deleted = 0
    if ob_ids:
        edges_deleted = (
            db.query(PrerequisiteEdge)
            .filter(
                (PrerequisiteEdge.obligation_id.in_(ob_ids))
                | (PrerequisiteEdge.prerequisite_id.in_(ob_ids))
            )
            .delete(synchronize_session=False)
        )
    signals_deleted = (
        db.query(ProcessedSignal).filter(ProcessedSignal.user_id == user_id).delete()
    )
    docs_deleted = db.query(Document).filter(Document.user_id == user_id).delete()
    consents_deleted = db.query(ConsentLog).filter(ConsentLog.user_id == user_id).delete()
    vendors_deleted = db.query(VendorPattern).filter(VendorPattern.user_id == user_id).delete()
    history_deleted = (
        db.query(ObligationHistory).filter(ObligationHistory.user_id == user_id).delete()
    )
    ob_deleted = db.query(Obligation).filter(Obligation.user_id == user_id).delete()
    prefs_deleted = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).delete()
    db.commit()
    return {
        "obligations_deleted": ob_deleted,
        "edges_deleted": edges_deleted,
        "signals_deleted": signals_deleted,
        "documents_deleted": docs_deleted,
        "consent_log_deleted": consents_deleted,
        "vendor_patterns_deleted": vendors_deleted,
        "history_deleted": history_deleted,
        "preferences_deleted": prefs_deleted,
    }
