"""Parse an "SMS Backup & Restore" XML export (60-day backfill).

<smses count="N">
  <sms protocol="0" address="AX-HDFCBK-S" date="1727600000000" type="1"
       body="Rs.500 debited&#10;..." readable_date="..." contact_name="(Unknown)" />
  <mms ...> ... </mms>
</smses>

Streaming (iterparse + root.clear()) because exports can be tens of MB.
SMS Backup & Restore writes emoji as UTF-16 surrogate-pair char refs
(&#55357;&#56832;), which are illegal in XML and make every parser choke, so the
byte stream is sanitised line by line first (entities never span a line: body
newlines are encoded as &#10;).
"""

from __future__ import annotations

import heapq
import io
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import IO

from app.ingest.sms import SmsMessage, check_sender, make_sms, parse_stamp

INBOX_TYPE = "1"

FINANCE_KEYWORDS_RE = re.compile(
    r"\brs\b|\brs\.?\d|\binr|₹|debit|credit|\b(?:over)?due\b|mandate|auto-?pay|"
    r"auto-?debit|renew|\bbill|premium|polic(?:y|ies)|recharge|\bemis?\b|subscription|payment",
    re.IGNORECASE,
)
OTP_RE = re.compile(r"\botp\b|one[- ]time password|verification code", re.IGNORECASE)

# Decimal char refs for UTF-16 surrogates: high D800-DBFF (55296-56319), low DC00-DFFF (56320-57343).
_HI = rb"(?:5529[6-9]|55[3-9]\d\d|56[0-2]\d\d|563[01]\d)"
_LO = rb"(?:563[2-9]\d|56[4-9]\d\d|57[0-2]\d\d|573[0-3]\d|5734[0-3])"
_PAIR_RE = re.compile(rb"&#(" + _HI + rb");&#(" + _LO + rb");")
_LONE_SURROGATE_RE = re.compile(rb"&#(?:" + _HI + rb"|" + _LO + rb");")
# XML 1.0 forbids control chars other than tab/LF/CR, even as char refs.
_BAD_CTRL_RE = re.compile(rb"&#0*(?:[0-8]|1[124-9]|2\d|3[01]);|&#x0*(?:[0-8bBcCeEfF]|1[0-9a-fA-F]);")


def _join_pair(m: re.Match[bytes]) -> bytes:
    hi, lo = int(m.group(1)), int(m.group(2))
    return b"&#%d;" % (0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00))


def sanitize_xml_line(line: bytes) -> bytes:
    if b"&#" not in line:
        return line
    line = _PAIR_RE.sub(_join_pair, line)
    line = _LONE_SURROGATE_RE.sub(b"&#65533;", line)
    return _BAD_CTRL_RE.sub(b" ", line)


class _SanitizingReader:
    """Minimal file-like wrapper: read(n) over sanitised lines of a binary stream."""

    def __init__(self, raw: IO[bytes]):
        self._lines = iter(raw.readline, b"")
        self._buf = bytearray()
        self._eof = False

    def read(self, size: int = -1) -> bytes:
        while not self._eof and (size < 0 or len(self._buf) < size):
            line = next(self._lines, None)
            if line is None:
                self._eof = True
                break
            self._buf += sanitize_xml_line(line)
        if size < 0 or size >= len(self._buf):
            out = bytes(self._buf)
            self._buf.clear()
        else:
            out = bytes(self._buf[:size])
            del self._buf[:size]
        return out


@dataclass
class BackupSms:
    address: str
    body: str
    stamp_ms: int | None
    type: str
    contact_name: str | None = None
    date_sent_ms: int | None = None


def iter_backup_sms(source: bytes | IO[bytes]) -> Iterator[BackupSms]:
    """Yield every <sms> element (all types). Raises ET.ParseError on broken XML."""
    raw = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    depth = 0
    root = None
    for event, elem in ET.iterparse(_SanitizingReader(raw), events=("start", "end")):
        if event == "start":
            if root is None:
                root = elem
            depth += 1
            continue
        depth -= 1
        if elem.tag == "sms":
            a = elem.attrib
            yield BackupSms(
                address=(a.get("address") or "").strip(),
                body=a.get("body") or "",
                stamp_ms=parse_stamp(a.get("date")),
                type=(a.get("type") or "").strip(),
                contact_name=a.get("contact_name"),
                date_sent_ms=parse_stamp(a.get("date_sent")),
            )
        if depth == 1 and root is not None:  # closed a direct child of <smses>
            root.clear()


@dataclass
class BackupParseResult:
    messages: list[SmsMessage]  # oldest first, ready for the pipeline
    scanned: int = 0
    filtered: dict[str, int] = field(default_factory=dict)
    parse_error: str | None = None


def parse_sms_backup(
    source: bytes | IO[bytes],
    *,
    days: int = 60,
    limit: int = 300,
    today: date,
) -> BackupParseResult:
    """Inbox-only, trusted senders, last `days`, financial keywords, newest `limit`."""
    filtered = {
        "not_inbox": 0,
        "untrusted_sender": 0,
        "out_of_window": 0,
        "otp": 0,
        "no_keyword": 0,
        "over_limit": 0,
    }
    cutoff = today - timedelta(days=days)
    heap: list[tuple[int, int, SmsMessage]] = []  # min-heap of the newest `limit` candidates
    scanned = 0
    parse_error = None
    try:
        for s in iter_backup_sms(source):
            scanned += 1
            if s.type != INBOX_TYPE:
                filtered["not_inbox"] += 1
                continue
            ok, _ = check_sender(s.address)
            if not ok:
                filtered["untrusted_sender"] += 1
                continue
            msg = make_sms(s.address, s.body, s.stamp_ms, ref_stamp_ms=s.date_sent_ms)
            if s.stamp_ms is None or msg.received_at < cutoff:
                filtered["out_of_window"] += 1
                continue
            if OTP_RE.search(msg.text):
                filtered["otp"] += 1
                continue
            if not FINANCE_KEYWORDS_RE.search(msg.text):
                filtered["no_keyword"] += 1
                continue
            item = (msg.stamp_ms or 0, scanned, msg)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)
                filtered["over_limit"] += 1
    except ET.ParseError as e:  # keep whatever parsed before the corruption
        parse_error = f"XML parse error: {e}"

    messages = [m for _, _, m in sorted(heap)]  # oldest first
    return BackupParseResult(messages, scanned, filtered, parse_error)
