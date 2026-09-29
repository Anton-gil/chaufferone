"""Single source of 'today' so the demo can pin the date (DEMO_TODAY)."""

from datetime import date

from app.config import settings


def today() -> date:
    return settings.demo_today or date.today()
