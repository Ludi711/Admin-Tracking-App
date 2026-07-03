from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from google_auth_oauthlib.flow import Flow

from config import (
    GMAIL_SCOPES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    OAUTH_STATE_SECRET,
)


def hosted_oauth_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


def _client_config() -> dict[str, Any]:
    if not hosted_oauth_configured():
        raise RuntimeError(
            "Hosted OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI."
        )
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _unb64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def create_signed_state(*, next_path: str = "/") -> str:
    payload = {
        "iat": int(time.time()),
        "nonce": _b64url(hashlib.sha256(str(time.time()).encode()).digest())[:24],
        "next": next_path,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        str(OAUTH_STATE_SECRET).encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_b64url(sig)}"


def verify_signed_state(state: str, *, max_age_seconds: int = 15 * 60) -> dict[str, Any]:
    try:
        body, sig = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid OAuth state format.") from exc

    expected = hmac.new(
        str(OAUTH_STATE_SECRET).encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual = _unb64url(sig)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid OAuth state signature.")

    payload = json.loads(_unb64url(body).decode("utf-8"))
    if int(time.time()) - int(payload.get("iat", 0)) > max_age_seconds:
        raise ValueError("OAuth state has expired. Please try connecting again.")
    return payload


def _make_flow() -> Flow:
    # Important: google-auth-oauthlib auto-generates a PKCE code_verifier by default.
    # Streamlit can lose that verifier across the external Google redirect, causing
    # "invalid_grant: Missing code verifier". For this hosted alpha we use a normal
    # confidential web-app flow with the client secret held in Streamlit secrets, so
    # PKCE is explicitly disabled.
    return Flow.from_client_config(
        _client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
    )


def build_authorization_url() -> str:
    """Return the Google consent URL for the hosted Streamlit alpha."""
    flow = _make_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=create_signed_state(),
    )
    return auth_url


def exchange_code_for_credentials(*, code: str, state: str):
    """Validate OAuth state, exchange authorization code, and return credentials."""
    verify_signed_state(state)
    flow = _make_flow()
    flow.fetch_token(code=code)
    return flow.credentials
