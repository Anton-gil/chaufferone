"""Seed data: dependency template knowledge pack + demo obligations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DependencyTemplate, Obligation

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
    today = date.today()
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
            sources=[{"type": "demo_seed", "ref": "sutradhar-seed-v1"}],
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
