from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import time
from typing import Any

import httpx
from pydantic import AnyHttpUrl

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)

FITBIT_AUTHORIZE_URL = "https://www.fitbit.com/oauth2/authorize"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"

FITBIT_SCOPES = [
    "activity",
    "heartrate",
    "location",
    "nutrition",
    "oxygen_saturation",
    "profile",
    "respiratory_rate",
    "settings",
    "sleep",
    "social",
    "temperature",
    "weight",
]


class FitbitOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth 2.1 Authorization Server that delegates to Fitbit for user authentication.

    Implements the MCP third-party authorization flow:
    1. MCP client (Claude) initiates OAuth with this server
    2. This server redirects user to Fitbit for authorization
    3. Fitbit redirects back with auth code
    4. This server exchanges for Fitbit tokens, then issues MCP tokens
    """

    def __init__(self, server_url: str, on_fitbit_tokens: Any = None) -> None:
        self._server_url = server_url.rstrip("/")
        self._fitbit_client_id = os.environ.get("FITBIT_CLIENT_ID", "")
        self._fitbit_client_secret = os.environ.get("FITBIT_CLIENT_SECRET", "")
        self._on_fitbit_tokens = on_fitbit_tokens

        # In-memory storage
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._mcp_tokens: dict[str, AccessToken] = {}
        self._mcp_refresh_tokens: dict[str, RefreshToken] = {}

        # Pending auth state: maps our state param to MCP client's auth params
        self._pending_auth: dict[str, dict[str, Any]] = {}

        # Maps state to Fitbit PKCE code_verifier (for the Fitbit OAuth exchange)
        self._fitbit_pkce: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(
        self, client_info: OAuthClientInformationFull
    ) -> None:
        if not client_info.client_id:
            client_info.client_id = f"client_{secrets.token_hex(16)}"
            client_info.client_id_issued_at = int(time.time())
        self._clients[client_info.client_id] = client_info
        logger.info(f"Registered MCP client: {client_info.client_id}")

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Redirect to Fitbit OAuth instead of showing a login form."""
        state = secrets.token_hex(32)

        # Store the MCP client's auth params so we can complete the flow later
        self._pending_auth[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "client_id": client.client_id,
            "scopes": params.scopes,
            "original_state": params.state,
            "resource": params.resource,
        }

        # Generate PKCE for our request to Fitbit
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .decode()
            .rstrip("=")
        )
        self._fitbit_pkce[state] = code_verifier

        # Build Fitbit authorization URL
        fitbit_auth_url = (
            f"{FITBIT_AUTHORIZE_URL}"
            f"?response_type=code"
            f"&client_id={self._fitbit_client_id}"
            f"&redirect_uri={self._server_url}/fitbit-callback"
            f"&scope={'+'.join(FITBIT_SCOPES)}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={state}"
        )

        logger.info("Redirecting user to Fitbit for authorization")
        return fitbit_auth_url

    async def handle_fitbit_callback(
        self, code: str, state: str
    ) -> str:
        """Handle Fitbit's OAuth callback. Exchange code for tokens and complete MCP flow."""
        pending = self._pending_auth.get(state)
        if not pending:
            raise ValueError("Invalid or expired state parameter")

        code_verifier = self._fitbit_pkce.get(state)
        if not code_verifier:
            raise ValueError("Missing PKCE code verifier")

        # Exchange the Fitbit authorization code for Fitbit tokens
        credentials = base64.b64encode(
            f"{self._fitbit_client_id}:{self._fitbit_client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                FITBIT_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content=(
                    f"grant_type=authorization_code"
                    f"&code={code}"
                    f"&redirect_uri={self._server_url}/fitbit-callback"
                    f"&code_verifier={code_verifier}"
                ),
            )

        if response.status_code != 200:
            logger.error(f"Fitbit token exchange failed: {response.text}")
            raise ValueError(f"Fitbit token exchange failed: {response.text}")

        fitbit_data = response.json()
        logger.info("Successfully exchanged Fitbit authorization code for tokens")

        # Notify the client (FitbitClient) of the new tokens
        if self._on_fitbit_tokens:
            self._on_fitbit_tokens(
                access_token=fitbit_data["access_token"],
                refresh_token=fitbit_data["refresh_token"],
                expires_in=fitbit_data.get("expires_in", 28800),
            )

        # Generate an MCP authorization code
        mcp_code = f"mcp_{secrets.token_hex(32)}"
        self._auth_codes[mcp_code] = AuthorizationCode(
            code=mcp_code,
            client_id=pending["client_id"],
            redirect_uri=AnyHttpUrl(pending["redirect_uri"]),
            redirect_uri_provided_explicitly=pending["redirect_uri_provided_explicitly"],
            expires_at=time.time() + 300,
            scopes=pending.get("scopes") or [],
            code_challenge=pending["code_challenge"],
            resource=pending.get("resource"),
        )

        # Clean up pending state
        del self._pending_auth[state]
        del self._fitbit_pkce[state]

        # Redirect back to the MCP client with the MCP authorization code
        redirect_uri = construct_redirect_uri(
            pending["redirect_uri"],
            code=mcp_code,
            state=pending.get("original_state"),
        )
        return redirect_uri

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._auth_codes.get(authorization_code)
        if code and code.client_id == client.client_id and time.time() < code.expires_at:
            return code
        return None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.code not in self._auth_codes:
            raise TokenError(error="invalid_grant", error_description="Invalid authorization code")

        # Generate MCP access token
        mcp_token = f"mcp_{secrets.token_hex(32)}"
        mcp_refresh = f"mcpr_{secrets.token_hex(32)}"

        self._mcp_tokens[mcp_token] = AccessToken(
            token=mcp_token,
            client_id=client.client_id or "",
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 3600,
            resource=authorization_code.resource,
        )

        self._mcp_refresh_tokens[mcp_refresh] = RefreshToken(
            token=mcp_refresh,
            client_id=client.client_id or "",
            scopes=authorization_code.scopes,
        )

        del self._auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=mcp_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=mcp_refresh,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        token = self._mcp_refresh_tokens.get(refresh_token)
        if token and token.client_id == client.client_id:
            return token
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Rotate MCP tokens
        new_token = f"mcp_{secrets.token_hex(32)}"
        new_refresh = f"mcpr_{secrets.token_hex(32)}"

        effective_scopes = scopes if scopes else refresh_token.scopes

        self._mcp_tokens[new_token] = AccessToken(
            token=new_token,
            client_id=client.client_id or "",
            scopes=effective_scopes,
            expires_at=int(time.time()) + 3600,
        )

        self._mcp_refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh,
            client_id=client.client_id or "",
            scopes=effective_scopes,
        )

        # Clean up old tokens
        if refresh_token.token in self._mcp_refresh_tokens:
            del self._mcp_refresh_tokens[refresh_token.token]

        return OAuthToken(
            access_token=new_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=new_refresh,
            scope=" ".join(effective_scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        access_token = self._mcp_tokens.get(token)
        if not access_token:
            return None
        if access_token.expires_at and time.time() > access_token.expires_at:
            del self._mcp_tokens[token]
            return None
        return access_token

    async def revoke_token(
        self, token: AccessToken | RefreshToken
    ) -> None:
        if isinstance(token, AccessToken) and token.token in self._mcp_tokens:
            del self._mcp_tokens[token.token]
        elif isinstance(token, RefreshToken) and token.token in self._mcp_refresh_tokens:
            del self._mcp_refresh_tokens[token.token]
