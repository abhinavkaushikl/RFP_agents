"""Sign in with Google (OAuth 2.0 authorization-code flow with PKCE)."""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleSignInError(AppError):
    status_code = 502
    code = "google_sign_in_failed"


def new_pkce() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def authorization_url(*, redirect_uri: str, state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "client_id": get_settings().google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })


def fetch_profile(*, code: str, verifier: str, redirect_uri: str) -> dict:
    """Trade the code for the person's verified Google profile: {sub, email, email_verified, name}."""
    settings = get_settings()
    try:
        token = httpx.post(TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value() if settings.google_client_secret else "",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }, timeout=15)
        token.raise_for_status()
        info = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {token.json()['access_token']}"}, timeout=15)
        info.raise_for_status()
        data = info.json()
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.error("Google sign-in failed: %s", exc)
        raise GoogleSignInError("Google sign-in did not complete. Try again.") from exc
    return {
        "sub": str(data.get("sub", "")),
        "email": str(data.get("email", "")).strip().lower(),
        "email_verified": bool(data.get("email_verified")),
        "name": str(data.get("name", "")).strip(),
    }
