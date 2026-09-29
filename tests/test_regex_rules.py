"""Deterministic fast-path extractor tests for real-world Indian bank SMS shapes."""

from datetime import date

import pytest

from app.extract.regex_rules import _parse_date, try_fast_extract

SIGNAL_KEYS = {
    "signal_type",
    "amount",
    "due_date",
    "txn_date",
    "payee",
    "vpa",
    "payer",
    "balance",
    "ref",
    "account_last4",
    "confidence",
}

REF = "627312345678"


def _check(result: dict | None, expected: dict) -> None:
    assert result is not None, "expected a signal, got None"
    assert set(result) == SIGNAL_KEYS
    for key, value in expected.items():
        assert result[key] == value, f"{key}: {result[key]!r} != {value!r}\nfull: {result}"
    assert isinstance(result["amount"], float)
    assert 0.8 <= result["confidence"] <= 0.95


# ---------------------------------------------------------------------------
# Debits
# ---------------------------------------------------------------------------

DEBIT_CASES = [
    pytest.param(
        "Sent Rs.500.00\nFrom HDFC Bank A/C *1234\nTo RAHUL K\nOn 30/09/26\nRef 627312345678\n"
        "Not You?\nCall 18002586161/SMS BLOCK UPI to 7308080808",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "vpa": None,
         "ref": REF, "account_last4": "1234"},
        id="hdfc-sent-multiline",
    ),
    pytest.param(
        "Rs.500.00 debited from A/c **1234 on 30-09-26 to VPA rahul@okaxis (UPI Ref No "
        "627312345678). Not you? Call 18002586161 - HDFC Bank",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "rahul@okaxis",
         "vpa": "rahul@okaxis", "ref": REF, "account_last4": "1234"},
        id="hdfc-vpa",
    ),
    pytest.param(
        "Dear UPI user A/C X1234 debited by 500.0 on date 30Sep26 trf to RAHUL K Refno "
        "627312345678. If not u? call 1800111109. -SBI",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "ref": REF,
         "account_last4": "1234"},
        id="sbi-upi",
    ),
    pytest.param(
        "ICICI Bank Acct XX123 debited for Rs 500.00 on 30-Sep-26; RAHUL K credited. "
        "UPI:627312345678. Call 18002662 for dispute. SMS BLOCK 123 to 9215676766.",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "ref": REF,
         "account_last4": "123"},
        id="icici-upi-payee-credited",
    ),
    pytest.param(
        "INR 500.00 debited\nA/c no. XX1234\n30-09-26, 14:22:11\nUPI/P2A/627312345678/RAHUL K\n"
        "Not you? SMS BLOCKUPI Cust ID to 919951860002\nAxis Bank",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "ref": REF,
         "account_last4": "1234"},
        id="axis-upi-multiline",
    ),
    pytest.param(
        "Sent Rs.500.00 from Kotak Bank AC X1234 to rahul@okaxis on 30-09-26.UPI Ref "
        "627312345678. Not you, https://kotak.com/KBANKT/Fraud",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "rahul@okaxis",
         "vpa": "rahul@okaxis", "ref": REF, "account_last4": "1234"},
        id="kotak-sent-vpa",
    ),
    pytest.param(
        "Rs.649.00 spent on HDFC Bank Card x1234 at STREAMMAX on 2026-10-06:10:15:22.Avl bal: "
        "Rs.2701.00.Not you?...",
        {"amount": 649.0, "txn_date": date(2026, 10, 6), "payee": "STREAMMAX",
         "balance": 2701.0, "account_last4": "1234", "ref": None},
        id="hdfc-card-spend",
    ),
    # --- extra real-world variants -------------------------------------------------
    pytest.param(
        "Money Transfer:Rs 500.00 from HDFC Bank A/c **1234 on 30-09-26 to RAHUL K UPI: "
        "627312345678 Not you? Call 18002586161",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "ref": REF,
         "account_last4": "1234"},
        id="hdfc-money-transfer",
    ),
    pytest.param(
        "Update! INR 5,000.00 debited from HDFC Bank XX1234 on 30-SEP-26. Info: "
        "IMPS-627312345678-RAHUL K. Avl bal:INR 12,000.00",
        {"amount": 5000.0, "txn_date": date(2026, 9, 30), "payee": "RAHUL K", "ref": REF,
         "balance": 12000.0, "account_last4": "1234"},
        id="hdfc-imps-update",
    ),
    pytest.param(
        "Dear Customer, Rs.2000 withdrawn at SBI ATM S1ANXX from A/cX1234 on 30Sep26 Txn# 1234. "
        "Avl Bal Rs.10000.00",
        {"amount": 2000.0, "txn_date": date(2026, 9, 30), "payee": "SBI ATM S1ANXX",
         "balance": 10000.0, "account_last4": "1234"},
        id="sbi-atm-withdrawal",
    ),
    pytest.param(
        "INR 649.00 spent using ICICI Bank Card XX1234 on 06-Oct-26 on STREAMMAX. Avl Limit: "
        "INR 49,351.00. If not you, call 1800 2662/SMS BLOCK 1234 to 9215676766",
        {"amount": 649.0, "txn_date": date(2026, 10, 6), "payee": "STREAMMAX", "balance": None,
         "account_last4": "1234"},
        id="icici-card-spend",
    ),
    pytest.param(
        "INR 500.00 debited from A/c no. XX1234 on 30-09-2026 at 14:22:11 IST. "
        "UPI/P2M/627312345678/STREAMMAX. Avl Bal INR 2,000.00",
        {"amount": 500.0, "txn_date": date(2026, 9, 30), "payee": "STREAMMAX", "ref": REF,
         "balance": 2000.0, "account_last4": "1234"},
        id="axis-p2m-single-line",
    ),
    pytest.param(
        "Rs 500.00 debited from a/c XX1234 on 30-09-26 to VPA rahul@okaxis. UPI Ref no "
        "627312345678.",
        {"amount": 500.0, "payee": "rahul@okaxis", "vpa": "rahul@okaxis", "ref": REF,
         "account_last4": "1234"},
        id="kotak-debited-vpa",
    ),
    pytest.param(
        "Paid Rs.500.00 to RAHUL K from Paytm Payments Bank a/c XX1234. UPI Ref: 627312345678.",
        {"amount": 500.0, "payee": "RAHUL K", "ref": REF, "account_last4": "1234"},
        id="paytm-paid",
    ),
    pytest.param(
        "Rs.1499.00 debited from A/c XX1234 for UPI AutoPay mandate towards StreamMax on 06-10-26. "
        "UPI Ref 627312345678 -HDFC Bank",
        {"amount": 1499.0, "txn_date": date(2026, 10, 6), "payee": "StreamMax", "ref": REF,
         "account_last4": "1234"},
        id="executed-autopay-is-debit",
    ),
    pytest.param(
        "Rs.500.00 debited from A/c **1234 on 30-09-26 to VPA rahul@okaxis. Never share OTP/PIN "
        "with anyone. -HDFC Bank",
        {"amount": 500.0, "payee": "rahul@okaxis", "account_last4": "1234"},
        id="debit-with-otp-disclaimer",
    ),
]


@pytest.mark.parametrize(("text", "expected"), DEBIT_CASES)
def test_debit(text, expected):
    result = try_fast_extract(text)
    _check(result, {"signal_type": "debit", "due_date": None, "payer": None, **expected})


# ---------------------------------------------------------------------------
# Pre-debit / mandate notices (must never be "debit")
# ---------------------------------------------------------------------------

PRE_DEBIT_CASES = [
    pytest.param(
        "Dear Customer, Rs.1499.00 will be debited from your HDFC Bank A/c XX1234 on 06-10-2026 "
        "towards StreamMax for UPI AutoPay mandate. To manage, visit the UPI app. -HDFC Bank",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="hdfc-autopay",
    ),
    pytest.param(
        "Your A/c XX1234 will be debited with INR 1,499.00 on 06/10/2026 for e-mandate towards "
        "StreamMax. UMRN HDFC0000012345678. -SBI",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="sbi-emandate",
    ),
    pytest.param(
        "Reminder: Rs 1499.00 will be auto-debited from ICICI Bank Acct XX123 on 06-Oct-26 for "
        "StreamMax via UPI AutoPay.",
        {"payee": "StreamMax", "account_last4": "123"},
        id="icici-auto-debit",
    ),
    pytest.param(
        "UPI AutoPay: Your mandate for StreamMax of Rs.1,499.00 is scheduled for execution on "
        "06-Oct-2026 from A/c XX1234. -Axis Bank",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="axis-scheduled",
    ),
    # --- extra variants -----------------------------------------------------------
    pytest.param(
        "Your A/c XX1234 will be debited for INR 1499.00 on 06-10-2026 towards StreamMax for UPI "
        "Mandate. UMN: a1b2c3d4e5f6@okaxis -Kotak Bank",
        {"payee": "StreamMax", "vpa": None, "account_last4": "1234"},
        id="npci-umn-not-vpa",
    ),
    pytest.param(
        "Upcoming debit: Your ICICI Bank Credit Card XX1234 will be charged INR 1,499.00 on "
        "06-Oct-26 for StreamMax as per the Standing Instruction.",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="icici-card-si",
    ),
    pytest.param(
        "Your SI for StreamMax of Rs 1499.00 is due for debit on 06-10-2026 from A/c XX1234. -SBI",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="sbi-si-due-for-debit",
    ),
    pytest.param(
        "Pre-debit notification: Rs.1,499.00 for StreamMax will be debited on 06 Oct 2026 from "
        "your Kotak Bank a/c X1234 via UPI AutoPay.",
        {"payee": "StreamMax", "account_last4": "1234"},
        id="kotak-pre-debit",
    ),
]


@pytest.mark.parametrize(("text", "expected"), PRE_DEBIT_CASES)
def test_pre_debit(text, expected):
    result = try_fast_extract(text)
    _check(
        result,
        {
            "signal_type": "pre_debit_notice",
            "amount": 1499.0,
            "due_date": date(2026, 10, 6),
            "txn_date": None,
            "confidence": 0.9,
            **expected,
        },
    )


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------

CREDIT_CASES = [
    pytest.param(
        "Rs.10000.00 credited to HDFC Bank A/c XX1234 on 01-10-26 by VPA dad@oksbi (UPI "
        "627312345678). Avl bal: Rs.12500.00",
        {"signal_type": "credit", "amount": 10000.0, "payer": "dad@oksbi", "vpa": "dad@oksbi",
         "balance": 12500.0, "ref": REF, "account_last4": "1234"},
        id="hdfc-credit-vpa",
    ),
    pytest.param(
        "Dear SBI User, your A/c X1234-credited by Rs.10,000 on 01Oct26 transfer from R KUMAR Ref "
        "No 627312345678 -SBI",
        {"signal_type": "credit", "amount": 10000.0, "payer": "R KUMAR", "vpa": None, "ref": REF,
         "account_last4": "1234"},
        id="sbi-credit",
    ),
    pytest.param(
        "Your A/c XX1234 is credited with INR 45,000.00 on 01-10-2026 towards SALARY. Avl Bal INR "
        "57,500.00",
        {"signal_type": "salary_credit", "amount": 45000.0, "balance": 57500.0,
         "account_last4": "1234"},
        id="salary-credit",
    ),
    # --- extra variants -----------------------------------------------------------
    pytest.param(
        "Money Received - INR 10,000.00 in your HDFC Bank A/c xx1234 on 01-10-26 by A/c linked to "
        "VPA dad@oksbi (UPI Ref No 627312345678). Avl bal: INR 12,500.00",
        {"signal_type": "credit", "amount": 10000.0, "payer": "dad@oksbi", "balance": 12500.0,
         "ref": REF, "account_last4": "1234"},
        id="hdfc-money-received",
    ),
    pytest.param(
        "Dear Customer, Acct XX123 is credited with Rs 10,000.00 on 01-Oct-26 from R KUMAR. "
        "UPI:627312345678-ICICI Bank.",
        {"signal_type": "credit", "amount": 10000.0, "payer": "R KUMAR", "ref": REF,
         "account_last4": "123"},
        id="icici-credit",
    ),
    pytest.param(
        "Received Rs.10000.00 in your Kotak Bank AC X1234 from dad@oksbi on 01-10-26.UPI "
        "Ref:627312345678.",
        {"signal_type": "credit", "amount": 10000.0, "payer": "dad@oksbi", "ref": REF,
         "account_last4": "1234"},
        id="kotak-received",
    ),
    pytest.param(
        "Update! INR 45,000.00 deposited in HDFC Bank A/c XX1234 on 01-OCT-26 for NEFT "
        "Cr-ICIC0000001-ACME CORP-SALARY SEP 2026. Avl bal INR 57,500.00",
        {"signal_type": "salary_credit", "amount": 45000.0, "balance": 57500.0,
         "account_last4": "1234"},
        id="hdfc-neft-salary",
    ),
]


@pytest.mark.parametrize(("text", "expected"), CREDIT_CASES)
def test_credit(text, expected):
    result = try_fast_extract(text)
    _check(result, {"txn_date": date(2026, 10, 1), "due_date": None, "payee": None, **expected})


# ---------------------------------------------------------------------------
# Negatives / non-signals
# ---------------------------------------------------------------------------


def test_otp_is_ignored():
    text = (
        "123456 is your OTP for txn of Rs 500.00 at AMAZON. Valid for 10 mins. Do not share. "
        "-HDFC Bank"
    )
    assert try_fast_extract(text) is None
    assert try_fast_extract("Your verification code is 482913. Rs 1 will be debited.") is None


def test_promo_is_not_a_signal():
    assert try_fast_extract("Get 50% off on your next order! Use code SAVE50") is None


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty(text):
    assert try_fast_extract(text) is None


def test_failed_txn_is_not_a_signal():
    text = (
        "Your UPI txn of Rs 500.00 to rahul@okaxis failed. Amount if debited will be credited back "
        "to A/c XX1234 within 3 days."
    )
    result = try_fast_extract(text)
    assert result is None or "signal_type" not in result


def test_policy_renewal_hint_has_no_signal_type():
    text = (
        "Policy renewal reminder\n\nDear Customer, your Star Health policy No. 123456789 expires "
        "on 15/11/2026. Renew now to stay protected."
    )
    result = try_fast_extract(text)
    assert result is not None
    assert "signal_type" not in result
    assert result["obligation_type"] == "renewal"
    assert result["category"] == "insurance"
    assert result["due_date"] == date(2026, 11, 15)


def test_bill_due_hint_has_no_signal_type():
    text = "Your electricity bill of Rs 1,250.00 is due on 15-10-2026. Pay now to avoid late fee."
    result = try_fast_extract(text)
    assert result is not None
    assert "signal_type" not in result
    assert result["obligation_type"] == "payment"
    assert result["amount"] == 1250.0
    assert result["due_date"] == date(2026, 10, 15)


def test_sender_argument_is_accepted():
    text = "Rs.500.00 debited from A/c **1234 on 30-09-26 to VPA rahul@okaxis. -HDFC Bank"
    assert try_fast_extract(text, sender="VM-HDFCBK")["signal_type"] == "debit"
    assert try_fast_extract(text, None)["signal_type"] == "debit"


# ---------------------------------------------------------------------------
# Dates (Indian D/M/Y)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("06-10-2026", date(2026, 10, 6)),
        ("06/10/26", date(2026, 10, 6)),
        ("06-10-26", date(2026, 10, 6)),
        ("06-Oct-26", date(2026, 10, 6)),
        ("06-Oct-2026", date(2026, 10, 6)),
        ("06 Oct 2026", date(2026, 10, 6)),
        ("30Sep26", date(2026, 9, 30)),
        ("30SEP2026", date(2026, 9, 30)),
        ("2026-10-06", date(2026, 10, 6)),
        ("6 October 2026", date(2026, 10, 6)),
    ],
)
def test_parse_date_dmy(raw, expected):
    assert _parse_date(raw) == expected
