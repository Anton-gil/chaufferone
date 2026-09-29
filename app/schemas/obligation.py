"""Pydantic response schemas for the API and LLM extraction contract."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedObligation(BaseModel):
    """The strict JSON contract we ask the LLM to produce."""

    title: str
    vendor: str | None = None
    category: str | None = Field(
        default=None,
        description="One of: utility|insurance|subscription|government|health|vehicle|education|financial|other",
    )
    obligation_type: Literal["payment", "document", "task", "event", "renewal"] = "payment"
    amount: float | None = None
    currency: str = "INR"
    due_date: date | None = None
    lead_time_days: int = 0
    flexibility_window_days: int = 0
    penalty_type: Literal["late_fee", "service_cutoff", "legal", "credit_impact", "expiry", "none"] | None = None
    penalty_amount: float | None = None
    penalty_description: str | None = None
    auto_pay: bool | None = None
    action_required: str | None = None
    urgency: Literal["low", "medium", "high", "critical"] | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    notes: str | None = None


class TriageDecision(BaseModel):
    is_obligation: bool
    confidence: float
    category_hint: str | None = None


class ObligationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    vendor: str | None
    category: str | None
    obligation_type: str
    amount: float | None
    currency: str
    due_date: date | None
    planned_on: date | None = None
    plan_locked: bool = False
    payee: str | None = None
    auto_pay_enabled: bool = False
    lead_time_days: int
    penalty: dict[str, Any]
    risk_score: int
    urgency_tier: str
    verification_state: str
    confidence: float
    status: str
    sources: list[dict[str, Any]]
    created_at: datetime
