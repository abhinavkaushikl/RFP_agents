"""Password hashing and signed session tokens, using only the standard library."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_process_secret = secrets.token_bytes(32)
_warned = False


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=128 * 1024 * 1024, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = _scrypt(password, _unb64(salt), int(n), int(r), int(p))
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


# Verified against when the email is unknown, so "no such user" costs the same as "wrong password".
DUMMY_HASH = hash_password(secrets.token_urlsafe(8))


def _secret() -> bytes:
    global _warned
    configured = get_settings().auth_secret
    if configured:
        return configured.encode()
    if not _warned:
        logger.warning("RFP_AUTH_SECRET is not set; sessions use a per-process secret and end on restart.")
        _warned = True
    return _process_secret


def _sign(body: str) -> str:
    return _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


def issue_session(user_id: str, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + get_settings().auth_session_ttl_s)
    body = f"{user_id}.{expires}"
    return f"{_b64(body.encode())}.{_sign(body)}"


def read_session(token: str | None, now: float | None = None) -> str | None:
    """The user id a valid, unexpired token was issued for, else None."""
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        body = _unb64(encoded).decode()
        user_id, expires = body.rsplit(".", 1)
        if not hmac.compare_digest(signature, _sign(body)):
            return None
        if int(expires) < (now if now is not None else time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return user_id
