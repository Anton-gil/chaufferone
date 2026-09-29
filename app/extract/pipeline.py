"""Orchestrator: raw message -> obligation row."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import Obligation, ProcessedSignal
from app.extract import llm, regex_rules
from app.extract.dedup import find_duplicate, normalize_vendor
from app.schemas.obligation import ExtractedObligation


@dataclass
class ProcessResult:
    obligation_id: str | None
    was_new: bool
    reason: str
    confidence: float


def _already_seen(db: Session, user_id: str, source_type: str, source_ref: str) -> bool:
    return (
        db.query(ProcessedSignal)
        .filter_by(user_id=user_id, source_type=source_type, source_ref=source_ref)
        .first()
        is not None
    )


def _record_signal(db, user_id, source_type, source_ref, obligation_id, snippet):
    db.add(
        ProcessedSignal(
            user_id=user_id,
            source_type=source_type,
            source_ref=source_ref,
            obligation_id=obligation_id,
            raw_snippet=snippet[:500],
        )
    )


def _merge_source(existing: Obligation, source_type: str, source_ref: str) -> None:
    existing.sources = (existing.sources or []) + [{"type": source_type, "ref": source_ref}]


def _urgency_to_tier(u: str | None) -> str:
    return {"low": "green", "medium": "green", "high": "amber", "critical": "red"}.get(u or "", "green")


def _persist_new(db, user_id, extracted: ExtractedObligation, source_type, source_ref):
    ob = Obligation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=extracted.title,
        vendor=extracted.vendor,
        vendor_normalized=normalize_vendor(extracted.vendor),
        category=extracted.category,
        obligation_type=extracted.obligation_type,
        amount=extracted.amount,
        currency=extracted.currency,
        due_date=extracted.due_date,
        lead_time_days=extracted.lead_time_days,
        flexibility_window=extracted.flexibility_window_days,
        penalty={
            "type": extracted.penalty_type,
            "amount": extracted.penalty_amount,
            "description": extracted.penalty_description,
        },
        resources={"inr": extracted.amount} if extracted.amount else {},
        auto_pay_enabled=bool(extracted.auto_pay),
        confidence=extracted.confidence,
        urgency_tier=_urgency_to_tier(extracted.urgency),
        sources=[{"type": source_type, "ref": source_ref}],
        signal_extracted={"source": source_type, "ref": source_ref, "action_required": extracted.action_required},
    )
    db.add(ob)
    return ob


def process_message(
    db: Session,
    *,
    user_id: str,
    source_type: str,
    source_ref: str,
    body: str,
    subject: str | None = None,
    received_at: date | None = None,
) -> ProcessResult:
    if _already_seen(db, user_id, source_type, source_ref):
        return ProcessResult(None, False, "already_processed", 0.0)

    full_text = f"{subject}\n\n{body}" if subject else body

    fast = regex_rules.try_fast_extract(full_text)
    if fast and fast.get("signal_type"):
        _record_signal(db, user_id, source_type, source_ref, None, full_text)
        db.commit()
        return ProcessResult(None, False, f"signal:{fast['signal_type']}", fast.get("confidence", 0))

    triage = llm.triage(full_text)
    if not triage.is_obligation or triage.confidence < 0.5:
        _record_signal(db, user_id, source_type, source_ref, None, full_text)
        db.commit()
        return ProcessResult(None, False, "not_an_obligation", triage.confidence)

    extracted = llm.extract(full_text, category_hint=triage.category_hint)
    if not extracted:
        _record_signal(db, user_id, source_type, source_ref, None, full_text)
        db.commit()
        return ProcessResult(None, False, "extraction_failed", 0.0)

    dup = find_duplicate(db, user_id, extracted.vendor, extracted.amount, extracted.due_date)
    if dup:
        _merge_source(dup, source_type, source_ref)
        dup.confidence = max(float(dup.confidence or 0), extracted.confidence)
        _record_signal(db, user_id, source_type, source_ref, dup.id, full_text)
        db.commit()
        return ProcessResult(dup.id, False, "merged_duplicate", extracted.confidence)

    ob = _persist_new(db, user_id, extracted, source_type, source_ref)
    _record_signal(db, user_id, source_type, source_ref, ob.id, full_text)
    db.commit()
    return ProcessResult(ob.id, True, "created", extracted.confidence)
