"""Parse a WhatsApp "Export chat (without media)" .txt (or the .zip it ships in).

Supported line headers (dates are D/M/Y - India):
  Android:  29/09/26, 9:41 pm - Rahul: text      (U+202F before am/pm is common; 12h or 24h)
  Android:  29/09/2026, 21:41 - Rahul: text
  iOS:      [29/09/26, 9:41:05 PM] Rahul: text   (line often prefixed with U+200E)
Lines without a header are continuations of the previous message. System lines
(no "Name: " part, or iOS U+200E-marked) and media placeholders are skipped.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_INVISIBLE_PREFIX = "﻿‎‏‪‫‬"

_DATE = r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})"
_TIME = r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?"
_AMPM = r"(?:\s*([AaPp])\.?\s?[Mm]\.?)?"  # \s also matches U+202F / U+00A0
ANDROID_RE = re.compile(rf"^{_DATE},?\s+{_TIME}{_AMPM}\s+[-–]\s+(.*)$")
IOS_RE = re.compile(rf"^\[{_DATE},?\s+{_TIME}{_AMPM}\]\s*(.*)$")

_SYSTEM_RE = re.compile(
    r"end-to-end encrypted|created group|changed the subject|changed this group's|"
    r"changed the group|joined using this group's invite link|security code|"
    r"disappearing messages|deleted this group's icon|is now an admin|now an admin",
    re.IGNORECASE,
)
_MEDIA_RE = re.compile(
    r"^(?:<media omitted>|(?:image|video|audio|sticker|gif|document|contact card) omitted|"
    r"<attached: [^>]*>|this message was deleted\.?|you deleted this message\.?|null|"
    r"missed (?:voice|video) call)$",
    re.IGNORECASE,
)
_EDITED_RE = re.compile(r"\s*<this message was edited>\s*$", re.IGNORECASE)

WA_KEYWORDS_RE = re.compile(
    r"₹|\brs\b|\brs\.?\d|\binr\b|\bsend\b|contribut|\bpay|\bsplit|\bdue\b|deadline|"
    r"\bsubmi(?:t|ssion)|\bby\s+(?:this\s+|next\s+)?"
    r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b|"
    r"\brsvp\b|birthday|\bb'?day\b|\bgift|\bfees?\b|\brent\b|\btrips?\b",
    re.IGNORECASE,
)


@dataclass
class WhatsAppMessage:
    timestamp: datetime  # naive, phone-local time
    author: str
    text: str

    @property
    def source_ref(self) -> str:
        key = f"{self.author}|{self.timestamp.isoformat()}|{self.text}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    @property
    def pipeline_body(self) -> str:
        return f"WhatsApp group message from {self.author} on {self.timestamp:%d %b %Y}: {self.text}"


def _build_ts(d: str, mo: str, y: str, h: str, mi: str, s: str | None, ampm: str | None):
    day, month, year = int(d), int(mo), int(y)
    if year < 100:
        year += 2000
    if month > 12 and day <= 12:  # US-locale export (M/D/Y)
        day, month = month, day
    hour = int(h)
    if ampm:
        if hour > 12:
            return None
        hour = hour % 12 + (12 if ampm.lower() == "p" else 0)
    try:
        return datetime(year, month, day, hour, int(mi), int(s or 0))
    except ValueError:
        return None


def _match_header(line: str) -> tuple[datetime, str] | None:
    m = IOS_RE.match(line) or ANDROID_RE.match(line)
    if not m:
        return None
    ts = _build_ts(*m.groups()[:7])
    if ts is None:
        return None
    return ts, m.group(8)


def _clean_text(text: str) -> str:
    return _EDITED_RE.sub("", text).strip()


def parse_whatsapp(text: str) -> list[WhatsAppMessage]:
    messages: list[WhatsAppMessage] = []
    current: WhatsAppMessage | None = None

    def flush() -> None:
        if current is None:
            return
        body = _clean_text(current.text)
        if body and not _MEDIA_RE.match(body.lstrip(_INVISIBLE_PREFIX)):
            messages.append(WhatsAppMessage(current.timestamp, current.author, body))

    for raw_line in text.splitlines():
        line = raw_line.lstrip(_INVISIBLE_PREFIX)
        header = _match_header(line)
        if header is None:
            if current is not None:
                current.text += "\n" + line
            continue

        flush()
        current = None
        ts, rest = header
        author, sep, body = rest.partition(": ")
        author = author.strip().lstrip(_INVISIBLE_PREFIX)
        if (
            not sep
            or not author
            or len(author) > 60
            or body.startswith("‎")  # iOS system events / media placeholders
            or (_SYSTEM_RE.search(rest) and not _looks_like_name(author))
        ):
            continue
        current = WhatsAppMessage(ts, author, body)
    flush()
    return messages


def _looks_like_name(author: str) -> bool:
    # "Rahul changed the subject from "Trip: Goa"" splits into a sentence, not a name.
    return '"' not in author and not _SYSTEM_RE.search(author) and len(author.split()) <= 5


def select_messages(
    messages: list[WhatsAppMessage], *, days: int, today: date
) -> tuple[list[WhatsAppMessage], dict[str, int]]:
    cutoff = today - timedelta(days=days)
    filtered = {"out_of_window": 0, "no_keyword": 0}
    selected: list[WhatsAppMessage] = []
    for m in messages:
        if m.timestamp.date() < cutoff:
            filtered["out_of_window"] += 1
        elif not WA_KEYWORDS_RE.search(m.text):
            filtered["no_keyword"] += 1
        else:
            selected.append(m)
    return selected, filtered


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def read_export(data: bytes, filename: str | None = None) -> str:
    """Return the chat text from a .txt upload or a .zip containing one .txt."""
    if data[:4] == b"PK\x03\x04" or (filename or "").lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                txts = [
                    i
                    for i in zf.infolist()
                    if not i.is_dir()
                    and i.filename.lower().endswith(".txt")
                    and not i.filename.startswith("__MACOSX")
                ]
                if not txts:
                    raise ValueError("zip contains no .txt chat export")
                data = zf.read(max(txts, key=lambda i: i.file_size))
        except zipfile.BadZipFile as e:
            raise ValueError(f"not a valid zip: {e}") from e
    return decode_text(data)
