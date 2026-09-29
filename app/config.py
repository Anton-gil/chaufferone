from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{ROOT / 'data' / 'chaufferone.db'}"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_token_path: str = str(ROOT / "data" / "google_token.json")

    anthropic_api_key: str = ""
    anthropic_triage_model: str = "claude-haiku-4-5-20251001"
    anthropic_extract_model: str = "claude-sonnet-5"

    gmail_scan_days: int = 90
    gmail_query_terms: list[str] = [
        "invoice", "bill", "due", "renewal", "premium", "insurance",
        "subscription", "fee", "receipt", "payment", "recharge", "policy",
    ]

    default_user_id: str = "00000000-0000-0000-0000-000000000001"


settings = Settings()
