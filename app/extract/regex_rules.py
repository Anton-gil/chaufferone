"""Fast-path regex templates for common Indian bank/biller SMS + email shapes.

Deterministic (no LLM). Covers HDFC / SBI / ICICI / Axis / Kotak style UPI,
IMPS, card-spend, ATM and e-mandate / UPI AutoPay alerts. Anything that doesn't
match falls through to the LLM extractor.

Return contract (consumed by ``app.extract.pipeline``):

* dict WITH ``signal_type`` -> bank signal, one of
  ``pre_debit_notice`` | ``salary_credit`` | ``debit`` | ``credit``.
  Keys: signal_type, amount, due_date, txn_date, payee, vpa, payer, balance,
  ref, account_last4, confidence.
* dict WITHOUT ``signal_type`` -> bill-due / policy-renewal hint (LLM handles it)
* ``None`` -> no match, or an OTP message (ignored entirely)

Classification priority:
  OTP (ignore) > pre-debit / mandate notice (future tense) > salary credit
  > debit / credit (whichever cue appears first in the text).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import dateparser

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_CUR = r"(?:INR|Rs|₹)\.?"
_AMT = r"\d[\d,]*(?:\.\d{1,2})?"

# "Rs.500.00", "INR 1,499.00", "Rs 1499", "₹500"
_CUR_AMT_RE = re.compile(r"(?<![A-Za-z])" + _CUR + r"\s*(?P<amt>" + _AMT + ")", re.I)

# "debited by 500.0" (SBI, no currency), "credited with INR 45,000.00", "debited for Rs 500"
_VERB_AMT_RE = re.compile(
    r"\b(?:debited|credited|deducted|deposited)\s+(?:by|with|for|of)\s+"
    r"(?:" + _CUR + r"\s*)?(?P<amt>" + _AMT + ")",
    re.I,
)

# "Avl bal: Rs.2701.00", "Avl Bal INR 57,500.00", "Available Balance Rs.10000", "Bal:Rs.5"
_BAL_RE = re.compile(
    r"(?:\bAvb?l\.?\s*|\bAvailable\s+|\bClosing\s+|\b)Bal(?:ance)?\b\.?"
    r"\s*(?:is\s*)?[:\-]?\s*(?:" + _CUR + r"\s*)?:?\s*(?P<amt>" + _AMT + ")",
    re.I,
)

# Card limits are not balances and not the txn amount.
_LIMIT_RE = re.compile(
    r"\b(?:Avb?l\.?|Available)\s*(?:Cr(?:edit)?\.?\s*)?(?:Lmt|Limit)\b\.?"
    r"\s*(?:is\s*)?[:\-]?\s*(?:" + _CUR + r"\s*)?(?P<amt>" + _AMT + ")",
    re.I,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON = (
    r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# Indian D/M/Y dates: 06-10-2026, 06/10/26, 06-Oct-26, 06 Oct 2026, 30Sep26,
# 30SEP2026, and ISO 2026-10-06 (also 2026-10-06:10:15:22).
_DATE_RE = re.compile(
    r"(?<!\d)(?:"
    r"(?P<iy>\d{4})-(?P<im>\d{1,2})-(?P<id>\d{1,2})"
    r"|(?P<d1>\d{1,2})[-/.](?P<m1>\d{1,2})[-/.](?P<y1>\d{4}|\d{2})"
    r"|(?P<d2>\d{1,2})(?:st|nd|rd|th)?[-\s/]?" + _MON + r"(?![a-z])\.?[-\s/,]*(?P<y2>\d{4}|\d{2})"
    r")(?!\d)",
    re.I,
)

# UPI VPA: rahul@okaxis. Not emails (handle part must not continue with ".tld").
_VPA_RE = re.compile(r"(?<![\w.\-@])(?P<vpa>[A-Za-z0-9][\w.\-]*@[A-Za-z][A-Za-z0-9]+)(?![\w@\-]|\.\w)")
# Mandate identifiers look like VPAs ("UMN: abc123@okaxis") but are not payees.
_VPA_EXCLUDE_BEFORE_RE = re.compile(
    r"(?:\bUMN|\bUMRN|\bMandate\s*(?:ID|Ref|No)\.?)\s*[:\-]?\s*$", re.I
)

# Masked account / card: "A/C *1234", "A/c **1234", "A/C X1234", "Acct XX123",
# "A/c no. XX1234", "AC X1234", "Card x1234", "A/cX1234", "Card ending 1234".
_ACCT_RES = [
    re.compile(
        r"(?:\bA/c|\bAcct|\bAccount|\bAC|\bCard)(?:\s*(?:no|number)\.?)?"
        r"(?:\s*ending(?:\s+(?:with|in))?)?\s*[:\-]?\s*[Xx*]*(?P<d>\d{3,6})(?!\d)",
        re.I,
    ),
    re.compile(r"(?<![A-Za-z0-9])[Xx*]+(?P<d>\d{3,6})(?!\d)"),
]

# UPI ref / RRN / UTR (10-12 digits)
_REF_RES = [
    re.compile(r"\b(?:UPI|IMPS|NEFT|RTGS)[/-](?:P2[AM][/-])?(?P<ref>\d{10,12})(?!\d)", re.I),
    re.compile(
        r"\b(?:UPI\s*)?(?:Ref(?:erence)?|RRN|UTR|Txn\s*(?:ID|No)?|Transaction\s*(?:ID|No|Number))"
        r"\.?\s*(?:No\.?|Number|ID)?\s*(?:is\s*)?[:#\-]?\s*(?P<ref>\d{10,12})(?!\d)",
        re.I,
    ),
    re.compile(r"\bUPI\s*[:\-]?\s*(?P<ref>\d{10,12})(?!\d)", re.I),
]

# ---------------------------------------------------------------------------
# Classification cues
# ---------------------------------------------------------------------------

# OTP messages are ignored entirely. "Never share OTP/PIN" disclaimers inside a
# real debit alert are stripped first so they don't suppress the alert.
_OTP_DISCLAIMER_RE = re.compile(
    r"(?:never|do\s+not|don'?t|dont|pls\s+do\s+not)\s+share\s+(?:your\s+|the\s+|this\s+|any\s+)?"
    r"(?:(?:OTP|PIN|CVV|password|passcode|card\s+details)\s*(?:[/,]|\s+or\s+|\s+and\s+)?\s*)+",
    re.I,
)
_OTP_RE = re.compile(
    r"\bOTP\b|\bone[\s-]?time[\s-]?pass(?:word|code)\b|\bverification\s+code\b", re.I
)

# Future-tense debit wording => pre-debit notice even though "debited" appears.
_STRONG_FUTURE_RE = re.compile(
    r"\b(?:will|shall|would)\s+(?:be|get)\s+(?:auto[\s-]?)?(?:debited|deducted|charged)\b"
    r"|\bto\s+be\s+(?:auto[\s-]?)?(?:debited|deducted|charged)\b"
    r"|\bdue\s+for\s+(?:auto[\s-]?)?(?:debit|deduction)\b"
    r"|\bupcoming\s+(?:auto[\s-]?)?(?:debit|deduction|mandate|autopay|auto\s*pay)\b"
    r"|\bpre[\s-]?debit\b",
    re.I,
)
# Weaker future cues that only count alongside a mandate keyword.
_WEAK_FUTURE_RE = re.compile(
    r"\bscheduled\b|\bwill\s+be\s+(?:processed|executed|presented|paid|collected)\b"
    r"|\bdue\s+(?:on|by)\b|\breminder\b|\bnext\s+(?:debit|payment|due)\b|\bupcoming\b",
    re.I,
)
_MANDATE_RE = re.compile(
    r"\bauto[\s-]?pay\b|\be-?mandate\b|\bmandate\b|\bstanding\s+instruction\b|(?-i:\bSI\b)"
    r"|\be-?NACH\b|(?-i:\bECS\b)|\bauto[\s-]?debit\b|\bUMRN\b",
    re.I,
)
# Mandate admin messages (created / revoked / failed) are not pre-debit notices.
_MANDATE_ADMIN_RE = re.compile(
    r"\b(?:created|registered|set\s*up|revoked|cancell?ed|paused|resumed|modified|declined"
    r"|failed|unsuccessful|rejected)\b",
    re.I,
)

# Past-tense debit cues.
_DEBIT_CUE_RE = re.compile(
    r"\bdebited\b|\bspent\b|\bwithdrawn\b|\bsent\s+" + _CUR + r"|\btrf\s+to\b"
    r"|\btransferred\s+to\b|\bdeducted\b|\bused\s+for\s+(?:a\s+)?(?:txn|transaction)\b"
    r"|(?-i:\bDR\b)|\bdebit\s+of\s+" + _CUR
    + r"|" + _CUR + r"\s*" + _AMT + r"\s+(?:has\s+been\s+)?from\s+(?:your\s+)?(?:[\w&]+\s+){0,3}"
    r"(?:A/c|Acct|Account|AC|Card)\b",
    re.I,
)
# "paid" is only a debit cue with an amount/payee attached and a bank context.
_WEAK_DEBIT_CUE_RE = re.compile(
    r"\bpaid\s+(?:" + _CUR + r"|to\b)"
    r"|" + _CUR + r"\s*" + _AMT + r"\s+(?:has\s+been\s+|was\s+|is\s+)?paid\b"
    r"|\bpayment\s+of\s+" + _CUR + r"\s*" + _AMT + r"\s+(?:\w+\s+){0,4}?(?:is\s+|was\s+|has\s+been\s+)?"
    r"(?:successful(?:ly)?|done|made|completed)\b",
    re.I,
)
_CREDIT_CUE_RE = re.compile(
    r"\bcredited\b|\bdeposited\b|\brefunded\b|\breversed\b|(?-i:\bCR\b)"
    r"|\bcredit\s+of\s+" + _CUR + r"|\breceived\s+" + _CUR,
    re.I,
)
_WEAK_CREDIT_CUE_RE = re.compile(r"\breceived\b", re.I)

_FAILED_RE = re.compile(
    r"\b(?:failed|declined|unsuccessful|rejected|could\s+not\s+be\s+processed)\b", re.I
)
_FUTURE_CREDIT_RE = re.compile(r"\bwill\s+be\s+(?:credited|refunded|reversed)\b", re.I)
_SALARY_RE = re.compile(r"\b(?:salary|sal|payroll|wages|stipend)\b", re.I)

_BANK_SENDER_RE = re.compile(
    r"HDFC|ICICI|SBI|AXIS|KOTAK|KMB|BOB|PNB|YESB|IDFC|INDUS|CANARA|CNRB|UNION|BOI|FEDRL|FEDBNK"
    r"|AUBANK|PAYTM|IPPB|BANK",
    re.I,
)

# ---------------------------------------------------------------------------
# Payee / payer name patterns
# ---------------------------------------------------------------------------

_NAME = r"(?P<name>[A-Za-z][^\n;,()]{0,60}?)"
_NAME_END = (
    r"(?=\s+(?:on|via|of|as|using|through|from|for|with|is|was|has|will|dated|towards|Ref(?:no)?|UPI|IMPS"
    r"|UMRN|UMN|Avl|if|at|by|not)\b"
    r"|\s*[,;(\n]|\.(?:\s|$|(?-i:[A-Z]))|\s*$)"
)


def _name_re(prefix: str) -> re.Pattern[str]:
    return re.compile(prefix + _NAME + _NAME_END, re.I)


# "UPI/P2A/627312345678/RAHUL K", "Info: IMPS-627312345678-RAHUL K."
_RAIL_NAME_RE = re.compile(
    r"\b(?:UPI|IMPS|NEFT|RTGS)[/-](?:P2[AM][/-])?\d{6,16}[/-]"
    r"(?P<name>[A-Za-z][^\n/;,()]{0,60}?)(?=\s*[/\n]|\.(?:\s|$)|\s*$)",
    re.I,
)

_DEBIT_PAYEE_RES = [
    re.compile(r"(?m)^[ \t]*To[ \t]+(?P<name>[A-Za-z][^\n]{0,60}?)[ \t]*$"),  # HDFC multi-line
    re.compile(r";\s*(?P<name>[A-Za-z][^;\n]{0,60}?)\s+credited\b", re.I),  # ICICI "; X credited"
    _RAIL_NAME_RE,
    _name_re(r"\btrf\s+to\s+"),
    _name_re(r"\btransferred\s+to\s+(?:VPA\s+)?"),
    _name_re(r"\bat\s+"),
    _name_re(r"\btowards\s+"),
    _name_re(r"\bto\s+(?:VPA\s+|beneficiary\s+)?"),
    _name_re(r"(?<=\d)\s+on\s+"),  # ICICI card: "on 06-Oct-26 on STREAMMAX"
]

_PREDEBIT_PAYEE_RES = [
    _name_re(r"\btowards\s+"),
    _name_re(
        r"\b(?:mandate|autopay|auto\s*pay|SI|standing\s+instruction|e-?NACH)\s+"
        r"(?:for|of|towards|to)\s+"
    ),
    _name_re(r"\bfor\s+"),
    _name_re(r"\bat\s+"),
    _name_re(r"\bto\s+(?:VPA\s+)?"),
]

_PAYER_RES = [
    _RAIL_NAME_RE,
    _name_re(r"\btransfer\s+from\s+"),
    _name_re(r"\bfrom\s+(?:VPA\s+)?"),
    _name_re(r"\bby\s+(?:VPA\s+)?"),
    re.compile(r";\s*(?P<name>[A-Za-z][^;\n]{0,60}?)\s+debited\b", re.I),
]

_NAME_STOP_RE = re.compile(
    r"^(?:your|the|a/c|ac|acct|account|vpa|upi|imps|neft|rtgs|mandate|e-?mandate|autopay|auto\s*pay"
    r"|rs|inr|execution|dispute|txn|transaction|mobile|beneficiary|si|nach|e-?nach|ecs|emi|payment"
    r"|debit|credit|you|date|this|any|us|linked|ref|block|report|avoid|manage|stop|know|check"
    r"|raise|register|unsubscribe|details|more)\b",
    re.I,
)
_NAME_BAD_RE = re.compile(r"\b(?:A/c|Acct|Account|Card)\b|[Xx*]+\d{3}|@", re.I)

# ---------------------------------------------------------------------------
# Legacy hint patterns (no signal_type) — behaviour unchanged
# ---------------------------------------------------------------------------

# Bill due
BILL_DUE_PATTERNS = [
    re.compile(
        r"(?:bill|invoice|amount).{0,30}(?:INR|Rs\.?)\s*([\d,]+\.?\d*).{0,30}due\s+(?:on|by|dt\.?)\s*(\d{1,2}[-/\s][A-Za-z]{3,9}[-/\s]?\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Insurance / policy renewal
POLICY_RENEWAL_PATTERNS = [
    re.compile(
        # lazy gap + digit boundary: greedy ".{0,30}" used to eat the day's first digit
        r"policy.{0,50}(?:expires?|expiry).{0,30}?(?<!\d)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        re.IGNORECASE | re.DOTALL,
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_amount(raw: str | None) -> float | None:
    try:
        return float(raw.replace(",", "").strip())  # type: ignore[union-attr]
    except (ValueError, AttributeError):
        return None


def _date_from_match(m: re.Match[str]) -> date | None:
    try:
        if m.group("iy"):
            y, mo, d = int(m.group("iy")), int(m.group("im")), int(m.group("id"))
        elif m.group("d1"):
            d, mo, y = int(m.group("d1")), int(m.group("m1")), int(m.group("y1"))
        else:
            d = int(m.group("d2"))
            mo = _MONTHS[m.group("mon")[:3].lower()]
            y = int(m.group("y2"))
        if y < 100:
            y += 2000
        return date(y, mo, d)
    except (ValueError, KeyError, TypeError):
        return None


def _parse_date(raw: str | None) -> date | None:
    """Parse an Indian D/M/Y date. Explicit formats first, dateparser as fallback."""
    if not raw:
        return None
    raw = raw.strip()
    m = _DATE_RE.fullmatch(raw)
    if m:
        parsed = _date_from_match(m)
        if parsed:
            return parsed
    parsed_dt = dateparser.parse(
        raw,
        settings={"DATE_ORDER": "DMY", "PREFER_DATES_FROM": "future"},
    )
    if isinstance(parsed_dt, datetime):
        return parsed_dt.date()
    return parsed_dt


def _find_dates(text: str) -> list[tuple[int, date]]:
    out: list[tuple[int, date]] = []
    for m in _DATE_RE.finditer(text):
        d = _date_from_match(m)
        if d:
            out.append((m.start(), d))
    return out


def _is_otp(text: str) -> bool:
    return bool(_OTP_RE.search(_OTP_DISCLAIMER_RE.sub(" ", text)))


def _account_last4(text: str) -> str | None:
    for rx in _ACCT_RES:
        m = rx.search(text)
        if m:
            return m.group("d")[-4:]
    return None


def _find_vpa(text: str) -> str | None:
    for m in _VPA_RE.finditer(text):
        if _VPA_EXCLUDE_BEFORE_RE.search(text[max(0, m.start() - 20) : m.start()]):
            continue
        return m.group("vpa")
    return None


def _find_ref(text: str) -> str | None:
    for rx in _REF_RES:
        m = rx.search(text)
        if m:
            return m.group("ref")
    return None


def _find_balance(text: str) -> float | None:
    m = _BAL_RE.search(text)
    return _clean_amount(m.group("amt")) if m else None


def _txn_amount(text: str) -> float | None:
    """Transaction amount: verb-anchored first, else first currency amount that
    isn't a balance or card limit."""
    m = _VERB_AMT_RE.search(text)
    if m:
        amt = _clean_amount(m.group("amt"))
        if amt is not None:
            return amt
    excluded = {mm.start("amt") for rx in (_BAL_RE, _LIMIT_RE) for mm in rx.finditer(text)}
    for mm in _CUR_AMT_RE.finditer(text):
        if mm.start("amt") in excluded:
            continue
        amt = _clean_amount(mm.group("amt"))
        if amt is not None:
            return amt
    return None


def _clean_name(raw: str | None) -> str | None:
    if not raw:
        return None
    name = re.sub(r"\s+", " ", raw).strip(" .:-/")
    if not 2 <= len(name) <= 50:
        return None
    if not re.search(r"[A-Za-z]", name):
        return None
    if _NAME_STOP_RE.match(name) or _NAME_BAD_RE.search(name):
        return None
    return name


def _find_name(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for rx in patterns:
        for m in rx.finditer(text):
            name = _clean_name(m.group("name"))
            if name:
                return name
    return None


def _pre_debit_cue(text: str) -> tuple[int, float] | None:
    """Return (cue_position, confidence) if this is a pre-debit / mandate notice."""
    strong = _STRONG_FUTURE_RE.search(text)
    if strong:
        return strong.start(), 0.9
    if not _MANDATE_RE.search(text):
        return None
    if _DEBIT_CUE_RE.search(text) or _CREDIT_CUE_RE.search(text):
        return None  # executed mandate debit (past tense) -> handled as debit
    weak = _WEAK_FUTURE_RE.search(text)
    if weak:
        return weak.start(), 0.9
    if _MANDATE_ADMIN_RE.search(text):
        return None
    if _find_dates(text):
        return 0, 0.85  # bare "AutoPay ... Rs X on <date>" notice
    return None


def _direction(text: str, bank_ctx: bool) -> str | None:
    hits: list[tuple[int, str]] = []
    for rx, kind, needs_ctx in (
        (_DEBIT_CUE_RE, "debit", False),
        (_WEAK_DEBIT_CUE_RE, "debit", True),
        (_CREDIT_CUE_RE, "credit", False),
        (_WEAK_CREDIT_CUE_RE, "credit", True),
    ):
        if needs_ctx and not bank_ctx:
            continue
        m = rx.search(text)
        if m:
            hits.append((m.start(), kind))
    return min(hits)[1] if hits else None


def _signal(
    signal_type: str,
    amount: float,
    *,
    confidence: float,
    due_date: date | None = None,
    txn_date: date | None = None,
    payee: str | None = None,
    vpa: str | None = None,
    payer: str | None = None,
    balance: float | None = None,
    ref: str | None = None,
    account_last4: str | None = None,
) -> dict[str, Any]:
    return {
        "signal_type": signal_type,
        "amount": amount,
        "due_date": due_date,
        "txn_date": txn_date,
        "payee": payee,
        "vpa": vpa,
        "payer": payer,
        "balance": balance,
        "ref": ref,
        "account_last4": account_last4,
        "confidence": confidence,
    }


def _extract_signal(text: str, sender: str | None) -> dict[str, Any] | None:
    acct = _account_last4(text)
    vpa = _find_vpa(text)
    ref = _find_ref(text)
    balance = _find_balance(text)
    dates = _find_dates(text)
    bank_ctx = bool(acct or vpa or ref or (sender and _BANK_SENDER_RE.search(sender)))

    # 1. Pre-debit / mandate notice (future tense) — never a debit.
    cue = _pre_debit_cue(text)
    if cue is not None:
        cue_pos, conf = cue
        amount = _txn_amount(text)
        if amount is None:
            return None
        due = next((d for pos, d in dates if pos >= cue_pos), None)
        if due is None and dates:
            due = dates[0][1]
        return _signal(
            "pre_debit_notice",
            amount,
            confidence=conf,
            due_date=due,
            payee=_find_name(text, _PREDEBIT_PAYEE_RES) or vpa,
            vpa=vpa,
            balance=balance,
            ref=ref,
            account_last4=acct,
        )

    if _FAILED_RE.search(text) or _FUTURE_CREDIT_RE.search(text):
        return None

    direction = _direction(text, bank_ctx)
    if direction is None:
        return None
    amount = _txn_amount(text)
    if amount is None:
        return None

    txn_date = dates[0][1] if dates else None
    conf = 0.9 if (acct and txn_date) else 0.85
    common = {
        "txn_date": txn_date,
        "vpa": vpa,
        "balance": balance,
        "ref": ref,
        "account_last4": acct,
    }

    # 2. Salary before generic credit.
    if direction == "credit":
        payer = vpa or _find_name(text, _PAYER_RES)
        if _SALARY_RE.search(text):
            return _signal("salary_credit", amount, confidence=0.9, payer=payer, **common)
        return _signal("credit", amount, confidence=conf, payer=payer, **common)

    # 3. Debit.
    payee = vpa or _find_name(text, _DEBIT_PAYEE_RES)
    return _signal("debit", amount, confidence=conf, payee=payee, **common)


def _extract_hint(text: str) -> dict[str, Any] | None:
    for pat in BILL_DUE_PATTERNS:
        m = pat.search(text)
        if m:
            return {
                "obligation_type": "payment",
                "amount": _clean_amount(m.group(1)),
                "due_date": _parse_date(m.group(2)),
                "confidence": 0.75,
            }

    for pat in POLICY_RENEWAL_PATTERNS:
        m = pat.search(text)
        if m:
            return {
                "obligation_type": "renewal",
                "category": "insurance",
                "due_date": _parse_date(m.group(1)),
                "confidence": 0.75,
            }
    return None


def try_fast_extract(text: str, sender: str | None = None) -> dict[str, Any] | None:
    """Deterministically classify a bank SMS/email.

    Returns a signal dict (with ``signal_type``), a bill/policy hint dict
    (without ``signal_type``), or ``None`` (no match / OTP).
    """
    if not text:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return None

    if _is_otp(text):
        return None

    signal = _extract_signal(text, sender)
    if signal:
        return signal
    return _extract_hint(text)
