"""Plan, consent, pay and demo endpoints (handoff-v2 §5 API contract)."""

from __future__ import annotations

import asyncio
import base64
import io
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import segno
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import (
    calendar_feed,
    consent,
    data_export,
    events,
    insights,
    knowledge_pack,
    license as license_mod,
    network_log,
)
from app.clock import today as clock_today
from app.config import settings
from app.db.models import ConsentLog, Obligation
from app.db.seeds import seed_scenario
from app.db.session import engine, get_db
from app.graph.dag import blocking_subgraph, build_graph
from app.graph.scheduler import compute_start_by
from app.money.forecast import effective_date, forecast_daily, is_active
from app.planner import replan_and_check

router = APIRouter()
USER = settings.default_user_id


# ------------------------------------------------------------------ plan / timeline


def _priority(o: Obligation, today) -> float:
    eff = effective_date(o)
    slack = (eff - today).days if eff else 30
    p_miss = min(1.0, max(0.05, 1 - slack / 14))
    penalty = float((o.penalty or {}).get("amount") or 0) or float(o.amount or 0) * 0.1
    effort = max(1, (o.lead_time_days or 0) + 1)
    return round(p_miss * penalty / effort, 2)


def _why(o: Obligation, obs: dict[str, Obligation], sub, today) -> str:
    if o.status == "verified":
        return "Done: the bank's own SMS confirmed it"
    if o.status == "pause_requested":
        return "You chose to pause this in your UPI app"
    if o.obligation_type == "income":
        return "Expected money in; the plan counts on it"
    pres = [obs[p] for p in (sub.predecessors(o.id) if o.id in sub else []) if p in obs and is_active(obs[p])]
    if pres:
        return f"Needs {pres[0].title} first"
    deps = [obs[d] for d in (sub.successors(o.id) if o.id in sub else []) if d in obs and is_active(obs[d])]
    if deps:
        return f"Start this first: {deps[0].title} depends on it"
    if o.auto_pay_enabled:
        return "Auto-debit by mandate; the bank's pre-debit notice is in"
    if o.plan_locked:
        return "Scheduled by your voice approval"
    eff = effective_date(o)
    if eff and o.due_date and o.due_date < today:
        return f"Overdue since {o.due_date:%d %b}: do it as soon as you can"
    if eff and o.due_date and eff < o.due_date:
        return f"Planned {(o.due_date - eff).days} days before the {o.due_date:%d %b} deadline"
    return "On the plan"


def _bucket_key(o: Obligation, order: list) -> Any:
    eff = effective_date(o)
    keys = [k for k in order if eff and k <= eff]
    return keys[-1] if keys else "before_income"


def _money_buckets(obs: dict[str, Obligation], points, today) -> tuple[list, dict[Any, list[str]]]:
    """Group outgoing payments by the income event that funds them ('shares money')."""
    order = [today] + sorted({p.date for p in points if p.income > 0 and p.date > today})
    buckets: dict[Any, list[str]] = {}
    for o in obs.values():
        if not is_active(o) or o.obligation_type == "income" or not o.amount:
            continue
        buckets.setdefault(_bucket_key(o, order), []).append(o.id)
    return order, buckets


def _pause_hint(o: Obligation, today) -> str | None:
    """P4-lite: for a subscription with no recent debit, suggest pausing before the next charge."""
    if o.category != "subscription" or o.status in ("verified", "paid", "resolved", "paused"):
        return None
    sig = o.signal_debit or {}
    last_raw = sig.get("date")
    last: Any = None
    if last_raw:
        try:
            from datetime import date as _date
            last = _date.fromisoformat(last_raw[:10])
        except (TypeError, ValueError):
            last = None
    elif o.resolved_at:
        last = o.resolved_at.date()
    if last is None or (today - last).days >= 60:
        return "No recent activity — pause it in your UPI app before the next charge?"
    return None


def _card(o: Obligation, obs, sub, graph, order, buckets, today) -> dict[str, Any]:
    eff = effective_date(o)
    start_by = compute_start_by(graph, o.id) if o.id in graph and o.due_date else None
    shares: list[str] = []
    if o.obligation_type != "income" and o.amount and is_active(o):
        shares = [x for x in buckets.get(_bucket_key(o, order), []) if x != o.id][:4]
    penalty = o.penalty or {}
    preds = list(sub.predecessors(o.id)) if o.id in sub else []
    succs = list(sub.successors(o.id)) if o.id in sub else []
    return {
        "id": o.id,
        "title": o.title,
        "type": o.obligation_type,
        "category": o.category,
        "vendor": o.vendor,
        "due": o.due_date.isoformat() if o.due_date else None,
        "start_by": start_by.isoformat() if start_by else None,
        "planned_on": eff.isoformat() if eff else None,
        "plan_locked": bool(o.plan_locked),
        "amount_inr": float(o.amount) if o.amount is not None else None,
        "status": o.status,
        "verification_state": o.verification_state,
        "auto_pay": bool(o.auto_pay_enabled),
        "priority": _priority(o, today),
        "why": _why(o, obs, sub, today),
        "needs_first": [{"id": p, "title": obs[p].title, "status": obs[p].status} for p in preds if p in obs],
        "needed_by": [{"id": d, "title": obs[d].title} for d in succs if d in obs],
        "shares_money_with": [{"id": s, "title": obs[s].title} for s in shares if s in obs],
        "penalty": penalty.get("description") or penalty.get("type"),
        "sources": [
            {"channel": s.get("type"), "label": s.get("label") or s.get("type"), "ref": s.get("ref")}
            for s in (o.sources or [])
        ],
        "confidence": float(o.confidence or 0),
        "payee": o.payee,
        "pause_suggestion": _pause_hint(o, today),
    }


@router.get("/api/plan")
def plan_view(db: Session = Depends(get_db)) -> dict[str, Any]:
    today = clock_today()
    obs = {o.id: o for o in db.query(Obligation).filter(Obligation.user_id == USER).all()}
    graph = build_graph(db, USER)
    sub = blocking_subgraph(graph)
    points, prefs = forecast_daily(db, USER)
    order, buckets = _money_buckets(obs, points, today)
    groups: dict[str, list[dict[str, Any]]] = {
        "today": [], "week": [], "later": [], "needs_check": [], "verified": []
    }
    for o in obs.values():
        card = _card(o, obs, sub, graph, order, buckets, today)
        eff = effective_date(o)
        if o.status in ("verified", "paid", "resolved"):
            groups["verified"].append(card)
        elif float(o.confidence or 0) < 0.75 and o.status == "upcoming":
            groups["needs_check"].append(card)
        elif o.status in ("pause_requested", "paused", "dismissed"):
            groups["later"].append(card)
        elif eff is None or eff > today + timedelta(days=7):
            groups["later"].append(card)
        elif eff <= today:
            groups["today"].append(card)
        else:
            groups["week"].append(card)
    groups["today"].sort(key=lambda c: -c["priority"])
    for k in ("week", "later", "needs_check", "verified"):
        groups[k].sort(key=lambda c: c["planned_on"] or "9999")
    proposal = consent.current_proposal(USER)
    return {
        "as_of": today.isoformat(),
        **groups,
        "money": {
            "balance_today": float(prefs.starting_balance_inr),
            "floor": float(prefs.hard_floor_inr),
            "cushion_top": float(prefs.hard_floor_inr) + float(prefs.soft_cushion_inr),
            "min_balance": min(p.closing_balance for p in points) if points else None,
        },
        "proposal": proposal.payload() if proposal and proposal.status == "open" else None,
    }


@router.post("/api/replan")
def replan(db: Session = Depends(get_db)) -> dict[str, object]:
    return replan_and_check(db, USER)


@router.post("/api/obligations/{obligation_id}/confirm")
def confirm_obligation(obligation_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    o = db.get(Obligation, obligation_id)
    if o is None or o.user_id != USER:
        raise HTTPException(404, "Not found")
    o.confidence = max(float(o.confidence or 0), 0.95)
    db.commit()
    events.publish("plan_changed", {"source": "confirm", "obligation_id": obligation_id})
    return {"obligation_id": obligation_id, "confidence": float(o.confidence)}


# ------------------------------------------------------------------ events (SSE)


@router.get("/api/events")
async def event_stream(request: Request) -> StreamingResponse:
    last_id = int(request.headers.get("last-event-id") or 0)

    async def gen():
        sub = events.subscribe()
        try:
            for msg in events.recent(last_id):
                yield events.format_sse(msg)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(sub[1].get(), timeout=15)
                    yield events.format_sse(msg)
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            events.unsubscribe(sub)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/events/recent")
def events_recent(since: int = Query(default=0, ge=0)) -> list[dict[str, Any]]:
    """Polling fallback for UIs that can't hold an SSE connection."""
    return events.recent(since)


# ------------------------------------------------------------------ consent / voice


class VoiceTurn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    proposal_id: str | None = None


@router.get("/api/proposal/current")
def proposal_current() -> dict[str, Any] | None:
    p = consent.current_proposal(USER)
    return p.payload() if p else None


@router.post("/api/voice/turn")
def voice_turn(payload: VoiceTurn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return consent.handle_turn(db, USER, payload.text, payload.proposal_id)


@router.post("/api/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)) -> dict[str, Any]:
    """Push-to-talk STT endpoint. Accepts a browser MediaRecorder blob
    (webm/opus by default), returns the transcribed text.

    Runs faster-whisper `base.en` locally on CPU — no audio ever leaves the box.
    """
    from app.voice_stt import transcribe as stt_transcribe

    data = await audio.read()
    if len(data) < 1024:
        return {"ok": False, "text": "", "reason": "empty"}
    try:
        text = stt_transcribe(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"stt failed: {e}") from e
    return {"ok": True, "text": text, "bytes": len(data)}


class EraseRequest(BaseModel):
    confirm: str = Field(..., description="Must equal 'YES-DELETE-EVERYTHING' to proceed.")


@router.get("/api/user/export")
def user_export(db: Session = Depends(get_db)) -> Response:
    """Download every row Chaufferone stores about this user (§7.4 data portability)."""
    import json as _json

    payload = data_export.export_all(db, USER)
    body = _json.dumps(payload, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="chaufferone-export.json"'},
    )


@router.post("/api/user/delete-all")
def user_delete_all(req: EraseRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Erase everything for this user. Irreversible. Requires confirm='YES-DELETE-EVERYTHING'."""
    if req.confirm != data_export.ERASE_CONFIRM:
        raise HTTPException(400, f"confirm must equal '{data_export.ERASE_CONFIRM}'")
    consent.clear_proposal(USER)
    events.clear()
    counts = data_export.erase_all(db, USER)
    events.publish("erased", {"user_id": USER, **counts})
    return {"ok": True, **counts}


@router.get("/api/knowledge/status")
def knowledge_status() -> dict[str, Any]:
    """Which knowledge packs are installed, and their versions (§7.6 update stream)."""
    return {"packs": knowledge_pack.status()}


@router.get("/api/license/status")
def license_status() -> dict[str, Any]:
    """Signed Ed25519 license state (§7.5). No phone-home; verified offline."""
    return license_mod.status()


@router.get("/api/insights")
def insights_view(
    window_days: int = Query(default=60, ge=7, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Spending rollup + dead-subscription hints (P6)."""
    return insights.summarize(db, USER, window_days=window_days)


@router.get("/api/network/log")
def network_log_view(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Every outbound connection this engine has made. Checkable-privacy screen (§7.2)."""
    rows = network_log.recent(db, limit=limit)
    hosts = sorted({r["host"] for r in rows})
    return {"count": len(rows), "hosts": hosts, "rows": rows}


@router.get("/api/calendar.ics")
def calendar_ics(db: Session = Depends(get_db)) -> Response:
    """Subscribe from Google/Apple/Outlook Calendar; each obligation shows up on its start-by day."""
    body = calendar_feed.render_ics(db, USER)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="chaufferone.ics"'},
    )


@router.get("/api/consent-log")
def consent_log(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        db.query(ConsentLog)
        .filter(ConsentLog.user_id == USER)
        .order_by(ConsentLog.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "at": r.created_at.isoformat() if r.created_at else None,
            "proposal_id": r.proposal_id,
            "spoken_proposal": r.spoken_proposal,
            "utterance": r.utterance,
            "intent": r.intent,
            "parsed_by": r.parsed_by,
            "applied_moves": r.applied_moves,
            "reply": r.reply,
        }
        for r in rows
    ]


# ------------------------------------------------------------------ pay (UPI P2P QR)


@router.get("/api/pay/{obligation_id}")
def pay(obligation_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    o = db.get(Obligation, obligation_id)
    if o is None or o.user_id != USER:
        raise HTTPException(404, "Not found")
    if not o.amount or float(o.amount) <= 0 or o.obligation_type == "income":
        raise HTTPException(400, "Nothing to pay for this obligation")
    vpa = o.payee if o.payee and "@" in o.payee else settings.upi_payee_vpa
    if not vpa:
        raise HTTPException(400, "No payee VPA. Set UPI_PAYEE_VPA in .env or the obligation's payee.")
    name = o.vendor or settings.upi_payee_name
    uri = (
        f"upi://pay?pa={quote(vpa, safe='@.')}&pn={quote(name)}&am={float(o.amount):.2f}"
        f"&cu=INR&tn={quote(o.title[:40])}"
    )
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="png", scale=8, border=2)
    o.verification_state = "pay_link_shown"
    if o.status == "upcoming":
        o.status = "approved"
    db.commit()
    events.publish("pay_requested", {"obligation_id": o.id, "title": o.title, "amount": float(o.amount)})
    masked = vpa[:2] + "***" + vpa[vpa.index("@"):] if "@" in vpa else vpa
    return {
        "obligation_id": o.id,
        "title": o.title,
        "amount_inr": float(o.amount),
        "payee_masked": masked,
        "upi_uri": uri,
        "qr_png_b64": base64.b64encode(buf.getvalue()).decode(),
        "note": "Scan with any UPI app and approve with your UPI PIN. We never touch your money.",
    }


# ------------------------------------------------------------------ demo controls


def _db_path() -> Path:
    path = engine.url.database
    if not path:
        raise HTTPException(500, "Demo snapshot needs a file-backed SQLite database")
    return Path(path)


def _sqlite_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    s, d = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        s.close()
        d.close()


@router.post("/api/demo/scenario")
def demo_scenario(db: Session = Depends(get_db)) -> dict[str, object]:
    """Load the handoff-v2 §6 scenario (wipes this user's obligations)."""
    consent.clear_proposal(USER)
    events.clear()
    out = seed_scenario(db, USER)
    out["check"] = replan_and_check(db, USER)
    return out


@router.post("/api/demo/snapshot")
def demo_snapshot() -> dict[str, str]:
    """Freeze the current DB (after imports) as the demo starting point."""
    src, dst = _db_path(), Path(settings.demo_snapshot_path)
    _sqlite_copy(src, dst)
    return {"snapshot": str(dst)}


@router.post("/api/demo/reset")
def demo_reset(db: Session = Depends(get_db)) -> dict[str, object]:
    """Restore the snapshot if one exists, else reload the scenario. Clears open proposals."""
    consent.clear_proposal(USER)
    events.clear()
    snap = Path(settings.demo_snapshot_path)
    if snap.exists():
        db.close()
        engine.dispose()
        _sqlite_copy(snap, _db_path())
        return {"restored": str(snap)}
    out = seed_scenario(db, USER)
    out["check"] = replan_and_check(db, USER)
    return {"reseeded": out}


class InjectSms(BaseModel):
    model_config = {"populate_by_name": True}

    text: str = Field(min_length=1)
    sender: str = Field(default="AX-DEMOBK-S", alias="from")


@router.post("/api/demo/inject/sms")
def demo_inject_sms(payload: InjectSms, db: Session = Depends(get_db)) -> dict[str, object]:
    """Replay button: the same code path as a forwarded SMS."""
    from app.api.ingest_routes import ingest_sms_payload

    return ingest_sms_payload(db, {"from": payload.sender, "text": payload.text})


@router.get("/api/demo/sample-sms")
def demo_sample_sms(db: Session = Depends(get_db)) -> dict[str, str]:
    """Bank-format texts for the live demo, dated relative to the engine clock."""
    today = clock_today()
    debit_on = today + timedelta(days=6)
    gift = next(
        (o for o in db.query(Obligation).filter(Obligation.user_id == USER).all() if o.category == "social"),
        None,
    )
    amount = float(gift.amount) if gift and gift.amount else 500.0
    vpa = (gift.payee if gift and gift.payee else settings.upi_payee_vpa) or "demo.teammate@okaxis"
    return {
        "pre_debit": (
            f"Dear Customer, Rs.1499.00 will be debited from your HDFC Bank A/c XX1234 on "
            f"{debit_on:%d-%m-%Y} towards StreamMax for UPI AutoPay mandate. "
            f"To manage, visit the UPI app. -HDFC Bank"
        ),
        "debit": (
            f"Rs.{amount:.2f} debited from A/c **1234 on {today:%d-%m-%y} to VPA {vpa} "
            f"(UPI Ref No 627312345678). Not you? Call 18002586161 - HDFC Bank"
        ),
    }
