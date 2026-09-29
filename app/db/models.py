"""SQLAlchemy models — the obligation graph.

Merges handoff.md's unified Obligation schema with he.md's dependency_templates
and 3-way match signal fields. SQLite-friendly types throughout.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String)
    vendor_normalized: Mapped[str | None] = mapped_column(String, index=True)
    category: Mapped[str | None] = mapped_column(String, index=True)
    obligation_type: Mapped[str] = mapped_column(String, default="payment")

    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    amount_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    flexibility_window: Mapped[int] = mapped_column(Integer, default=0)
    recurrence: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    penalty: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    urgency_tier: Mapped[str] = mapped_column(String, default="green")

    verification_state: Mapped[str] = mapped_column(String, default="extracted")
    signal_extracted: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    signal_pre_debit: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    signal_debit: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    signal_receipt: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    batchable: Mapped[bool] = mapped_column(Boolean, default=False)
    batch_group: Mapped[str | None] = mapped_column(String)
    trigger_event: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    auto_pay_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String, default="upcoming", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    outgoing_edges: Mapped[list["PrerequisiteEdge"]] = relationship(
        "PrerequisiteEdge",
        foreign_keys="PrerequisiteEdge.obligation_id",
        back_populates="obligation",
        cascade="all, delete-orphan",
    )


class PrerequisiteEdge(Base):
    __tablename__ = "prerequisite_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id", ondelete="CASCADE"), index=True)
    prerequisite_id: Mapped[str] = mapped_column(ForeignKey("obligations.id", ondelete="CASCADE"), index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    legal_basis: Mapped[str | None] = mapped_column(Text)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    edge_kind: Mapped[str] = mapped_column(String, default="needs_first")

    obligation: Mapped["Obligation"] = relationship(
        "Obligation", foreign_keys=[obligation_id], back_populates="outgoing_edges"
    )

    __table_args__ = (UniqueConstraint("obligation_id", "prerequisite_id", name="uq_edge"),)


class DependencyTemplate(Base):
    __tablename__ = "dependency_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    prereq_category: Mapped[str] = mapped_column(String, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_basis: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=1.0)
    country: Mapped[str] = mapped_column(String, default="IN")


class ObligationHistory(Base):
    __tablename__ = "obligation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    vendor_normalized: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    due_date: Mapped[date | None] = mapped_column(Date)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    was_late: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_final_state: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VendorPattern(Base):
    __tablename__ = "vendor_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    vendor_normalized: Mapped[str] = mapped_column(String, nullable=False)
    avg_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    std_dev_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    avg_day_of_month: Mapped[int | None] = mapped_column(Integer)
    recurrence_frequency: Mapped[str | None] = mapped_column(String)
    recurrence_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    miss_rate: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    trend: Mapped[str | None] = mapped_column(String)
    seasonal_multipliers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_predicted: Mapped[date | None] = mapped_column(Date)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "vendor_normalized", name="uq_vendor_pattern"),)


class ProcessedSignal(Base):
    __tablename__ = "processed_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    obligation_id: Mapped[str | None] = mapped_column(ForeignKey("obligations.id", ondelete="SET NULL"))
    raw_snippet: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "source_type", "source_ref", name="uq_signal"),)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    hard_floor_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=3000)
    soft_cushion_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=2000)
    starting_balance_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=15000)
    estimated_monthly_income_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=20000)
    salary_day_of_month: Mapped[int | None] = mapped_column(Integer)
    admin_day_offset: Mapped[int] = mapped_column(Integer, default=2)
    aggressiveness: Mapped[str] = mapped_column(String, default="balanced")
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    channels_enabled: Mapped[dict[str, bool]] = mapped_column(
        JSON,
        default=lambda: {"gmail": True, "sms": True, "whatsapp": False, "pdf": True},
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    linked_obligation_id: Mapped[str | None] = mapped_column(ForeignKey("obligations.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
