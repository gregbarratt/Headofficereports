from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class SingsApiConfig:
    base_url: str
    api_key: str
    api_secret: str


class SingsApiNotConfiguredError(RuntimeError):
    pass


class SingsService:
    """Placeholder for future SINGs/Singhs API integration.

    CSV/XLSX upload remains the active customer payment import method.
    Do not add guessed endpoint paths here. Actual endpoints, authentication
    format and response mapping must come from official SINGs/Singhs API docs.
    """

    def __init__(self, config: SingsApiConfig | None = None) -> None:
        self.config = config or SingsApiConfig(
            base_url=settings.sings_api_base_url.strip(),
            api_key=settings.sings_api_key.strip(),
            api_secret=settings.sings_api_secret.strip(),
        )

    def ensure_configured(self) -> None:
        if not self.config.base_url or not self.config.api_key:
            raise SingsApiNotConfiguredError(
                "SINGs/Singhs API is not configured. CSV/XLSX customer payment import remains active."
            )

    def fetch_transactions(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        self.ensure_configured()
        # TODO: Add the real transactions endpoint once SINGs/Singhs API documentation is received.
        raise NotImplementedError("SINGs/Singhs transactions API endpoint has not been provided yet.")

    def fetch_settlements(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        self.ensure_configured()
        # TODO: Add the real settlements endpoint once SINGs/Singhs API documentation is received.
        raise NotImplementedError("SINGs/Singhs settlements API endpoint has not been provided yet.")

    def fetch_refunds(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        self.ensure_configured()
        # TODO: Add the real refunds endpoint once SINGs/Singhs API documentation is received.
        raise NotImplementedError("SINGs/Singhs refunds API endpoint has not been provided yet.")

    def fetch_chargebacks(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        self.ensure_configured()
        # TODO: Add the real chargebacks endpoint once SINGs/Singhs API documentation is received.
        raise NotImplementedError("SINGs/Singhs chargebacks API endpoint has not been provided yet.")
