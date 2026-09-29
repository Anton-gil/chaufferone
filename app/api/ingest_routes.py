"""Ingest adapters: SMS forwarder, SMS Backup XML, WhatsApp export, .eml upload.

Every endpoint returns the same stats shape
    {"scanned", "created", "merged", "skipped", "signals", "rejected", "errors", "results": [...]}
plus whatever app.hooks.after_ingest() returns (called once per batch, only if at
least one message reached the pipeline). Invariant:
    scanned == created + merged + skipped + signals + rejected + errors
A failing message (e.g. no LLM key) is counted in "errors"; the batch never 500s.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import clock
from app.config import settings
from app.db.session import get_db
from app.extract.pipeline import process_message
from app.hooks import after_ingest
from app.ingest import eml, sms, sms_backup, whatsapp

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


# --- shared helpers ------------------------------------------------------------


def _new_stats() -> dict[str, Any]:
    return {
        "scanned": 0,
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "signals": 0,
        "rejected": 0,
        "errors": 0,
        "results": [],
    }


def _preview(text: str, n: int = 80) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= n else flat[: n - 1] + "…"


def _pipeline_accepts_sender() -> bool:
    """The `sender` kwarg is being added to process_message; don't break if it isn't there yet."""
    try:
        params = inspect.signature(process_message).parameters
    except (TypeError, ValueError):
        return True
    return "sender" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def _safe_rollback(db: Any) -> None:
    rollback = getattr(db, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception:  # pragma: no cover - best effort
            log.exception("rollback failed")


def _run_pipeline(
    db: Any,
    stats: dict[str, Any],
    meta: dict[str, Any],
    *,
    source_type: str,
    source_ref: str,
    body: str,
    subject: str | None = None,
    received_at=None,
    sender: str | None = None,
) -> None:
    kwargs: dict[str, Any] = {
        "user_id": settings.default_user_id,
        "source_type": source_type,
        "source_ref": source_ref,
        "body": body,
        "subject": subject,
        "received_at": received_at,
    }
    if sender is not None and _pipeline_accepts_sender():
        kwargs["sender"] = sender
    try:
        res = process_message(db, **kwargs)
    except Exception as e:
        _safe_rollback(db)
        log.warning("ingest %s %s failed: %s: %s", source_type, source_ref[:12], type(e).__name__, e)
        stats["errors"] += 1
        stats["results"].append({**meta, "status": "error", "error": f"{type(e).__name__}: {e}"[:300]})
        return

    reason = str(res.reason)
    if reason.startswith("signal:"):
        stats["signals"] += 1
    elif res.was_new:
        stats["created"] += 1
    elif reason == "merged_duplicate":
        stats["merged"] += 1
    else:
        stats["skipped"] += 1
    try:
        confidence = round(float(res.confidence or 0), 3)
    except (TypeError, ValueError):
        confidence = None
    stats["results"].append(
        {**meta, "status": reason, "obligation_id": res.obligation_id, "confidence": confidence}
    )


def _finish(db: Any, stats: dict[str, Any], attempted: int) -> dict[str, Any]:
    if not attempted:
        return stats
    try:
        extra = after_ingest(db, settings.default_user_id) or {}
    except Exception as e:
        _safe_rollback(db)
        log.exception("after_ingest failed")
        stats["after_ingest_error"] = f"{type(e).__name__}: {e}"[:300]
        return stats
    for k, v in extra.items():
        stats[k if k not in stats else f"hook_{k}"] = v
    return stats


# --- 1. SMS forwarder / demo injector ----------------------------------------------


def _salvage_forwarder_json(text: str) -> dict[str, Any] | None:
    """Last resort for a template that didn't JSON-escape quotes inside %text%."""
    m_from = re.search(r'"from"\s*:\s*"([^"]*)"', text)
    m_text = re.search(
        r'"text"\s*:\s*"(.*?)"\s*,\s*"(?:sentStamp|receivedStamp|sim)"\s*:', text, re.S
    ) or re.search(r'"text"\s*:\s*"(.*)"\s*\}\s*$', text, re.S)
    if not (m_from and m_text):
        return None
    out: dict[str, Any] = {
        "from": m_from.group(1),
        "text": m_text.group(1).replace('\\"', '"').replace("\\n", "\n"),
    }
    for key in ("sentStamp", "receivedStamp"):
        m = re.search(rf'"{key}"\s*:\s*"?(\d+)', text)
        if m:
            out[key] = m.group(1)
    return out


def parse_sms_request_body(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise HTTPException(400, 'empty body; expected JSON like {"from": "...", "text": "..."}')
    for strict in (True, False):  # strict=False tolerates raw newlines inside the SMS text
        try:
            data = json.loads(text, strict=strict)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
        raise HTTPException(422, "expected a JSON object")
    if not text.startswith("{") and "=" in text:  # form-encoded fallback
        qs = parse_qs(text, keep_blank_values=True)
        if qs:
            return {k: v[-1] for k, v in qs.items()}
    salvaged = _salvage_forwarder_json(text)
    if salvaged:
        return salvaged
    raise HTTPException(400, 'body must be JSON like {"from": "AX-HDFCBK-S", "text": "..."}')


def ingest_sms_payload(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Single-SMS path shared by the forwarder app and the demo injector."""
    msg = sms.parse_forwarder_payload(payload)
    ok, reason = sms.check_sender(msg.sender)
    stats = _new_stats()
    stats["scanned"] = 1
    stats["accepted"] = ok and bool(msg.text)
    stats["sender_reason"] = reason
    meta = {
        "sender": msg.sender,
        "date": msg.received_at.isoformat(),
        "ref": msg.source_ref[:12],
        "preview": _preview(msg.text),
    }
    if not stats["accepted"]:
        stats["rejected"] = 1
        stats["results"].append({**meta, "status": "rejected", "reason": reason if not ok else "empty_text"})
        return stats
    _run_pipeline(
        db,
        stats,
        meta,
        source_type="sms",
        source_ref=msg.source_ref,
        body=msg.text,
        received_at=msg.received_at,
        sender=msg.sender,
    )
    return _finish(db, stats, attempted=1)


_SMS_OPENAPI: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "from": {"type": "string"},
                        "text": {"type": "string"},
                        "sentStamp": {"type": ["string", "integer"], "description": "epoch millis"},
                        "receivedStamp": {"type": ["string", "integer"], "description": "epoch millis"},
                        "sim": {"type": "string"},
                    },
                    "required": ["from", "text"],
                    "additionalProperties": True,
                },
                "example": {
                    "from": "AX-HDFCBK-S",
                    "text": "Rs.1499 will be debited from a/c XX1234 on 06-Oct-26 towards StreamMax mandate.",
                    "sentStamp": "1790658000000",
                    "receivedStamp": "1790658001000",
                    "sim": "SIM1",
                },
            }
        },
    }
}


@router.post("/sms", openapi_extra=_SMS_OPENAPI)
async def ingest_sms(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Android "SMS to URL Forwarder" webhook (default JSON template) and demo injector."""
    payload = parse_sms_request_body(await request.body())
    return await run_in_threadpool(ingest_sms_payload, db, payload)


# --- 2. SMS Backup & Restore XML -------------------------------------------------


@router.post("/sms-backup")
def ingest_sms_backup(
    file: UploadFile = File(..., description="SMS Backup & Restore .xml export"),
    days: int = Query(default=60, ge=1, le=3650),
    limit: int = Query(default=300, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    parsed = sms_backup.parse_sms_backup(file.file, days=days, limit=limit, today=clock.today())
    if parsed.scanned == 0 and parsed.parse_error:
        raise HTTPException(400, parsed.parse_error)
    stats = _new_stats()
    stats["scanned"] = parsed.scanned
    stats["rejected"] = sum(parsed.filtered.values())
    stats["filtered"] = parsed.filtered
    if parsed.parse_error:
        stats["parse_error"] = parsed.parse_error
    for m in parsed.messages:
        meta = {
            "sender": m.sender,
            "date": m.received_at.isoformat(),
            "ref": m.source_ref[:12],
            "preview": _preview(m.text),
        }
        _run_pipeline(
            db,
            stats,
            meta,
            source_type="sms",
            source_ref=m.source_ref,
            body=m.text,
            received_at=m.received_at,
            sender=m.sender,
        )
    return _finish(db, stats, attempted=len(parsed.messages))


# --- 3. WhatsApp chat export --------------------------------------------------------


@router.post("/whatsapp")
def ingest_whatsapp(
    file: UploadFile = File(..., description="WhatsApp 'Export chat (without media)' .txt or .zip"),
    days: int = Query(default=60, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        text = whatsapp.read_export(file.file.read(), file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    messages = whatsapp.parse_whatsapp(text)
    selected, filtered = whatsapp.select_messages(messages, days=days, today=clock.today())
    stats = _new_stats()
    stats["scanned"] = len(messages)
    stats["rejected"] = sum(filtered.values())
    stats["filtered"] = filtered
    if not messages and text.strip():
        stats["warning"] = "no chat messages recognised; is this a WhatsApp export .txt?"
    for m in selected:
        meta = {
            "author": m.author,
            "date": m.timestamp.date().isoformat(),
            "ref": m.source_ref[:12],
            "preview": _preview(m.text),
        }
        _run_pipeline(
            db,
            stats,
            meta,
            source_type="whatsapp",
            source_ref=m.source_ref,
            body=m.pipeline_body,
            received_at=m.timestamp.date(),
        )
    return _finish(db, stats, attempted=len(selected))


# --- 4. .eml upload -------------------------------------------------------------------


@router.post("/eml")
def ingest_eml(
    files: list[UploadFile] = File(..., description="One or more .eml files"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stats = _new_stats()
    attempted = 0
    for f in files:
        stats["scanned"] += 1
        try:
            m = eml.parse_eml(f.file.read())
        except Exception as e:
            stats["errors"] += 1
            stats["results"].append(
                {"file": f.filename, "status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
            )
            continue
        meta = {
            "file": f.filename,
            "subject": m.subject,
            "from": m.sender,
            "date": m.received_at.isoformat() if m.received_at else None,
            "ref": m.source_ref[:40],
        }
        if not (m.body or m.subject):
            stats["rejected"] += 1
            stats["results"].append({**meta, "status": "rejected", "reason": "empty_message"})
            continue
        attempted += 1
        body = f"From: {m.sender}\n\n{m.body}" if m.sender else m.body
        _run_pipeline(
            db,
            stats,
            meta,
            source_type="email",
            source_ref=m.source_ref,
            body=body,
            subject=m.subject or None,
            received_at=m.received_at or clock.today(),
        )
    return _finish(db, stats, attempted=attempted)
