"""Password hashing and signed session tokens, using only the standard library."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
import uuid

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


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(user_id: str, code: str) -> str:
    """Keyed hash of a one-time code, bound to the user it was issued for."""
    return _sign(f"otp:{user_id}:{code}")


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
        uuid.UUID(user_id)  # a session is only ever issued for a user id; anything else is not a session
    except (ValueError, UnicodeDecodeError):
        return None
    return user_id


# ── authenticator app (TOTP, RFC 6238) ─────────────────────────────────
TOTP_STEP_S = 30
TOTP_DIGITS = 6


def new_totp_secret() -> str:
    """20 random bytes as unpadded base32, the form authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret_b32: str, step: int) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10**TOTP_DIGITS)
    return f"{value:0{TOTP_DIGITS}d}"


def verify_totp(secret_b32: str, code: str, *, now: float | None = None, last_step: int | None = None) -> int | None:
    """The time step the code belongs to, or None. Allows one step of clock drift either way,
    and refuses any step at or before `last_step` so a code can only be used once."""
    code = code.strip().replace(" ", "")
    if len(code) != TOTP_DIGITS or not code.isdigit():
        return None
    current = int((now if now is not None else time.time()) // TOTP_STEP_S)
    for step in (current - 1, current, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp_code(secret_b32, step), code):
            return step
    return None


def totp_uri(secret_b32: str, email: str, issuer: str = "Proposal Builder") -> str:
    from urllib.parse import quote

    return (
        f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret_b32}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_STEP_S}"
    )


# ── sealing the stored secret ──────────────────────────────────────────
def _mfa_key() -> bytes:
    configured = get_settings().mfa_key
    return hmac.new((configured.encode() if configured else _secret()), b"proposal-builder/mfa-seal", hashlib.sha256).digest()


def seal(plain: str) -> str:
    """Encrypt-and-authenticate a short string (HMAC-SHA256 keystream + tag), stdlib only."""
    key, nonce, data = _mfa_key(), secrets.token_bytes(16), plain.encode()
    stream = b"".join(hmac.new(key, nonce + struct.pack(">I", i), hashlib.sha256).digest() for i in range(len(data) // 32 + 1))
    cipher = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.new(key, b"tag" + nonce + cipher, hashlib.sha256).digest()[:16]
    return _b64(nonce + cipher + tag)


def unseal(token: str | None) -> str | None:
    if not token:
        return None
    try:
        raw = _unb64(token)
        nonce, cipher, tag = raw[:16], raw[16:-16], raw[-16:]
        key = _mfa_key()
        if not hmac.compare_digest(tag, hmac.new(key, b"tag" + nonce + cipher, hashlib.sha256).digest()[:16]):
            return None
        stream = b"".join(hmac.new(key, nonce + struct.pack(">I", i), hashlib.sha256).digest() for i in range(len(cipher) // 32 + 1))
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


# ── the short-lived "password accepted, now the code" token ────────────
MFA_TOKEN_TTL_S = 300


def _mfa_sign(body: str) -> str:
    # A different HMAC context from sessions, so this token can never be presented as a session cookie.
    return _b64(hmac.new(_secret(), b"mfa-login:" + body.encode(), hashlib.sha256).digest())


def issue_mfa_token(user_id: str, now: float | None = None) -> str:
    body = f"{user_id}.{int((now if now is not None else time.time()) + MFA_TOKEN_TTL_S)}"
    return f"{_b64(body.encode())}.{_mfa_sign(body)}"


def read_mfa_token(token: str | None, now: float | None = None) -> str | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        body = _unb64(encoded).decode()
        user_id, expires = body.rsplit(".", 1)
        if not hmac.compare_digest(signature, _mfa_sign(body)) or int(expires) < (now if now is not None else time.time()):
            return None
        uuid.UUID(user_id)
    except (ValueError, UnicodeDecodeError):
        return None
    return user_id


# ── backup codes ───────────────────────────────────────────────────────
def new_backup_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(count)]


def normalize_backup(code: str) -> str:
    return code.strip().lower().replace("-", "").replace(" ", "")


def hash_backup(user_id: str, code: str) -> str:
    return _b64(hmac.new(_secret(), f"backup:{user_id}:{normalize_backup(code)}".encode(), hashlib.sha256).digest())
