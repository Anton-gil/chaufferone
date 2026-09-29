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
    credits: list[DebitEntry] = []  # expected one-off income (e.g. freelance), salary excluded
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
    id: str | None = None          # "A", "B", "C" after ranking
    kind: Literal["defer", "pause_subscription", "pause_mandate", "reorder"]
    obligation_id: str
    obligation_title: str
    description: str
    old_date: date | None = None
    new_date: date | None = None
    deadline: date | None = None   # pause_mandate: last day to act (24h before the debit)
    added_penalty_inr: float = 0
    disruption_score: int = 0      # 0-100, subjective (defer within window = low; pause active sub = higher)
    resolves_clash: bool = False
    touches_cushion: bool = False
    resulting_min_balance_inr: float = 0
    depends_on_income: str | None = None  # title of an *expected* income the fix relies on
    income_date: date | None = None
    requires_user_action: bool = False    # e.g. pausing a mandate happens in the user's UPI app


class ForecastResponse(BaseModel):
    horizon_days: int
    starting_balance_inr: float
    hard_floor_inr: float
    soft_cushion_inr: float
    days: list[DayPoint]
    clashes: list[Clash]
