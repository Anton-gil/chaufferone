"""Subscribable .ics feed of every obligation, anchored at its start-by date.

Google Calendar, Apple Calendar and Outlook all subscribe to a URL and refresh
periodically. The feed is read-only. We anchor events on start_by (not due_date)
so the calendar shows people what to *begin* today, matching the Timeline's
promise in handoff.md §3.6.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import Obligation
from app.graph.dag import build_graph
from app.graph.scheduler import compute_start_by
from app.money.forecast import effective_date


def _escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _fold(line: str) -> str:
    # RFC 5545 caps lines at 75 octets; fold with CRLF + single space.
    if len(line) <= 75:
        return line
    chunks = [line[:75]]
    rest = line[75:]
    while rest:
        chunks.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(chunks)


def _event(o: Obligation, anchor: date, uid_domain: str) -> list[str]:
    end = anchor + timedelta(days=1)
    summary = o.title if o.status not in ("verified", "paid", "resolved") else f"Done: {o.title}"
    if o.amount:
        summary = f"{summary} (Rs.{float(o.amount):.0f})"
    parts: list[str] = []
    if o.due_date:
        parts.append(f"Due {o.due_date:%d %b %Y}.")
    if o.vendor:
        parts.append(f"Vendor: {o.vendor}.")
    penalty = (o.penalty or {}).get("description")
    if penalty:
        parts.append(f"Miss it: {penalty}")
    parts.append("From Chaufferone.")
    return [
        "BEGIN:VEVENT",
        f"UID:{o.id}@{uid_domain}",
        f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{anchor:%Y%m%d}",
        f"DTEND;VALUE=DATE:{end:%Y%m%d}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(' '.join(parts))}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]


def render_ics(db: Session, user_id: str, *, uid_domain: str = "chaufferone.local") -> str:
    graph = build_graph(db, user_id)
    obligations = db.query(Obligation).filter(Obligation.user_id == user_id).all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chaufferone//Obligation Engine//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Chaufferone: Start-by dates",
        "X-WR-CALDESC:What to start today so nothing goes missed.",
    ]
    for o in obligations:
        anchor = (
            compute_start_by(graph, o.id) if o.id in graph and o.due_date else None
        ) or effective_date(o) or o.due_date
        if not anchor:
            continue
        lines.extend(_event(o, anchor, uid_domain))
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
