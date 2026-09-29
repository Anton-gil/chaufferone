"""SMS ingest: forwarder payload parsing + TRAI trusted-sender filter.

Used by POST /api/ingest/sms (the Android "SMS to URL Forwarder" app and the demo
injector share this path) and by the SMS Backup & Restore importer.

Pure functions only - no DB / LLM calls here, so they are trivially testable.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app import clock
from app.config import settings

try:  # Windows without the tzdata package has no IANA db; IST has no DST so a fixed offset is exact.
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - environment dependent
    IST = timezone(timedelta(hours=5, minutes=30), "IST")

# TRAI commercial header: 2-letter operator/circle prefix, 6-char header, optional
# category suffix (mandatory since 6 May 2025): -S service, -T transactional,
# -G government, -P promotional.
_HEADER_RE = re.compile(r"^([A-Z]{2})-([A-Z0-9]{6})(?:-([A-Z]))?$")
_BARE_HEADER_RE = re.compile(r"^[A-Z]{6}$")
_PHONE_RE = re.compile(r"^\+?[\d\s\-()]{5,20}$")
TRUSTED_SUFFIXES = frozenset({"S", "T", "G"})


def normalize_phone(value: str) -> str:
    """Digits only, Indian country code / trunk prefix dropped (last 10 digits)."""
    digits = re.sub(r"\D", "", value or "")
    # "+91 98765-43210", "919876543210", "09876543210" -> "9876543210"
    return digits[-10:] if len(digits) > 10 else digits


def _is_demo_sender(sender: str) -> bool:
    raw = sender.strip().upper()
    phone = normalize_phone(sender) if _PHONE_RE.match(sender.strip()) else ""
    for entry in settings.demo_senders or []:
        entry = str(entry).strip()
        if not entry:
            continue
        if entry.upper() == raw:
            return True
        if phone and _PHONE_RE.match(entry) and normalize_phone(entry) == phone:
            return True
    return False


def check_sender(sender: str | None) -> tuple[bool, str]:
    """TRAI-rules sender filter. Returns (ok, reason); reason is surfaced in the API."""
    s = (sender or "").strip()
    if not s:
        return False, "empty_sender"
    if _is_demo_sender(s):
        return True, "demo_sender"

    up = s.upper().replace(" ", "")
    m = _HEADER_RE.match(up)
    if m:
        suffix = m.group(3)
        if suffix is None:
            return True, "legacy_header"
        if suffix in TRUSTED_SUFFIXES:
            return True, f"trusted_header_{suffix}"
        if suffix == "P":
            return False, "promotional_header"
        return False, f"unknown_suffix_{suffix}"
    if _BARE_HEADER_RE.match(up):
        return True, "bare_header"
    if _PHONE_RE.match(s):
        return False, "phone_number_not_in_demo_senders"
    return False, "unrecognised_sender"


# --- Forwarder payload -------------------------------------------------------


def parse_stamp(value: Any) -> int | None:
    """Epoch millis (int / float / numeric string) -> int millis; None if missing/garbage."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = int(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            n = int(float(text))
        except ValueError:
            return None  # e.g. an unreplaced "%sentStamp%" placeholder
    if n <= 0:
        return None
    if n < 100_000_000_000:  # looks like epoch seconds, not millis
        n *= 1000
    return n


def stamp_to_date(stamp_ms: int | None) -> date | None:
    if not stamp_ms:
        return None
    try:
        return datetime.fromtimestamp(stamp_ms / 1000, tz=IST).date()
    except (OverflowError, OSError, ValueError):
        return None


def sms_source_ref(sender: str, stamp_ms: int | None, text: str) -> str:
    key = f"{sender}|{stamp_ms if stamp_ms is not None else ''}|{text}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


@dataclass
class SmsMessage:
    sender: str
    text: str
    stamp_ms: int | None
    received_at: date
    source_ref: str


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = payload.get(k)
        if v not in (None, ""):
            return v
    return None


def make_sms(
    sender: str, text: str, stamp_ms: int | None, ref_stamp_ms: int | None = None
) -> SmsMessage:
    """ref_stamp_ms (default: stamp_ms) feeds the dedup hash; the forwarder's sentStamp
    equals the backup's date_sent, so the same SMS dedupes across both paths."""
    sender = (sender or "").strip()
    text = (text or "").strip()
    ref_stamp = ref_stamp_ms if ref_stamp_ms is not None else stamp_ms
    return SmsMessage(
        sender=sender,
        text=text,
        stamp_ms=stamp_ms,
        received_at=stamp_to_date(stamp_ms) or clock.today(),
        source_ref=sms_source_ref(sender, ref_stamp, text),
    )


def parse_forwarder_payload(payload: dict[str, Any]) -> SmsMessage:
    """Default forwarder template: {"from","text","sentStamp","receivedStamp","sim"}.

    Extra fields are ignored; stamps may be int/str/missing. The demo injector
    sends only {"from", "text"}.
    """
    sender = _first(payload, "from", "sender", "address", "phone")
    text = _first(payload, "text", "body", "message", "msg")
    stamp = parse_stamp(_first(payload, "sentStamp", "sent_stamp", "timestamp"))
    if stamp is None:
        stamp = parse_stamp(_first(payload, "receivedStamp", "received_stamp"))
    return make_sms(str(sender or ""), str(text or ""), stamp)
