"""Outbound-connection audit log (§7.2: 'network log screen').

The privacy pitch is that user data never leaves the device. To be checkable
instead of merely promised, every outbound HTTP call the engine makes routes
through log_outbound() first, which records host + purpose + timestamp.
The /network page reads this back verbatim.

We deliberately don't log request bodies or URLs (which could leak query
strings) - the promise is 'we can prove we didn't send anything', not 'here
is a debug trace of everything we did send'.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.session import Base, SessionLocal


class OutboundLog(Base):
    __tablename__ = "outbound_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    host: Mapped[str] = mapped_column(String, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def _host(url: str) -> str:
    try:
        h = urlparse(url).hostname
    except (TypeError, ValueError):
        h = None
    return h or url


def log_outbound(url_or_host: str, purpose: str, *, ok: bool = True, reason: str | None = None) -> None:
    """Fire-and-forget. Uses its own session so callers don't need one."""
    db: Session = SessionLocal()
    try:
        db.add(OutboundLog(host=_host(url_or_host), purpose=purpose, ok=ok, reason=reason))
        db.commit()
    except Exception:  # never let logging break the caller
        db.rollback()
    finally:
        db.close()


def recent(db: Session, limit: int = 200) -> list[dict[str, Any]]:
    rows = (
        db.query(OutboundLog)
        .order_by(OutboundLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "host": r.host,
            "purpose": r.purpose,
            "ok": bool(r.ok),
            "reason": r.reason,
            "at": r.at.isoformat() if r.at else None,
        }
        for r in rows
    ]
