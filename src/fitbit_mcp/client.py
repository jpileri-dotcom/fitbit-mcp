from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FITBIT_BASE_URL = "https://api.fitbit.com"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"


class FitbitError(Exception):
    """Raised when the Fitbit API returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Fitbit API error {status_code}: {detail}")


class FitbitRateLimitError(FitbitError):
    """Raised when the Fitbit API rate limit is exceeded."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            status_code=429,
            detail=f"Rate limit exceeded. Resets in {retry_after_seconds} seconds.",
        )


class FitbitClient:
    """Async HTTP client for the Fitbit Web API with OAuth 2.0 token management."""

    def __init__(self) -> None:
        self._client_id = os.environ.get("FITBIT_CLIENT_ID", "")
        self._client_secret = os.environ.get("FITBIT_CLIENT_SECRET", "")
        self._client = httpx.AsyncClient(
            base_url=FITBIT_BASE_URL,
            timeout=30.0,
        )
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._token_file = Path(os.environ.get("FITBIT_TOKEN_FILE", "/data/.fitbit_tokens.json"))

        self._load_persisted_tokens()

    def _load_persisted_tokens(self) -> None:
        """Load Fitbit tokens from the persistence file if available."""
        try:
            if self._token_file.exists():
                data = json.loads(self._token_file.read_text())
                self._access_token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                expires_at = data.get("expires_at", 0)
                self._token_expires_at = expires_at
                logger.info("Loaded persisted Fitbit tokens")
        except Exception:
            logger.warning("Could not load persisted tokens, will need fresh auth")

    def _persist_tokens(self) -> None:
        """Persist current Fitbit tokens to disk."""
        try:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": self._token_expires_at,
            }
            self._token_file.write_text(json.dumps(data))
            logger.info("Persisted Fitbit tokens to disk")
        except Exception:
            logger.warning("Could not persist tokens to disk")

    def set_tokens(
        self, access_token: str, refresh_token: str, expires_in: int
    ) -> None:
        """Set Fitbit tokens after OAuth exchange."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = time.time() + expires_in - 60
        self._persist_tokens()

    @property
    def has_tokens(self) -> bool:
        return self._refresh_token is not None

    async def _refresh_access_token(self) -> None:
        """Refresh the Fitbit access token using the refresh token."""
        if not self._refresh_token:
            raise FitbitError(401, "No refresh token available. User must re-authenticate.")

        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()

        response = await self._client.post(
            FITBIT_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            content=f"grant_type=refresh_token&refresh_token={self._refresh_token}",
        )

        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.status_code} {response.text}")
            raise FitbitError(response.status_code, f"Token refresh failed: {response.text}")

        data = response.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 28800) - 60
        self._persist_tokens()
        logger.info("Fitbit access token refreshed successfully")

    async def _ensure_token(self, force: bool = False) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        async with self._lock:
            if not force and self._access_token and time.time() < self._token_expires_at:
                return
            await self._refresh_access_token()

    async def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse response, raising errors on non-2xx status."""
        if response.status_code == 429:
            retry_after = int(response.headers.get("Fitbit-Rate-Limit-Reset", "3600"))
            raise FitbitRateLimitError(retry_after_seconds=retry_after)

        if response.status_code >= 400:
            try:
                body = response.json()
                errors = body.get("errors", [])
                if errors:
                    detail = "; ".join(
                        f"{e.get('errorType', 'unknown')}: {e.get('message', '')}"
                        for e in errors
                    )
                else:
                    detail = response.text
            except (json.JSONDecodeError, KeyError):
                detail = response.text
            raise FitbitError(status_code=response.status_code, detail=detail)

        return response.json()

    def _rate_limit_info(self, response: httpx.Response) -> str:
        """Extract rate limit info from response headers."""
        remaining = response.headers.get("Fitbit-Rate-Limit-Remaining")
        limit = response.headers.get("Fitbit-Rate-Limit-Limit")
        reset = response.headers.get("Fitbit-Rate-Limit-Reset")
        if remaining is not None:
            return f"[Rate limit: {remaining}/{limit} remaining, resets in {reset}s]"
        return ""

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated GET request to the Fitbit API."""
        await self._ensure_token()
        params = {k: v for k, v in (params or {}).items() if v is not None}
        response = await self._client.get(
            path,
            headers={"Authorization": f"Bearer {self._access_token}"},
            params=params or None,
        )

        if response.status_code == 401:
            await self._ensure_token(force=True)
            response = await self._client.get(
                path,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params or None,
            )

        result = await self._handle_response(response)
        rate_info = self._rate_limit_info(response)
        if rate_info:
            logger.info(f"GET {path} {rate_info}")
        return result

    async def post(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated POST request to the Fitbit API with form-encoded data."""
        await self._ensure_token()
        response = await self._client.post(
            path,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={k: str(v) for k, v in (data or {}).items() if v is not None},
        )

        if response.status_code == 401:
            await self._ensure_token(force=True)
            response = await self._client.post(
                path,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={k: str(v) for k, v in (data or {}).items() if v is not None},
            )

        result = await self._handle_response(response)
        rate_info = self._rate_limit_info(response)
        if rate_info:
            logger.info(f"POST {path} {rate_info}")
        return result

    async def close(self) -> None:
        await self._client.aclose()
