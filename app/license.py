"""Signed license (§7.5): offline verification, no phone-home.

Model:
    data/license_public_key.pem   -- shipped with the app, embedded key
    data/license.json             -- optional; user drops this in to unlock updates

license.json shape:
    {
      "payload": {
        "user_id":       "arun@example.com",
        "plan":          "personal" | "family" | "team",
        "issued_at":     "2026-09-30",
        "updates_until": "2027-09-30"
      },
      "signature": "<base64 Ed25519 signature over canonical json.dumps(payload, sort_keys=True)>"
    }

'community' status (no license file) still runs the full engine - only the
update stream (knowledge packs, biller lists) stops. That's the promise in
§7.6: "an unpaid copy slowly gets worse at reading your messages," never
"an unpaid copy stops working."
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.config import ROOT

LICENSE_PATH = ROOT / "data" / "license.json"
PUBLIC_KEY_PATH = ROOT / "data" / "license_public_key.pem"


@dataclass
class LicenseStatus:
    status: str  # "active" | "expired_updates" | "invalid_signature" | "no_public_key" | "community" | "malformed"
    plan: str | None
    user_id: str | None
    updates_until: str | None
    issued_at: str | None
    reason: str | None


def _verify(payload_bytes: bytes, signature_b64: str, public_key_pem: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    try:
        pub = load_pem_public_key(public_key_pem)
        pub.verify(base64.b64decode(signature_b64), payload_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _load_status() -> LicenseStatus:
    if not LICENSE_PATH.exists():
        return LicenseStatus("community", None, None, None, None, "No license file installed.")

    try:
        blob = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
        payload = blob["payload"]
        sig = blob["signature"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        return LicenseStatus("malformed", None, None, None, None, f"Bad license file: {e}")

    if not PUBLIC_KEY_PATH.exists():
        return LicenseStatus(
            "no_public_key",
            payload.get("plan"),
            payload.get("user_id"),
            payload.get("updates_until"),
            payload.get("issued_at"),
            "License public key missing from build.",
        )

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not _verify(canonical, sig, PUBLIC_KEY_PATH.read_bytes()):
        return LicenseStatus(
            "invalid_signature",
            payload.get("plan"),
            payload.get("user_id"),
            payload.get("updates_until"),
            payload.get("issued_at"),
            "Signature failed verification.",
        )

    updates_until_str = payload.get("updates_until")
    try:
        expires = date.fromisoformat(updates_until_str) if updates_until_str else None
    except (TypeError, ValueError):
        expires = None
    if expires and expires < date.today():
        return LicenseStatus(
            "expired_updates",
            payload.get("plan"),
            payload.get("user_id"),
            updates_until_str,
            payload.get("issued_at"),
            f"Update entitlement ended {updates_until_str}. The engine still works; knowledge packs won't refresh.",
        )

    return LicenseStatus(
        "active",
        payload.get("plan"),
        payload.get("user_id"),
        updates_until_str,
        payload.get("issued_at"),
        None,
    )


def status() -> dict[str, Any]:
    s = _load_status()
    return {
        "status": s.status,
        "plan": s.plan,
        "user_id": s.user_id,
        "updates_until": s.updates_until,
        "issued_at": s.issued_at,
        "reason": s.reason,
        "receives_updates": s.status == "active",
    }
