"""FastAPI routes."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Obligation, PrerequisiteEdge, UserPreferences
from app.db.seeds import seed_demo_obligations, seed_demo_preferences
from app.db.session import get_db
from app.extract.pipeline import process_message
from app.graph.cascade import simulate_miss
from app.graph.dag import build_graph
from app.graph.linker import auto_link_prerequisites
from app.graph.risk import compute_risk
from app.graph.scheduler import compute_start_by, schedule_all
from app.ingest.gmail import list_and_fetch, load_credentials, make_flow, save_credentials
from app.money.clash import detect_clashes
from app.money.fixes import propose_fixes
from app.money.forecast import forecast_daily
from app.schemas.money import Clash, DayPoint, Fix, ForecastResponse
from app.schemas.obligation import ObligationOut

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "chaufferone"}


# --- Auth ---


@router.get("/api/auth/google/start")
def google_start() -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(500, "GOOGLE_CLIENT_ID not configured")
    flow = make_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/api/auth/google/callback")
def google_callback(request: Request) -> dict[str, str]:
    flow = make_flow()
    flow.fetch_token(authorization_response=str(request.url))
    save_credentials(flow.credentials)
    return {"status": "authorized", "next": "/api/ingest/gmail/run"}


# --- Ingest ---


@router.post("/api/ingest/gmail/run")
def ingest_gmail(
    days: int = Query(default=90, ge=1, le=365),
    max_results: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    creds = load_credentials()
    if not creds:
        raise HTTPException(401, "Not authorized. Visit /api/auth/google/start first.")

    messages = list_and_fetch(creds, days=days, max_results=max_results)
    stats = {"scanned": len(messages), "created": 0, "merged": 0, "skipped": 0, "signals": 0}
    user_id = settings.default_user_id

    for m in messages:
        result = process_message(
            db,
            user_id=user_id,
            source_type="gmail",
            source_ref=m.id,
            body=m.body_text,
            subject=m.subject,
            received_at=m.received_at.date(),
        )
        if result.reason.startswith("signal:"):
            stats["signals"] += 1
        elif result.was_new:
            stats["created"] += 1
        elif result.reason == "merged_duplicate":
            stats["merged"] += 1
        else:
            stats["skipped"] += 1

    linked = auto_link_prerequisites(db, user_id)
    stats["edges_linked"] = linked
    return stats


# --- Timeline / detail ---


@router.get("/api/timeline")
def timeline(db: Session = Depends(get_db)) -> list[ObligationOut]:
    rows = (
        db.query(Obligation)
        .filter(Obligation.user_id == settings.default_user_id)
        .order_by(Obligation.due_date.asc().nullslast(), Obligation.created_at.desc())
        .limit(200)
        .all()
    )
    return [ObligationOut.model_validate(r) for r in rows]


@router.get("/api/obligation/{obligation_id}")
def obligation_detail(obligation_id: str, db: Session = Depends(get_db)) -> ObligationOut:
    row = (
        db.query(Obligation)
        .filter(Obligation.id == obligation_id, Obligation.user_id == settings.default_user_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Not found")
    return ObligationOut.model_validate(row)


class ObligationCreate(BaseModel):
    title: str
    vendor: str | None = None
    category: str | None = None
    obligation_type: str = "payment"
    amount: float | None = None
    currency: str = "INR"
    due_date: date | None = None
    lead_time_days: int = 1
    flexibility_window_days: int = 0
    penalty_type: str | None = None
    penalty_amount: float | None = None
    penalty_description: str | None = None


@router.post("/api/obligation", status_code=201)
def obligation_create(payload: ObligationCreate, db: Session = Depends(get_db)) -> ObligationOut:
    ob = Obligation(
        id=str(uuid.uuid4()),
        user_id=settings.default_user_id,
        title=payload.title,
        vendor=payload.vendor,
        vendor_normalized=(payload.vendor or "").lower().strip() or None,
        category=payload.category,
        obligation_type=payload.obligation_type,
        amount=payload.amount,
        currency=payload.currency,
        due_date=payload.due_date,
        lead_time_days=payload.lead_time_days,
        flexibility_window=payload.flexibility_window_days,
        penalty={
            "type": payload.penalty_type,
            "amount": payload.penalty_amount,
            "description": payload.penalty_description,
        },
        resources={"inr": payload.amount} if payload.amount else {},
        confidence=1.0,
        sources=[{"type": "manual", "ref": "api"}],
        urgency_tier="green",
    )
    db.add(ob)
    db.commit()
    auto_link_prerequisites(db, settings.default_user_id)
    return ObligationOut.model_validate(ob)


# --- Graph (NEXUS) ---


def _node_payload(g: nx.DiGraph, nid: str) -> dict[str, object]:
    n = g.nodes[nid]["data"]
    return {
        "id": n.id,
        "title": n.title,
        "category": n.category,
        "due_date": n.due_date.isoformat() if n.due_date else None,
        "lead_time_days": n.lead_time_days,
        "amount": n.amount,
        "penalty_amount": n.penalty_amount,
        "urgency_tier": n.urgency_tier,
        "risk_score": n.risk_score,
        "status": n.status,
        "verification_state": n.verification_state,
    }


@router.get("/api/graph")
def graph_view(db: Session = Depends(get_db)) -> dict[str, object]:
    g = build_graph(db, settings.default_user_id)
    nodes = [_node_payload(g, n) for n in g.nodes]
    edges = [
        {
            "from": u,
            "to": v,
            "kind": d.get("kind", "needs_first"),
            "lead_time_days": d.get("lead_time_days", 0),
            "is_blocking": d.get("is_blocking", True),
            "legal_basis": d.get("legal_basis"),
            "confidence": d.get("confidence"),
        }
        for u, v, d in g.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges, "count": {"nodes": len(nodes), "edges": len(edges)}}


@router.post("/api/graph/link")
def graph_link(db: Session = Depends(get_db)) -> dict[str, int]:
    added = auto_link_prerequisites(db, settings.default_user_id)
    return {"edges_added": added}


@router.get("/api/graph/schedule")
def graph_schedule(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    g = build_graph(db, settings.default_user_id)
    schedule = schedule_all(g)
    out = []
    for nid, start_by in schedule.items():
        n = g.nodes[nid]["data"]
        out.append(
            {
                "obligation_id": nid,
                "title": n.title,
                "due_date": n.due_date.isoformat() if n.due_date else None,
                "start_by": start_by.isoformat() if start_by else None,
                "lead_time_days": n.lead_time_days,
            }
        )
    out.sort(key=lambda r: r["start_by"] or "9999")
    return out


@router.get("/api/graph/cascade/{obligation_id}")
def graph_cascade(obligation_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    g = build_graph(db, settings.default_user_id)
    if obligation_id not in g:
        raise HTTPException(404, "Not found")
    result = simulate_miss(g, obligation_id)
    return {
        "root_id": result.root_id,
        "total_exposure_inr": result.total_exposure_inr,
        "step_count": result.step_count,
        "steps": [asdict(s) for s in result.steps],
    }


@router.get("/api/graph/risk/{obligation_id}")
def graph_risk(obligation_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    g = build_graph(db, settings.default_user_id)
    if obligation_id not in g:
        raise HTTPException(404, "Not found")
    cascade = simulate_miss(g, obligation_id)
    breakdown = compute_risk(g, obligation_id, cascade_exposure_inr=cascade.total_exposure_inr)
    return {
        "obligation_id": breakdown.obligation_id,
        "score": breakdown.score,
        "tier": breakdown.tier,
        "components": {
            "time_urgency": breakdown.time_urgency,
            "penalty_severity": breakdown.penalty_severity,
            "prerequisite_risk": breakdown.prerequisite_risk,
            "cash_flow_risk": breakdown.cash_flow_risk,
            "historical_miss": breakdown.historical_miss,
        },
        "cascade_exposure_inr": breakdown.cascade_exposure_inr,
        "start_by": breakdown.start_by.isoformat() if breakdown.start_by else None,
    }


@router.get("/api/graph/start-by/{obligation_id}")
def graph_start_by(obligation_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    g = build_graph(db, settings.default_user_id)
    if obligation_id not in g:
        raise HTTPException(404, "Not found")
    start_by = compute_start_by(g, obligation_id)
    n = g.nodes[obligation_id]["data"]
    return {
        "obligation_id": obligation_id,
        "due_date": n.due_date.isoformat() if n.due_date else None,
        "start_by": start_by.isoformat() if start_by else None,
        "lead_time_days": n.lead_time_days,
    }


# --- Money Engine (ORACLE) ---


class PreferencesUpdate(BaseModel):
    hard_floor_inr: float | None = None
    soft_cushion_inr: float | None = None
    starting_balance_inr: float | None = None
    estimated_monthly_income_inr: float | None = None
    salary_day_of_month: int | None = None
    admin_day_offset: int | None = None
    aggressiveness: str | None = None
    voice_enabled: bool | None = None


class PreferencesOut(BaseModel):
    user_id: str
    hard_floor_inr: float
    soft_cushion_inr: float
    starting_balance_inr: float
    estimated_monthly_income_inr: float
    salary_day_of_month: int | None
    admin_day_offset: int
    aggressiveness: str
    voice_enabled: bool


def _prefs_or_create(db: Session, user_id: str) -> UserPreferences:
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
    return prefs


def _prefs_to_dict(p: UserPreferences) -> PreferencesOut:
    return PreferencesOut(
        user_id=p.user_id,
        hard_floor_inr=float(p.hard_floor_inr),
        soft_cushion_inr=float(p.soft_cushion_inr),
        starting_balance_inr=float(p.starting_balance_inr),
        estimated_monthly_income_inr=float(p.estimated_monthly_income_inr),
        salary_day_of_month=p.salary_day_of_month,
        admin_day_offset=p.admin_day_offset,
        aggressiveness=p.aggressiveness,
        voice_enabled=p.voice_enabled,
    )


@router.get("/api/preferences")
def preferences_get(db: Session = Depends(get_db)) -> PreferencesOut:
    return _prefs_to_dict(_prefs_or_create(db, settings.default_user_id))


@router.put("/api/preferences")
def preferences_put(payload: PreferencesUpdate, db: Session = Depends(get_db)) -> PreferencesOut:
    prefs = _prefs_or_create(db, settings.default_user_id)
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(prefs, field, val)
    db.commit()
    return _prefs_to_dict(prefs)


@router.get("/api/money/forecast")
def money_forecast(
    days: int = Query(default=45, ge=7, le=180),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    points, prefs = forecast_daily(db, settings.default_user_id, horizon_days=days)
    clashes = detect_clashes(points)
    return ForecastResponse(
        horizon_days=days,
        starting_balance_inr=float(prefs.starting_balance_inr),
        hard_floor_inr=float(prefs.hard_floor_inr),
        soft_cushion_inr=float(prefs.soft_cushion_inr),
        days=points,
        clashes=clashes,
    )


@router.get("/api/money/clashes")
def money_clashes(
    days: int = Query(default=45, ge=7, le=180),
    db: Session = Depends(get_db),
) -> list[Clash]:
    points, _ = forecast_daily(db, settings.default_user_id, horizon_days=days)
    return detect_clashes(points)


@router.get("/api/money/fixes/{clash_id}")
def money_fixes(
    clash_id: str,
    days: int = Query(default=45, ge=7, le=180),
    db: Session = Depends(get_db),
) -> list[Fix]:
    points, _ = forecast_daily(db, settings.default_user_id, horizon_days=days)
    clashes = detect_clashes(points)
    target = next((c for c in clashes if c.id == clash_id), None)
    if not target:
        raise HTTPException(404, f"clash {clash_id} not found")
    return propose_fixes(db, settings.default_user_id, target, horizon_days=days)


# --- Demo ---


@router.post("/api/demo/seed")
def demo_seed(db: Session = Depends(get_db)) -> dict[str, object]:
    added = seed_demo_obligations(db, settings.default_user_id)
    edges = auto_link_prerequisites(db, settings.default_user_id)
    prefs_seeded = seed_demo_preferences(db, settings.default_user_id)
    return {"obligations_added": added, "edges_added": edges, "preferences_seeded": prefs_seeded}


@router.post("/api/demo/clear")
def demo_clear(db: Session = Depends(get_db)) -> dict[str, int]:
    ob_deleted = db.query(Obligation).filter(Obligation.user_id == settings.default_user_id).delete()
    edge_deleted = db.query(PrerequisiteEdge).delete()
    db.commit()
    return {"obligations_deleted": ob_deleted, "edges_deleted": edge_deleted}
