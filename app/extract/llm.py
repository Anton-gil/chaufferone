"""Claude Sonnet extraction stage.

Two-stage pipeline: Haiku triages (is this an obligation?), Sonnet extracts
structured fields. Uses Anthropic's tool-use / JSON mode to enforce schema.

Note per handoff.md §8: for the demo we call the hosted API. The interface
here is drop-in replaceable with a local Ollama call later.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic
from pydantic import ValidationError

from app.config import settings
from app.schemas.obligation import ExtractedObligation, TriageDecision

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


TRIAGE_SYSTEM = (
    "You classify short text as containing (or not) a financial or life-admin obligation. "
    "An obligation is anything the user owes by a specific time: a bill, a renewal, a "
    "document expiry, an appointment, an assignment, an RSVP with money or time attached. "
    "Return JSON only. Do not guess if unsure."
)

TRIAGE_TOOL = {
    "name": "record_triage",
    "description": "Record whether the message contains an obligation.",
    "input_schema": {
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
}

EXTRACT_SYSTEM = (
    "You extract a single structured obligation from an email or SMS body. "
    "Be precise. Use null for missing fields. Do not hallucinate amounts or dates. "
    "If the message is a reminder about an obligation, extract the underlying obligation "
    "(not the reminder itself). Currency defaults to INR unless another is stated."
)

EXTRACT_TOOL = {
    "name": "record_obligation",
    "description": "Record the structured obligation extracted from the message.",
    "input_schema": {
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
            "lead_time_days": {"type": "integer"},
            "flexibility_window_days": {"type": "integer"},
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
}


def _tool_input(response: Any, tool_name: str) -> dict[str, Any] | None:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            return block.input
    return None


def triage(message: str) -> TriageDecision:
    client = _get_client()
    resp = client.messages.create(
        model=settings.anthropic_triage_model,
        max_tokens=200,
        system=TRIAGE_SYSTEM,
        tools=[TRIAGE_TOOL],
        tool_choice={"type": "tool", "name": "record_triage"},
        messages=[{"role": "user", "content": message[:4000]}],
    )
    payload = _tool_input(resp, "record_triage") or {}
    return TriageDecision(
        is_obligation=bool(payload.get("is_obligation", False)),
        confidence=float(payload.get("confidence", 0)),
        category_hint=payload.get("category_hint"),
    )


def extract(message: str, category_hint: str | None = None) -> ExtractedObligation | None:
    client = _get_client()
    hint = f"\n\nCategory hint from triage: {category_hint}" if category_hint else ""
    resp = client.messages.create(
        model=settings.anthropic_extract_model,
        max_tokens=800,
        system=EXTRACT_SYSTEM + hint,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "record_obligation"},
        messages=[{"role": "user", "content": message[:8000]}],
    )
    payload = _tool_input(resp, "record_obligation")
    if not payload:
        return None
    try:
        return ExtractedObligation.model_validate(payload)
    except ValidationError:
        try:
            return ExtractedObligation.model_validate(json.loads(json.dumps(payload)))
        except (ValidationError, TypeError):
            return None
