"""Gmail read-only ingest. OAuth with gmail.readonly scope."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings
from app.network_log import log_outbound

# Local dev: Google accepts http://localhost redirect URIs but the oauthlib client
# refuses non-HTTPS callbacks unless this is set. Guarded so prod (https://) is unaffected.
if settings.google_redirect_uri.startswith("http://"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
# Google may return extra scopes (openid/email/profile) if the account is already
# signed in via NextAuth on the same client; without this, oauthlib raises
# "Scope has changed" on fetch_token.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    received_at: datetime
    body_text: str


def _client_config() -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def make_flow() -> Flow:
    # PKCE is disabled because the callback is stateless: google_start and
    # google_callback each build a fresh Flow, so the auto-generated code_verifier
    # from step 1 is lost by step 3 and Google rejects the token exchange.
    # We are a confidential "web" client (client_secret authenticates the app),
    # so PKCE isn't required for security here.
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        autogenerate_code_verifier=False,
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def save_credentials(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(settings.google_token_path), exist_ok=True)
    with open(settings.google_token_path, "w") as f:
        f.write(creds.to_json())


def load_credentials() -> Credentials | None:
    if not os.path.exists(settings.google_token_path):
        return None
    with open(settings.google_token_path) as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            log_outbound("oauth2.googleapis.com", "gmail.token_refresh", ok=False, reason=f"{type(e).__name__}: {e}"[:200])
            raise
        log_outbound("oauth2.googleapis.com", "gmail.token_refresh")
        save_credentials(creds)
    return creds


def _build_query(days: int, terms: list[str]) -> str:
    after = (date.today() - timedelta(days=days)).strftime("%Y/%m/%d")
    or_terms = " OR ".join(f'"{t}"' for t in terms)
    return f"after:{after} ({or_terms}) -category:promotions"


def _decode_body(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data.encode("utf-8") + b"===")
        return raw.decode("utf-8", errors="ignore")
    except (ValueError, UnicodeDecodeError):
        return ""


def _extract_body(payload: dict[str, Any]) -> str:
    parts_to_walk = [payload]
    text_parts: list[str] = []
    html_parts: list[str] = []
    while parts_to_walk:
        p = parts_to_walk.pop(0)
        mime = p.get("mimeType", "")
        if mime == "text/plain":
            text_parts.append(_decode_body(p))
        elif mime == "text/html":
            html_parts.append(_decode_body(p))
        for sub in p.get("parts", []):
            parts_to_walk.append(sub)
    if text_parts:
        return "\n".join(text_parts).strip()
    if html_parts:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_parts[0], "lxml")
        return soup.get_text("\n", strip=True)
    return ""


def _header(payload: dict[str, Any], name: str) -> str:
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def list_and_fetch(
    creds: Credentials,
    *,
    days: int | None = None,
    terms: list[str] | None = None,
    max_results: int = 100,
) -> list[GmailMessage]:
    days = days or settings.gmail_scan_days
    terms = terms or settings.gmail_query_terms
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = _build_query(days, terms)

    resp = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    log_outbound("gmail.googleapis.com", "gmail.list")
    ids = [m["id"] for m in resp.get("messages", [])]

    out: list[GmailMessage] = []
    for mid in ids:
        msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
        log_outbound("gmail.googleapis.com", "gmail.get")
        payload = msg.get("payload", {})
        subject = _header(payload, "Subject")
        sender = _header(payload, "From")
        date_hdr = _header(payload, "Date")
        try:
            received = parsedate_to_datetime(date_hdr) if date_hdr else datetime.utcnow()
        except (TypeError, ValueError):
            received = datetime.utcnow()
        body = _extract_body(payload)
        out.append(
            GmailMessage(
                id=mid,
                thread_id=msg.get("threadId", ""),
                subject=subject,
                sender=sender,
                received_at=received,
                body_text=body,
            )
        )
    return out
