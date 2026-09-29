"""Fast-path regex templates for common Indian bank/biller SMS + email shapes.

Handles the ~50% of messages that follow predictable formats. Anything that
doesn't match falls through to the LLM extractor.
"""

import re
from datetime import date, datetime
from typing import Any

import dateparser

# Indian bank SMS: HDFC/ICICI/SBI/AXIS/KOTAK debit alerts
DEBIT_PATTERNS = [
    re.compile(
        r"(?:INR|Rs\.?)\s*([\d,]+\.?\d*)\s+debited",
        re.IGNORECASE,
    ),
    re.compile(
        r"debited\s+(?:by|with|for)\s+(?:INR|Rs\.?)?\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    ),
]

# RBI-mandated e-mandate pre-debit notice
PRE_DEBIT_PATTERNS = [
    re.compile(
        r"(?:mandate|autopay).{0,50}(?:INR|Rs\.?)\s*([\d,]+\.?\d*).{0,50}(?:on|dt\.?)\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Salary credit
SALARY_PATTERNS = [
    re.compile(
        r"(?:salary|sal|payroll).{0,30}credited.{0,30}(?:INR|Rs\.?)\s*([\d,]+\.?\d*)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"credited\s+(?:INR|Rs\.?)\s*([\d,]+\.?\d*).{0,40}(?:salary|sal)",
        re.IGNORECASE | re.DOTALL,
    ),
]

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
        r"policy.{0,50}(?:expires?|expiry).{0,30}(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        re.IGNORECASE | re.DOTALL,
    ),
]


def _clean_amount(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _parse_date(raw: str) -> date | None:
    parsed = dateparser.parse(
        raw,
        settings={"DATE_ORDER": "DMY", "PREFER_DATES_FROM": "future"},
    )
    if isinstance(parsed, datetime):
        return parsed.date()
    return parsed


def try_fast_extract(text: str) -> dict[str, Any] | None:
    """Return a partial obligation dict if a rule matches, else None."""
    text = text.strip()
    if not text:
        return None

    for pat in SALARY_PATTERNS:
        m = pat.search(text)
        if m:
            amt = _clean_amount(m.group(1))
            return {
                "signal_type": "salary_credit",
                "amount": amt,
                "confidence": 0.9,
            }

    for pat in PRE_DEBIT_PATTERNS:
        m = pat.search(text)
        if m:
            return {
                "signal_type": "pre_debit_notice",
                "amount": _clean_amount(m.group(1)),
                "due_date": _parse_date(m.group(2)),
                "confidence": 0.9,
            }

    for pat in DEBIT_PATTERNS:
        m = pat.search(text)
        if m:
            return {
                "signal_type": "debit",
                "amount": _clean_amount(m.group(1)),
                "confidence": 0.85,
            }

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
