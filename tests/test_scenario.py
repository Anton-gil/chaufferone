"""handoff-v2 §6: the hero demo, end to end through the real API.

Asserts properties of the story (no warning before the pre-debit SMS; a floor clash after
it; option A = pay insurance after the freelance money lands; PUC-on-Sunday accepted;
past-deadline and wrong-order moves rejected; the bank debit SMS verifies the payment),
so an engine change that would break the live demo fails here first.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

TODAY = date(2026, 9, 30)  # Wednesday; pinned via DEMO_TODAY in conftest


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:  # runs the lifespan: alembic migrations + templates
        yield c


def seed(client) -> dict[str, str]:
    r = client.post("/api/demo/scenario")
    assert r.status_code == 200, r.text
    return r.json()["ids"]


def inject(client, which: str) -> dict:
    text = client.get("/api/demo/sample-sms").json()[which]
    r = client.post("/api/demo/inject/sms", json={"from": "AX-HDFCBK-S", "text": text})
    assert r.status_code == 200, r.text
    return r.json()


def planned(client) -> dict[str, dict]:
    plan = client.get("/api/plan").json()
    cards = [c for k in ("today", "week", "later", "needs_check", "verified") for c in plan[k]]
    return {c["id"]: c for c in cards}


def floor_clashes(client) -> list[dict]:
    return [c for c in client.get("/api/money/forecast").json()["clashes"] if c["tier"] == "floor"]


def test_scenario_starts_without_any_warning(client):
    ids = seed(client)
    forecast = client.get("/api/money/forecast").json()
    assert forecast["clashes"] == []
    assert min(d["closing_balance"] for d in forecast["days"]) == 2250

    cards = planned(client)
    assert cards[ids["insurance"]]["planned_on"] == "2026-10-15"  # due 18 - lead 1 - margin 2
    assert cards[ids["puc"]]["planned_on"] == "2026-10-03"  # overdue -> next Saturday
    assert cards[ids["rent"]]["planned_on"] == "2026-10-03"
    assert [n["id"] for n in cards[ids["insurance"]]["needs_first"]] == [ids["puc"]]
    assert client.get("/api/proposal/current").json() is None


def test_pre_debit_sms_opens_a_floor_clash_proposal(client):
    ids = seed(client)
    result = inject(client, "pre_debit")
    assert result["signals"] == 1

    clash = floor_clashes(client)[0]
    assert clash["first_breach_date"] == "2026-10-15"
    assert clash["max_depth_inr"] == 249

    p = client.get("/api/proposal/current").json()
    assert p["status"] == "open"
    a, b = p["options"][:2]
    assert (a["id"], a["kind"], a["obligation_id"], a["new_date"]) == ("A", "defer", ids["insurance"], "2026-10-17")
    assert a["depends_on_income"].startswith("Freelance payment")
    assert (b["id"], b["kind"], b["deadline"]) == ("B", "pause_mandate", "2026-10-05")
    assert "₹249 below your emergency floor" in p["speech"]
    assert "Saturday the 17th" in p["speech"]
    assert "the puc has to come first" in p["speech"].lower()


def test_voice_reply_applies_option_a_with_puc_moved_to_sunday(client):
    ids = seed(client)
    inject(client, "pre_debit")
    r = client.post(
        "/api/voice/turn",
        json={"text": "Go with the first one, but do the PUC on Sunday, I've got a lab on Saturday"},
    ).json()
    assert r["intent"] == "approve", r
    moves = {m["obligation_id"]: m["to"] for m in r["applied_moves"]}
    assert moves == {ids["insurance"]: "2026-10-17", ids["puc"]: "2026-10-04"}
    assert "Nothing touches your floor" in r["speech"]

    assert floor_clashes(client) == []
    cards = planned(client)
    assert cards[ids["insurance"]]["plan_locked"] is True
    assert client.get("/api/proposal/current").json() is None  # clash gone -> proposal closed
    log = client.get("/api/consent-log").json()[0]
    assert log["utterance"].startswith("Go with the first one") and log["intent"] == "approve"


def test_moves_past_the_deadline_or_out_of_order_are_refused(client):
    seed(client)
    inject(client, "pre_debit")
    r = client.post("/api/voice/turn", json={"text": "pay the insurance on the 19th"}).json()
    assert r["intent"] == "rejected_move"
    assert "latest I can do it is Saturday the 17th" in r["speech"]

    r = client.post("/api/voice/turn", json={"text": "first one, and do the PUC on the 18th"}).json()
    assert r["intent"] == "rejected_move"
    assert "has to happen before insurance" in r["speech"]
    assert floor_clashes(client)  # nothing was applied


def test_option_b_pauses_the_mandate(client):
    seed(client)
    inject(client, "pre_debit")
    r = client.post("/api/voice/turn", json={"text": "the second one"}).json()
    assert r["intent"] == "approve"
    assert r["applied_moves"][0]["to"] == "paused"
    assert "UPI app before Monday the 5th" in r["speech"]
    assert floor_clashes(client) == []


def test_unclear_and_rejected_replies_change_nothing(client):
    seed(client)
    inject(client, "pre_debit")
    assert client.post("/api/voice/turn", json={"text": "what's the weather"}).json()["intent"] == "unclear"
    r = client.post("/api/voice/turn", json={"text": "no, leave it"}).json()
    assert r["intent"] == "reject"
    assert floor_clashes(client)


def test_qr_then_bank_debit_sms_verifies_the_gift(client):
    ids = seed(client)
    pay = client.get(f"/api/pay/{ids['gift']}").json()
    assert pay["upi_uri"].startswith("upi://pay?pa=demo.teammate@okaxis&")
    assert "am=500.00" in pay["upi_uri"] and pay["qr_png_b64"]

    result = inject(client, "debit")
    assert result["signals"] == 1
    cards = planned(client)
    assert cards[ids["gift"]]["status"] == "verified"
    plan = client.get("/api/plan").json()
    assert any(c["id"] == ids["gift"] for c in plan["verified"])
    assert plan["money"]["balance_today"] == 2000  # the paid ₹500 came off the anchor balance
    assert floor_clashes(client) == []


def test_snapshot_and_reset_restore_the_demo_start(client):
    ids = seed(client)
    assert client.post("/api/demo/snapshot").status_code == 200
    inject(client, "pre_debit")
    assert floor_clashes(client)
    assert "restored" in client.post("/api/demo/reset").json()
    assert floor_clashes(client) == []
    assert client.get("/api/proposal/current").json() is None
    assert ids["insurance"] in planned(client)
