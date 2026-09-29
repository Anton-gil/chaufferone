"""Parse .eml files (Gmail -> Download message). Stdlib email + BeautifulSoup for HTML-only mail."""

from __future__ import annotations

import email
import email.policy
import hashlib
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage, Message
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from app.ingest.sms import IST


@dataclass
class EmlMessage:
    source_ref: str
    subject: str
    sender: str
    received_at: date | None
    body: str


def html_to_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:  # lxml missing/broken -> stdlib parser
        soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def _part_text(part: Message) -> str:
    try:
        content = part.get_content()  # type: ignore[attr-defined]
        if isinstance(content, bytes):
            raise LookupError
        return content
    except (LookupError, AttributeError, UnicodeError, ValueError):
        payload = part.get_payload(decode=True) or b""
        if isinstance(payload, str):
            return payload
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _body_text(msg: EmailMessage) -> str:
    plain = msg.get_body(preferencelist=("plain",))
    if plain is not None:
        text = _part_text(plain).strip()
        if text:
            return text
    html = msg.get_body(preferencelist=("html",))
    if html is not None:
        return html_to_text(_part_text(html))
    # Odd structures: first text/* part anywhere.
    for part in msg.walk():
        if part.get_content_maintype() == "text" and not part.is_multipart():
            text = _part_text(part)
            return html_to_text(text) if part.get_content_subtype() == "html" else text.strip()
    return ""


def _header(msg: Message, name: str) -> str:
    try:
        value = msg.get(name)
    except Exception:  # malformed header under policy.default -> use the raw value
        value = next(
            (v for k, v in getattr(msg, "raw_items", list)() if k.lower() == name.lower()), None
        )
    return str(value).strip() if value is not None else ""


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    return dt.astimezone(IST).date() if dt.tzinfo else dt.date()


def parse_eml(raw: bytes) -> EmlMessage:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    message_id = _header(msg, "Message-ID")
    return EmlMessage(
        source_ref=message_id or hashlib.sha1(raw).hexdigest(),
        subject=_header(msg, "Subject"),
        sender=_header(msg, "From"),
        received_at=_parse_date(_header(msg, "Date")),
        body=_body_text(msg),  # type: ignore[arg-type]
    )
