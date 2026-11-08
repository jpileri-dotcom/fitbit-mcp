"""Server-side Google OAuth: token storage on the Fly volume, code exchange, refresh."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from fitbit_mcp import config

logger = logging.getLogger("fitbit_mcp.auth")


class AuthRequired(Exception):
    """Raised when there is no usable Google refresh token."""


def _token_path() -> Path:
    return Path(config.DATA_DIR) / "google_token.json"


def _state_path() -> Path:
    return Path(config.DATA_DIR) / "oauth_states.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


# ---------------------------------------------------------------- OAuth flow


def new_auth_url() -> str:
    """Create a one-time state value (stored on disk so it survives restarts)."""
    states = _read_json(_state_path())
    now = time.time()
    states = {k: v for k, v in states.items() if now - v < 900}  # 15 min validity
    state = secrets.token_urlsafe(24)
    states[state] = now
    _write_json(_state_path(), states)
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(config.SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{config.AUTH_URL}?{urlencode(params)}"


def consume_state(state: str) -> bool:
    states = _read_json(_state_path())
    ts = states.pop(state, None)
    _write_json(_state_path(), states)
    return ts is not None and time.time() - ts < 900


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(
            config.TOKEN_URL,
            data={
                "code": code,
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
                "redirect_uri": config.REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    data = r.json()
    if r.status_code != 200 or "access_token" not in data:
        raise ValueError(f"Google token exchange failed: {data.get('error_description') or data}")
    if not data.get("refresh_token"):
        raise ValueError("Google did not return a refresh token. Open /auth/start again.")
    tok = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
        "scope": data.get("scope", ""),
        "linked_at": time.time(),
    }
    _write_json(_token_path(), tok)
    return tok


# ---------------------------------------------------------------- tokens

_lock = asyncio.Lock()


def granted_scopes() -> set[str]:
    return set(_read_json(_token_path()).get("scope", "").split())


def has_token() -> bool:
    return bool(_read_json(_token_path()).get("refresh_token"))


def clear_token() -> None:
    try:
        _token_path().unlink()
    except FileNotFoundError:
        pass


async def get_access_token(force_refresh: bool = False) -> str:
    async with _lock:
        tok = _read_json(_token_path())
        if not tok.get("refresh_token"):
            raise AuthRequired()
        if not force_refresh and tok.get("access_token") and tok.get("expires_at", 0) > time.time():
            return tok["access_token"]
        async with httpx.AsyncClient(timeout=20) as http:
            r = await http.post(
                config.TOKEN_URL,
                data={
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "refresh_token": tok["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        data = r.json() if r.content else {}
        if r.status_code in (400, 401) and data.get("error") in ("invalid_grant", "unauthorized_client", "invalid_client"):
            logger.warning("Refresh token rejected by Google: %s", data.get("error"))
            raise AuthRequired()
        if r.status_code != 200:
            raise RuntimeError(f"Google token refresh failed ({r.status_code}): {data}")
        tok["access_token"] = data["access_token"]
        tok["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
        if data.get("refresh_token"):
            tok["refresh_token"] = data["refresh_token"]
        if data.get("scope"):
            tok["scope"] = data["scope"]
        _write_json(_token_path(), tok)
        return tok["access_token"]
