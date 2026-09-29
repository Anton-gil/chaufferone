"""Response schemas for the money engine."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class DebitEntry(BaseModel):
    obligation_id: str
    title: str
    amount: float
    category: str | None = None
    flexibility_window_days: int = 0
    penalty_amount: float = 0


class DayPoint(BaseModel):
    date: date
    opening_balance: float
    income: float
    debits: list[DebitEntry]
    total_debit: float
    closing_balance: float
    breach_type: Literal["none", "cushion", "floor"] = "none"
    breach_depth_inr: float = 0


class Clash(BaseModel):
    id: str                       # stable within one forecast call
    first_breach_date: date
    last_breach_date: date
    tier: Literal["cushion", "floor"]
    max_depth_inr: float
    obligations_involved: list[str]     # ids
    obligation_titles: list[str]        # for pitch readability


class Fix(BaseModel):
    kind: Literal["defer", "pause_subscription", "reorder"]
    obligation_id: str
    obligation_title: str
    description: str
    new_date: date | None = None
    added_penalty_inr: float
    disruption_score: int          # 0-100, subjective (defer within window = low; pause active sub = higher)
    resolves_clash: bool
    resulting_min_balance_inr: float


class ForecastResponse(BaseModel):
    horizon_days: int
    starting_balance_inr: float
    hard_floor_inr: float
    soft_cushion_inr: float
    days: list[DayPoint]
    clashes: list[Clash]
