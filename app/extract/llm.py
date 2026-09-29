"""Groq extraction stage.

Two-stage pipeline: a small model triages (is this an obligation?), a bigger
one extracts structured fields. Uses OpenAI-compatible tool calling to enforce
the schema.

Groq exposes an OpenAI-shaped API; we use its official SDK which is a thin
wrapper over that. Swap in another OpenAI-compatible provider by changing the
client and the model IDs — the tool schemas below are portable.
"""

from __future__ import annotations

import json
from typing import Any

from groq import Groq
from pydantic import ValidationError

from app.config import settings
from app.network_log import log_outbound
from app.schemas.obligation import ExtractedObligation, TriageDecision

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = Groq(api_key=settings.groq_api_key)
    return _client


TRIAGE_SYSTEM = (
    "You classify short text as containing (or not) a financial or life-admin obligation. "
    "An obligation is anything the user owes by a specific time: a bill, a renewal, a "
    "document expiry, an appointment, an assignment, an RSVP with money or time attached. "
    "Return JSON only. Do not guess if unsure."
)

TRIAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "record_triage",
        "description": "Record whether the message contains an obligation.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_obligation": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "category_hint": {
                    "type": "string",
                    "description": "utility|insurance|subscription|government|health|vehicle|education|financial|appointment|other",
                },
            },
            "required": ["is_obligation", "confidence"],
        },
    },
}

EXTRACT_SYSTEM = (
    "You extract a single structured obligation from an email or SMS body. "
    "Be precise. Use null for missing fields. Do not hallucinate amounts or dates. "
    "If the message is a reminder about an obligation, extract the underlying obligation "
    "(not the reminder itself). Currency defaults to INR unless another is stated."
)

EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_obligation",
        "description": "Record the structured obligation extracted from the message.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "vendor": {"type": ["string", "null"]},
                "category": {"type": ["string", "null"]},
                "obligation_type": {
                    "type": "string",
                    "enum": ["payment", "document", "task", "event", "renewal"],
                },
                "amount": {"type": ["number", "null"]},
                "currency": {"type": "string"},
                "due_date": {
                    "type": ["string", "null"],
                    "description": "ISO YYYY-MM-DD",
                },
                "lead_time_days": {"type": ["integer", "null"]},
                "flexibility_window_days": {"type": ["integer", "null"]},
                "penalty_type": {
                    "type": ["string", "null"],
                    "enum": ["late_fee", "service_cutoff", "legal", "credit_impact", "expiry", "none", None],
                },
                "penalty_amount": {"type": ["number", "null"]},
                "penalty_description": {"type": ["string", "null"]},
                "auto_pay": {"type": ["boolean", "null"]},
                "action_required": {"type": ["string", "null"]},
                "urgency": {
                    "type": ["string", "null"],
                    "enum": ["low", "medium", "high", "critical", None],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["title", "obligation_type", "currency", "confidence"],
        },
    },
}


def _tool_arguments(response: Any, tool_name: str) -> dict[str, Any] | None:
    """Pull the first matching tool call's parsed JSON arguments."""
    choice = response.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None) or []
    for call in tool_calls:
        fn = getattr(call, "function", None)
        if fn is not None and getattr(fn, "name", None) == tool_name:
            raw = fn.arguments or "{}"
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return None
    return None


def triage(message: str) -> TriageDecision:
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.groq_triage_model,
            max_tokens=200,
            temperature=0,
            tools=[TRIAGE_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_triage"}},
            messages=[
                {"role": "system", "content": TRIAGE_SYSTEM},
                {"role": "user", "content": message[:4000]},
            ],
        )
    except Exception as e:
        log_outbound("api.groq.com", "llm.triage", ok=False, reason=f"{type(e).__name__}: {e}"[:200])
        raise
    log_outbound("api.groq.com", "llm.triage")
    payload = _tool_arguments(resp, "record_triage") or {}
    return TriageDecision(
        is_obligation=bool(payload.get("is_obligation", False)),
        confidence=float(payload.get("confidence", 0)),
        category_hint=payload.get("category_hint"),
    )


def extract(message: str, category_hint: str | None = None) -> ExtractedObligation | None:
    client = _get_client()
    hint = f"\n\nCategory hint from triage: {category_hint}" if category_hint else ""
    try:
        resp = client.chat.completions.create(
            model=settings.groq_extract_model,
            max_tokens=800,
            temperature=0,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_obligation"}},
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM + hint},
                {"role": "user", "content": message[:8000]},
            ],
        )
    except Exception as e:
        log_outbound("api.groq.com", "llm.extract", ok=False, reason=f"{type(e).__name__}: {e}"[:200])
        raise
    log_outbound("api.groq.com", "llm.extract")
    payload = _tool_arguments(resp, "record_obligation")
    if not payload:
        return None
    # Coerce nullable ints back to the pydantic default so unknown values don't
    # trip validation. The tool schema allows null so Groq's server accepts the
    # model's output; pydantic still wants int on this side.
    for k in ("lead_time_days", "flexibility_window_days"):
        if payload.get(k) is None:
            payload.pop(k, None)
    try:
        return ExtractedObligation.model_validate(payload)
    except ValidationError:
        return None
