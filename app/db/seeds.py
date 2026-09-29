"""Seed data: dependency template knowledge pack + demo obligations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.clock import today as clock_today
from app.config import settings
from app.db.models import (
    ConsentLog,
    DependencyTemplate,
    Obligation,
    PrerequisiteEdge,
    ProcessedSignal,
    UserPreferences,
)

TEMPLATES = [
    {
        "parent_category": "motor_insurance_renewal",
        "prereq_category": "puc_certificate",
        "lead_time_days": 1,
        "legal_basis": "SC directive Aug 2017 + IRDAI circular IRDA/NL/CIR/MISC/104/07/2018 (Jul 2018)",
        "confidence": 1.0,
    },
    {
        "parent_category": "international_travel",
        "prereq_category": "passport_validity_6mo",
        "lead_time_days": 0,
        "legal_basis": "Common visa/entry rule (6-month passport validity)",
        "confidence": 0.95,
    },
    {
        "parent_category": "passport_renewal",
        "prereq_category": "passport_documents",
        "lead_time_days": 1,
        "legal_basis": "Passport Seva Kendra requirements",
        "confidence": 1.0,
    },
    {
        "parent_category": "vehicle_transfer",
        "prereq_category": "insurance_transfer",
        "lead_time_days": 3,
        "legal_basis": "Motor Vehicles Act (transfer within 14 days)",
        "confidence": 1.0,
    },
    {
        "parent_category": "tax_filing",
        "prereq_category": "form_16_received",
        "lead_time_days": 0,
        "legal_basis": "Income Tax Act §192 (employer TDS certificate)",
        "confidence": 1.0,
    },
    {
        "parent_category": "college_registration",
        "prereq_category": "fee_payment",
        "lead_time_days": 2,
        "legal_basis": "University policy (payment clearance)",
        "confidence": 0.9,
    },
    {
        "parent_category": "visa_application",
        "prereq_category": "passport_validity_6mo",
        "lead_time_days": 0,
        "legal_basis": "Consular requirement",
        "confidence": 0.95,
    },
]


def seed_dependency_templates(db: Session) -> int:
    existing = {(r.parent_category, r.prereq_category) for r in db.query(DependencyTemplate).all()}
    added = 0
    for tmpl in TEMPLATES:
        key = (tmpl["parent_category"], tmpl["prereq_category"])
        if key in existing:
            continue
        db.add(DependencyTemplate(**tmpl))
        added += 1
    db.commit()
    return added


@dataclass
class DemoOb:
    title: str
    vendor: str
    category: str
    obligation_type: str
    days_from_today: int
    amount: float | None
    penalty_amount: float | None
    penalty_type: str
    penalty_description: str
    lead_time_days: int = 1
    flexibility_window: int = 0


DEMO_OBLIGATIONS: list[DemoOb] = [
    # The demo anchor: PUC + insurance so auto-linker wires the SC/IRDAI edge.
    DemoOb(
        title="PUC certificate for scooter",
        vendor="Chennai Emission Testing Center",
        category="puc_certificate",
        obligation_type="document",
        days_from_today=18,
        amount=100,
        penalty_amount=10000,
        penalty_type="legal",
        penalty_description="Motor Vehicles Act §190(2) - driving without PUC",
        lead_time_days=1,
        flexibility_window=15,
    ),
    DemoOb(
        title="Two-wheeler insurance renewal",
        vendor="ACKO",
        category="motor_insurance_renewal",
        obligation_type="renewal",
        days_from_today=22,
        amount=1850,
        penalty_amount=200000,
        penalty_type="legal",
        penalty_description="Uninsured accident exposure; NCB loss",
        lead_time_days=1,
        flexibility_window=5,
    ),
    # Utility
    DemoOb(
        title="TANGEDCO electricity bill",
        vendor="TANGEDCO",
        category="utility",
        obligation_type="payment",
        days_from_today=8,
        amount=2340,
        penalty_amount=100,
        penalty_type="late_fee",
        penalty_description="Late payment surcharge + service cutoff after 15 days",
    ),
    # Subscription
    DemoOb(
        title="Netflix subscription",
        vendor="Netflix",
        category="subscription",
        obligation_type="renewal",
        days_from_today=5,
        amount=199,
        penalty_amount=0,
        penalty_type="service_cutoff",
        penalty_description="Streaming access paused",
    ),
    # Financial (rent)
    DemoOb(
        title="Hostel rent October",
        vendor="Anna Nagar PG",
        category="financial",
        obligation_type="payment",
        days_from_today=3,
        amount=12000,
        penalty_amount=500,
        penalty_type="late_fee",
        penalty_description="Landlord late fee",
    ),
    # Health appointment
    DemoOb(
        title="Dentist checkup",
        vendor="Dr. Raghavan Clinic",
        category="health",
        obligation_type="event",
        days_from_today=12,
        amount=800,
        penalty_amount=0,
        penalty_type="none",
        penalty_description="Rescheduling fee if missed",
        flexibility_window=7,
    ),
    # Education
    DemoOb(
        title="Semester fee - Anna University",
        vendor="Anna University",
        category="fee_payment",
        obligation_type="payment",
        days_from_today=25,
        amount=45000,
        penalty_amount=1000,
        penalty_type="late_fee",
        penalty_description="Late registration fee (7-day grace)",
        lead_time_days=2,
        flexibility_window=7,
    ),
    DemoOb(
        title="Semester registration",
        vendor="Anna University",
        category="college_registration",
        obligation_type="task",
        days_from_today=30,
        amount=0,
        penalty_amount=5000,
        penalty_type="expiry",
        penalty_description="Miss the semester",
    ),
    # Document expiration
    DemoOb(
        title="Aadhaar biometric update",
        vendor="UIDAI",
        category="government",
        obligation_type="document",
        days_from_today=60,
        amount=100,
        penalty_amount=0,
        penalty_type="none",
        penalty_description="Recommended every 10 years",
        flexibility_window=180,
    ),
    # Ghost-style: small recurring subscription
    DemoOb(
        title="CloudApp Pro",
        vendor="CloudApp Inc",
        category="subscription",
        obligation_type="renewal",
        days_from_today=15,
        amount=299,
        penalty_amount=0,
        penalty_type="none",
        penalty_description="unused for 4+ months",
    ),
]


def seed_demo_obligations(db: Session, user_id: str) -> int:
    """Idempotent by (user_id, title, vendor)."""
    added = 0
    existing_keys = {
        (o.user_id, o.title, o.vendor)
        for o in db.query(Obligation).filter(Obligation.user_id == user_id).all()
    }
    today = clock_today()
    for d in DEMO_OBLIGATIONS:
        key = (user_id, d.title, d.vendor)
        if key in existing_keys:
            continue
        ob = Obligation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=d.title,
            vendor=d.vendor,
            vendor_normalized=d.vendor.lower().strip(),
            category=d.category,
            obligation_type=d.obligation_type,
            amount=d.amount,
            currency="INR",
            amount_confidence=1.0,
            due_date=today + timedelta(days=d.days_from_today),
            lead_time_days=d.lead_time_days,
            flexibility_window=d.flexibility_window,
            penalty={
                "type": d.penalty_type,
                "amount": d.penalty_amount,
                "description": d.penalty_description,
            },
            resources={"inr": d.amount} if d.amount else {},
            confidence=1.0,
            sources=[{"type": "demo_seed", "ref": "chaufferone-seed-v1"}],
            urgency_tier="green",
        )
        db.add(ob)
        added += 1
    if added:
        db.commit()
    return added


def seed_demo_preferences(db: Session, user_id: str) -> bool:
    """Seed realistic Chennai-student demo preferences so the money engine has signal."""
    from app.db.models import UserPreferences

    prefs = db.get(UserPreferences, user_id)
    if prefs:
        return False
    prefs = UserPreferences(
        user_id=user_id,
        hard_floor_inr=3000,
        soft_cushion_inr=2000,
        starting_balance_inr=15000,
        estimated_monthly_income_inr=20000,
        salary_day_of_month=1,
        admin_day_offset=2,
        aggressiveness="balanced",
        voice_enabled=True,
    )
    db.add(prefs)
    db.commit()
    return True


# --------------------------------------------------------------------------------------
# handoff-v2 §6 hero scenario: persona "Arun", a tight month. Fictional companies only.
# Numbers are pinned by tests/test_scenario.py (properties, not rupees).
# --------------------------------------------------------------------------------------

SCENARIO_PREFS = {
    "hard_floor_inr": 1000,
    "soft_cushion_inr": 1000,
    "starting_balance_inr": 2500,
    "estimated_monthly_income_inr": 10000,  # allowance on the 1st
    "salary_day_of_month": 1,
}


@dataclass
class ScenarioOb:
    key: str
    title: str
    vendor: str
    category: str
    obligation_type: str
    days_from_today: int
    amount: float | None
    penalty: dict[str, Any]
    source_label: str
    source_type: str
    lead_time_days: int = 0
    confidence: float = 0.95
    payee: str | None = None


def _scenario() -> list[ScenarioOb]:
    teammate_vpa = settings.upi_payee_vpa or "demo.teammate@okaxis"
    return [
        ScenarioOb(
            key="rent",
            title="Hostel rent — October",
            vendor="Anna Nagar PG",
            category="rent",
            obligation_type="payment",
            days_from_today=5,
            amount=7800,
            penalty={"type": "late_fee", "amount": 500, "description": "₹500 late fee after the 5th"},
            source_label="WhatsApp: PG owner's reminder",
            source_type="whatsapp",
        ),
        ScenarioOb(
            key="gift",
            title="Priya's birthday gift contribution",
            vendor="Priya bday gift pool",
            category="social",
            obligation_type="payment",
            days_from_today=8,
            amount=500,
            penalty={"type": "none", "amount": 0, "description": "Social: the group buys the gift on the 8th"},
            source_label="WhatsApp: class group, 'send ₹500 by Thursday'",
            source_type="whatsapp",
            confidence=0.8,
            payee=teammate_vpa,
        ),
        ScenarioOb(
            key="puc",
            title="PUC certificate for scooter",
            vendor="Emission test centre",
            category="puc_certificate",
            obligation_type="document",
            days_from_today=-10,  # expired 10 days ago
            amount=100,
            penalty={
                "type": "legal",
                "amount": 10000,
                "description": "Riding without a valid PUC: up to ₹10,000 fine (MV Act s.190(2))",
            },
            source_label="Vehicle profile (PUC expiry entered at onboarding)",
            source_type="manual",
            lead_time_days=1,
            confidence=1.0,
        ),
        ScenarioOb(
            key="insurance",
            title="Two-wheeler insurance renewal",
            vendor="SafeRide General Insurance",
            category="motor_insurance_renewal",
            obligation_type="renewal",
            days_from_today=18,
            amount=1850,
            penalty={
                "type": "legal",
                "amount": 2000,
                "description": "Riding uninsured risks a fine; no-claim bonus is lost after a 90-day lapse",
            },
            source_label="Email: SafeRide renewal notice",
            source_type="email",
            lead_time_days=1,
        ),
        ScenarioOb(
            key="freelance",
            title="Freelance payment — logo project",
            vendor="Kavi Studio",
            category="income",
            obligation_type="income",
            days_from_today=16,
            amount=3000,
            penalty={"type": "none", "amount": 0, "description": "Expected income (invoice #0412)"},
            source_label="Email: invoice #0412, 'payment by the 16th'",
            source_type="email",
            confidence=0.85,
        ),
        ScenarioOb(
            key="lab",
            title="DBMS lab record submission",
            vendor="College",
            category="education",
            obligation_type="task",
            days_from_today=12,
            amount=None,
            penalty={"type": "none", "amount": 0, "description": "Internal marks"},
            source_label="Email: college LMS notification",
            source_type="email",
            lead_time_days=2,
        ),
    ]


def clear_user_data(db: Session, user_id: str) -> dict[str, int]:
    ids = [o.id for o in db.query(Obligation.id).filter(Obligation.user_id == user_id).all()]
    edges = 0
    if ids:
        edges = (
            db.query(PrerequisiteEdge)
            .filter(
                (PrerequisiteEdge.obligation_id.in_(ids)) | (PrerequisiteEdge.prerequisite_id.in_(ids))
            )
            .delete(synchronize_session=False)
        )
    signals = db.query(ProcessedSignal).filter(ProcessedSignal.user_id == user_id).delete()
    consents = db.query(ConsentLog).filter(ConsentLog.user_id == user_id).delete()
    obs = db.query(Obligation).filter(Obligation.user_id == user_id).delete()
    db.commit()
    return {"obligations": obs, "edges": edges, "signals": signals, "consents": consents}


def seed_scenario(db: Session, user_id: str) -> dict[str, object]:
    """Wipe this user's data and load the §6 hero scenario. Idempotent."""
    cleared = clear_user_data(db, user_id)
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
    for k, v in SCENARIO_PREFS.items():
        setattr(prefs, k, v)

    today = clock_today()
    ids: dict[str, str] = {}
    for s in _scenario():
        oid = str(uuid.uuid4())
        ids[s.key] = oid
        db.add(
            Obligation(
                id=oid,
                user_id=user_id,
                title=s.title,
                vendor=s.vendor,
                vendor_normalized=s.vendor.lower().strip(),
                category=s.category,
                obligation_type=s.obligation_type,
                amount=s.amount,
                currency="INR",
                amount_confidence=1.0 if s.amount else None,
                due_date=today + timedelta(days=s.days_from_today),
                lead_time_days=s.lead_time_days,
                penalty=s.penalty,
                resources={"inr": s.amount} if s.amount else {},
                confidence=s.confidence,
                payee=s.payee,
                sources=[{"type": s.source_type, "ref": f"scenario:{s.key}", "label": s.source_label}],
                urgency_tier="green",
            )
        )
    db.commit()

    from app.graph.linker import auto_link_prerequisites
    from app.planner import plan_dates

    edges = auto_link_prerequisites(db, user_id)
    planned = plan_dates(db, user_id)
    return {"cleared": cleared, "obligations": len(ids), "edges": edges, "planned": planned, "ids": ids}
