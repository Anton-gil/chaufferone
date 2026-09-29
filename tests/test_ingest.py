"""Ingest adapters: pure parsers + endpoint wiring (no DB, no LLM)."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime
from email.message import EmailMessage

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_routes
from app.config import settings
from app.db.session import get_db
from app.extract.pipeline import ProcessResult
from app.ingest import eml, sms, sms_backup, whatsapp
from app.ingest.sms import IST

TODAY = date(2026, 9, 30)


def ms(y: int, m: int, d: int, h: int = 12, mi: int = 0) -> int:
    return int(datetime(y, m, d, h, mi, tzinfo=IST).timestamp() * 1000)


@pytest.fixture(autouse=True)
def pinned_env(monkeypatch):
    monkeypatch.setattr(settings, "demo_today", TODAY)
    monkeypatch.setattr(settings, "demo_senders", [])


# --- sender filter ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "sender,reason",
    [
        ("AX-HDFCBK-S", "trusted_header_S"),
        ("VM-SBIUPI-T", "trusted_header_T"),
        ("JD-ICICIT-G", "trusted_header_G"),
        ("BZ-KOTAKB-S", "trusted_header_S"),
        ("ax-hdfcbk-s", "trusted_header_S"),
        ("AX-HDFCBK", "legacy_header"),
        ("HDFCBK", "bare_header"),
    ],
)
def test_sender_accepts_trusted_headers(sender, reason):
    assert sms.check_sender(sender) == (True, reason)


@pytest.mark.parametrize(
    "sender,reason",
    [
        ("AX-HDFCBK-P", "promotional_header"),
        ("+919876543210", "phone_number_not_in_demo_senders"),
        ("98765 43210", "phone_number_not_in_demo_senders"),
        ("", "empty_sender"),
        (None, "empty_sender"),
        ("AX-HDFCBK-X", "unknown_suffix_X"),
        ("HDFC", "unrecognised_sender"),
    ],
)
def test_sender_rejects(sender, reason):
    assert sms.check_sender(sender) == (False, reason)


@pytest.mark.parametrize(
    "incoming", ["+919876543210", "919876543210", "09876543210", "9876543210", "+91 98765-43210"]
)
def test_demo_sender_normalization(monkeypatch, incoming):
    monkeypatch.setattr(settings, "demo_senders", ["+91 98765-43210"])
    assert sms.check_sender(incoming) == (True, "demo_sender")
    assert sms.check_sender("+919876543211")[0] is False


def test_demo_sender_can_be_a_header(monkeypatch):
    monkeypatch.setattr(settings, "demo_senders", ["AX-DEMOBK-P"])
    assert sms.check_sender("ax-demobk-p") == (True, "demo_sender")


# --- forwarder payload ---------------------------------------------------------------------


def test_forwarder_payload_string_stamps_and_ist_date():
    # 20:00 UTC on 29 Sep is 01:30 IST on 30 Sep.
    stamp = int(datetime(2026, 9, 29, 20, 0, tzinfo=UTC).timestamp() * 1000)
    msg = sms.parse_forwarder_payload(
        {"from": " AX-HDFCBK-S ", "text": " Rs.500 due ", "sentStamp": str(stamp),
         "receivedStamp": "", "sim": "SIM1", "extra": 1}
    )
    assert msg.sender == "AX-HDFCBK-S"
    assert msg.text == "Rs.500 due"
    assert msg.stamp_ms == stamp
    assert msg.received_at == date(2026, 9, 30)
    expected = hashlib.sha1(f"AX-HDFCBK-S|{stamp}|Rs.500 due".encode()).hexdigest()
    assert msg.source_ref == expected


def test_forwarder_payload_missing_stamps_falls_back():
    msg = sms.parse_forwarder_payload({"from": "HDFCBK", "text": "hi", "sentStamp": "%sentStamp%"})
    assert msg.stamp_ms is None
    assert msg.received_at == TODAY
    rcv = sms.parse_forwarder_payload({"from": "HDFCBK", "text": "hi", "receivedStamp": ms(2026, 9, 1)})
    assert rcv.received_at == date(2026, 9, 1)


def test_parse_stamp_variants():
    assert sms.parse_stamp("1790658000000") == 1790658000000
    assert sms.parse_stamp(1790658000000) == 1790658000000
    assert sms.parse_stamp("1790658000") == 1790658000000  # seconds -> millis
    assert sms.parse_stamp("") is None
    assert sms.parse_stamp(None) is None
    assert sms.parse_stamp("abc") is None


# --- WhatsApp ----------------------------------------------------------------------------

WA_ANDROID = (
    "29/09/26, 9:39 pm - Messages and calls are end-to-end encrypted. No one outside of this chat, "
    "not even WhatsApp, can read or listen to them. Tap to learn more.\n"
    '29/09/26, 9:40 pm - Rahul created group "Goa Trip"\n'
    "29/09/26, 9:40 pm - Rahul added Priya\n"
    '29/09/26, 9:40 pm - Rahul changed the subject from "Trip: Goa" to "Trip"\n'
    "29/09/26, 9:41 pm - Rahul: Everyone please send ₹500 for Asha's birthday gift\n"
    "by Thursday night\n"
    "UPI: rahul@okaxis\n"
    "29/09/26, 9:42 pm - Priya: <Media omitted>\n"
    "29/09/26, 21:43 - Priya: done!\n"
    "29/09/26, 12:05 am - Karan: late night msg\n"
)


def test_whatsapp_android_2digit_12h_narrow_nbsp_multiline_and_system_skip():
    msgs = whatsapp.parse_whatsapp(WA_ANDROID)
    assert [(m.author, m.timestamp) for m in msgs] == [
        ("Rahul", datetime(2026, 9, 29, 21, 41)),
        ("Priya", datetime(2026, 9, 29, 21, 43)),
        ("Karan", datetime(2026, 9, 29, 0, 5)),
    ]
    assert msgs[0].text == (
        "Everyone please send ₹500 for Asha's birthday gift\nby Thursday night\nUPI: rahul@okaxis"
    )


def test_whatsapp_android_4digit_year_24h():
    msgs = whatsapp.parse_whatsapp("29/09/2026, 21:41 - Rahul: Rent due by Monday\n")
    assert len(msgs) == 1
    assert msgs[0].timestamp == datetime(2026, 9, 29, 21, 41)
    assert msgs[0].author == "Rahul"
    assert msgs[0].text == "Rent due by Monday"


def test_whatsapp_ios_format():
    chat = (
        "‎[29/09/26, 9:40:00 PM] Goa Trip: ‎Messages and calls are end-to-end encrypted.\n"
        "‎[29/09/26, 9:40:10 PM] Goa Trip: ‎Rahul created group “Goa Trip”\n"
        "[29/09/26, 9:41:05 PM] Rahul: Trip contribution ₹2000 each\n"
        "second line\n"
        "‎[29/09/26, 9:41:30 PM] Priya: ‎image omitted\n"
        "[02/10/26, 10:00:00 AM] +91 98765 43210: Fee submission deadline Friday\n"
    )
    msgs = whatsapp.parse_whatsapp(chat)
    assert [(m.author, m.timestamp, m.text) for m in msgs] == [
        ("Rahul", datetime(2026, 9, 29, 21, 41, 5), "Trip contribution ₹2000 each\nsecond line"),
        ("+91 98765 43210", datetime(2026, 10, 2, 10, 0, 0), "Fee submission deadline Friday"),
    ]


def test_whatsapp_select_and_body_and_ref():
    msgs = whatsapp.parse_whatsapp(
        WA_ANDROID + "01/06/26, 10:00 - Rahul: old: send ₹100 for trip\n"
    )
    selected, filtered = whatsapp.select_messages(msgs, days=60, today=TODAY)
    assert [m.author for m in selected] == ["Rahul"]
    assert filtered == {"out_of_window": 1, "no_keyword": 2}
    m = selected[0]
    assert m.pipeline_body.startswith("WhatsApp group message from Rahul on 29 Sep 2026: Everyone")
    key = f"Rahul|{m.timestamp.isoformat()}|{m.text}"
    assert m.source_ref == hashlib.sha1(key.encode()).hexdigest()


def test_whatsapp_read_export_zip_and_bom():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("WhatsApp Chat with Goa Trip.txt", ("﻿" + WA_ANDROID).encode("utf-8"))
    text = whatsapp.read_export(buf.getvalue(), "chat.zip")
    assert len(whatsapp.parse_whatsapp(text)) == 3
    with pytest.raises(ValueError):
        whatsapp.read_export(b"PK\x03\x04garbage", "x.zip")


# --- SMS Backup XML ---------------------------------------------------------------------


def backup_xml() -> bytes:
    rows = [
        # kept: trusted, inbox, in window, keyword; entities + newline + emoji surrogate pair
        ("AX-HDFCBK-S", ms(2026, 9, 20), "1",
         "Rs.1,499 will be debited on 06-Oct&#10;towards StreamMax &amp; co &#55357;&#56832; &#27;",
         ms(2026, 9, 20, 11, 59)),
        ("VM-SBIUPI-T", ms(2026, 9, 25), "2", "Rs.500 sent to Rahul", 0),  # sent box
        ("AX-OFFERS-P", ms(2026, 9, 25), "1", "Rs.99 recharge offer!", 0),  # promotional
        ("+919876543210", ms(2026, 9, 25), "1", "Pay Rs.200 for pizza", 0),  # phone
        ("JD-ICICIT-G", ms(2026, 6, 1), "1", "EMI due Rs.5000", 0),  # out of window
        ("BZ-KOTAKB-S", ms(2026, 9, 26), "1", "123456 is your OTP for Rs.500 txn", 0),
        ("BZ-KOTAKB-S", ms(2026, 9, 26), "1", "Welcome to Kotak! &#55357;&#56836;", 0),  # no keyword
        ("VM-AIRTEL", ms(2026, 9, 28), "1", "Your bill of Rs.599 is due on 5-Oct", 0),  # legacy header
    ]
    body = "".join(
        f'  <sms protocol="0" address="{a}" date="{d}" type="{t}" subject="null" body="{b}" '
        f'toa="null" sc_toa="null" service_center="null" read="1" status="-1" locked="0" '
        f'date_sent="{ds}" sub_id="1" readable_date="x" contact_name="(Unknown)" />\n'
        for a, d, t, b, ds in rows
    )
    mms = '  <mms date="1" msg_box="1" address="x"><parts><part seq="0" ct="text/plain" text="hi &#55357;&#56832;" /></parts></mms>\n'
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n"
        f'<smses count="{len(rows)}" backup_set="x">\n{body}{mms}</smses>\n'
    ).encode("utf-8")


def test_sms_backup_filters_and_decodes():
    res = sms_backup.parse_sms_backup(backup_xml(), days=60, limit=300, today=TODAY)
    assert res.parse_error is None
    assert res.scanned == 8
    assert res.filtered == {
        "not_inbox": 1, "untrusted_sender": 2, "out_of_window": 1, "otp": 1, "no_keyword": 1,
        "over_limit": 0,
    }
    assert [m.sender for m in res.messages] == ["AX-HDFCBK-S", "VM-AIRTEL"]  # oldest first
    first = res.messages[0]
    assert first.text == "Rs.1,499 will be debited on 06-Oct\ntowards StreamMax & co \U0001f600"
    assert first.received_at == date(2026, 9, 20)
    # dedup ref uses date_sent -> matches the forwarder's sentStamp for the same SMS
    fwd = sms.parse_forwarder_payload(
        {"from": "AX-HDFCBK-S", "text": first.text, "sentStamp": str(ms(2026, 9, 20, 11, 59))}
    )
    assert first.source_ref == fwd.source_ref


def test_sms_backup_limit_keeps_newest():
    res = sms_backup.parse_sms_backup(io.BytesIO(backup_xml()), days=60, limit=1, today=TODAY)
    assert [m.sender for m in res.messages] == ["VM-AIRTEL"]
    assert res.filtered["over_limit"] == 1


def test_sms_backup_truncated_file_keeps_parsed_rows():
    xml = backup_xml()
    cut = xml[: xml.index(b"VM-AIRTEL") - 30]
    res = sms_backup.parse_sms_backup(cut, days=60, limit=300, today=TODAY)
    assert res.parse_error
    assert [m.sender for m in res.messages] == ["AX-HDFCBK-S"]


# --- .eml ---------------------------------------------------------------------------------


def _plain_eml() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "Your SafeRide policy renewal"
    msg["From"] = "SafeRide Insurance <noreply@saferide.example>"
    msg["Date"] = "Tue, 29 Sep 2026 20:30:00 +0000"  # 02:00 IST on 30 Sep
    msg["Message-ID"] = "<abc123@saferide.example>"
    msg.set_content("Premium of Rs 8,450 due by 15 Oct 2026.")
    msg.add_alternative("<p>HTML version should not win</p>", subtype="html")
    return bytes(msg)


def test_eml_plain():
    m = eml.parse_eml(_plain_eml())
    assert m.subject == "Your SafeRide policy renewal"
    assert "SafeRide Insurance" in m.sender
    assert m.received_at == date(2026, 9, 30)
    assert m.source_ref == "<abc123@saferide.example>"
    assert m.body == "Premium of Rs 8,450 due by 15 Oct 2026."


def test_eml_html_only():
    msg = EmailMessage()
    msg["Subject"] = "StreamMax annual plan"
    msg["From"] = "billing@streammax.example"
    msg.set_content(
        "<html><head><style>.x{color:red}</style></head><body><h1>Renewal</h1>"
        "<p>₹1,499 on 6 Oct</p><script>var a=1;</script></body></html>",
        subtype="html",
    )
    raw = bytes(msg)
    m = eml.parse_eml(raw)
    assert m.body == "Renewal\n₹1,499 on 6 Oct"
    assert m.source_ref == hashlib.sha1(raw).hexdigest()
    assert m.received_at is None


# --- endpoints ---------------------------------------------------------------------------


class DummyDB:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class FakePipeline:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, db, **kw):
        self.calls.append(kw)
        body = kw["body"]
        if "BOOM" in body:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        if "debited" in body:
            return ProcessResult(None, False, "signal:debit", 0.95)
        if "DUP" in body:
            return ProcessResult("ob-dup", False, "merged_duplicate", 0.8)
        return ProcessResult(f"ob-{len(self.calls)}", True, "created", 0.9)


@pytest.fixture
def api(monkeypatch):
    pipeline = FakePipeline()
    hook_calls: list[str] = []

    def fake_after_ingest(db, user_id):
        hook_calls.append(user_id)
        return {"edges_linked": 2, "results": "hook-collision"}

    monkeypatch.setattr("app.api.ingest_routes.process_message", pipeline)
    monkeypatch.setattr("app.api.ingest_routes.after_ingest", fake_after_ingest)
    app = FastAPI()
    app.include_router(ingest_routes.router)
    db = DummyDB()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.pipeline = pipeline
    client.hook_calls = hook_calls
    client.db = db
    return client


STATS_KEYS = {"scanned", "created", "merged", "skipped", "signals", "rejected", "errors", "results"}


def _check_invariant(data):
    assert STATS_KEYS <= data.keys()
    assert data["scanned"] == sum(
        data[k] for k in ("created", "merged", "skipped", "signals", "rejected", "errors")
    )


def test_endpoint_sms_accepts_forwarder_template(api):
    payload = {"from": "AX-HDFCBK-S", "text": "StreamMax Rs.1499 on 6 Oct", "sentStamp": str(ms(2026, 9, 29)),
               "receivedStamp": str(ms(2026, 9, 29)), "sim": "SIM1"}
    r = api.post("/api/ingest/sms", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    _check_invariant(data)
    assert data["accepted"] is True and data["sender_reason"] == "trusted_header_S"
    assert data["created"] == 1 and data["edges_linked"] == 2
    assert data["results"][0]["status"] == "created"
    assert data["hook_results"] == "hook-collision"  # hook keys never clobber stats
    call = api.pipeline.calls[0]
    assert call["source_type"] == "sms" and call["sender"] == "AX-HDFCBK-S"
    assert call["received_at"] == date(2026, 9, 29)
    assert call["user_id"] == settings.default_user_id
    assert api.hook_calls == [settings.default_user_id]


def test_endpoint_sms_rejects_promotional_without_pipeline(api):
    r = api.post("/api/ingest/sms", json={"from": "AX-OFFERS-P", "text": "50% off!"})
    data = r.json()
    _check_invariant(data)
    assert data["accepted"] is False and data["sender_reason"] == "promotional_header"
    assert data["rejected"] == 1
    assert api.pipeline.calls == [] and api.hook_calls == []


def test_endpoint_sms_demo_injector_raw_newline_and_errors(api, monkeypatch):
    monkeypatch.setattr(settings, "demo_senders", ["+919876543210"])
    raw = '{"from": "9876543210", "text": "Rs.1499 BOOM\nline two"}'
    r = api.post("/api/ingest/sms", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
    data = r.json()
    _check_invariant(data)
    assert data["sender_reason"] == "demo_sender"
    assert data["errors"] == 1 and "ANTHROPIC_API_KEY" in data["results"][0]["error"]
    assert api.db.rollbacks == 1
    assert api.pipeline.calls[0]["body"] == "Rs.1499 BOOM\nline two"


def test_endpoint_sms_unescaped_quotes_salvaged(api):
    raw = '{"from": "AX-HDFCBK-S", "text": "Pay "now" Rs.10", "sentStamp": "1790658000000", "sim": "x"}'
    r = api.post("/api/ingest/sms", content=raw)
    assert r.status_code == 200, r.text
    assert api.pipeline.calls[0]["body"] == 'Pay "now" Rs.10'
    assert api.post("/api/ingest/sms", content="not json").status_code == 400


def test_endpoint_sms_without_sender_kwarg_support(api, monkeypatch):
    seen = {}

    def old_pipeline(db, *, user_id, source_type, source_ref, body, subject=None, received_at=None):
        seen["ok"] = True
        return ProcessResult("ob-1", True, "created", 0.9)

    monkeypatch.setattr("app.api.ingest_routes.process_message", old_pipeline)
    r = api.post("/api/ingest/sms", json={"from": "HDFCBK", "text": "Rs.1 due"})
    assert r.json()["created"] == 1 and seen["ok"]


def test_endpoint_sms_backup(api):
    files = {"file": ("sms-2026.xml", backup_xml(), "text/xml")}
    r = api.post("/api/ingest/sms-backup?days=60&limit=300", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    _check_invariant(data)
    assert data["scanned"] == 8 and data["rejected"] == 6
    assert data["signals"] == 1 and data["created"] == 1
    assert [c["sender"] for c in api.pipeline.calls] == ["AX-HDFCBK-S", "VM-AIRTEL"]
    assert len(api.hook_calls) == 1
    bad = api.post("/api/ingest/sms-backup", files={"file": ("x.xml", b"<nope", "text/xml")})
    assert bad.status_code == 400


def test_endpoint_whatsapp_txt_and_zip(api):
    r = api.post("/api/ingest/whatsapp", files={"file": ("chat.txt", WA_ANDROID.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    data = r.json()
    _check_invariant(data)
    assert data["scanned"] == 3 and data["created"] == 1 and data["rejected"] == 2
    call = api.pipeline.calls[0]
    assert call["source_type"] == "whatsapp" and "sender" not in call
    assert call["received_at"] == date(2026, 9, 29)
    assert call["body"].startswith("WhatsApp group message from Rahul on 29 Sep 2026:")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_chat.txt", WA_ANDROID)
    r2 = api.post("/api/ingest/whatsapp", files={"file": ("export.zip", buf.getvalue(), "application/zip")})
    assert r2.json()["created"] == 1
    assert len(api.hook_calls) == 2


def test_endpoint_eml_multiple_files(api):
    files = [
        ("files", ("a.eml", _plain_eml(), "message/rfc822")),
        ("files", ("b.eml", b"Subject: DUP renewal\r\n\r\nDUP body Rs.10 due", "message/rfc822")),
    ]
    r = api.post("/api/ingest/eml", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    _check_invariant(data)
    assert data["scanned"] == 2 and data["created"] == 1 and data["merged"] == 1
    first = api.pipeline.calls[0]
    assert first["source_type"] == "email"
    assert first["subject"] == "Your SafeRide policy renewal"
    assert first["source_ref"] == "<abc123@saferide.example>"
    assert first["received_at"] == date(2026, 9, 30)
    assert "Premium of Rs 8,450" in first["body"]
    assert api.pipeline.calls[1]["received_at"] == TODAY  # no Date header -> clock.today()
    assert json.dumps(data)  # serialisable
