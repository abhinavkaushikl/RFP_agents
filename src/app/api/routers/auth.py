"""Sign up, sign in and session endpoints for the web app."""
from __future__ import annotations

import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.security import SESSION_COOKIE, UnauthorizedError, _api_limiter
from app.core.auth_crypto import (
    DUMMY_HASH, hash_backup, hash_code, hash_password, issue_mfa_token, issue_session, new_backup_codes, new_code,
    new_totp_secret, open_blob, read_mfa_token, read_session, seal, seal_blob, totp_uri, unseal, verify_password, verify_totp,
)
from app.core.config import get_settings
from app.core.errors import AppError, InvalidRequestError, RateLimitedError
from app.db.models import EmailOtp, User
from app.services import google_oauth
from app.services.mailer import send_code

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class SignupRequest(Credentials):
    name: str = Field(default="", max_length=120)


def _public(user: User) -> dict:
    admin = user.role == "admin" or user.email.lower() in get_settings().admin_email_list
    return {
        "id": str(user.id), "email": user.email, "name": user.name, "role": "admin" if admin else "member",
        "mfa_enabled": user.totp_enabled_at is not None,
    }


def _set_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(str(user.id)),
        max_age=settings.auth_session_ttl_s,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/",
    )


def _throttle(request: Request) -> None:
    limit = get_settings().auth_login_attempts_per_minute
    if limit <= 0:
        return
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    allowed, retry_after = _api_limiter().hit(f"auth:{ip}", limit)
    if not allowed:
        raise RateLimitedError("Too many attempts. Try again in a minute.", retry_after=retry_after)


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise InvalidRequestError("Enter a valid email address.")
    return email


class VerifyRequest(BaseModel):
    email: str = Field(max_length=320)
    code: str = Field(max_length=12)


class ResetRequest(BaseModel):
    email: str = Field(max_length=320)
    code: str = Field(max_length=12)
    new_password: str = Field(max_length=256)


class EmailOnly(BaseModel):
    email: str = Field(max_length=320)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _send_new_code(db: Session, user: User, *, respect_cooldown: bool) -> None:
    """Replace any pending code with a fresh one and email it."""
    settings = get_settings()
    latest = db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id).order_by(EmailOtp.created_at.desc()))
    if respect_cooldown and latest is not None:
        wait = settings.otp_resend_cooldown_s - (_now() - _aware(latest.created_at)).total_seconds()
        if wait > 0:
            raise RateLimitedError(f"Wait {int(wait) + 1} seconds before asking for another code.", retry_after=wait)
    db.execute(delete(EmailOtp).where(EmailOtp.user_id == user.id))
    code = new_code()
    db.add(EmailOtp(
        id=uuid.uuid4(), user_id=user.id, code_hash=hash_code(str(user.id), code),
        expires_at=_now() + timedelta(seconds=settings.otp_ttl_s),
    ))
    db.commit()
    try:
        send_code(user.email, code)
    except AppError:
        # Nothing reached them: drop the code so the retry isn't held back by the resend cooldown.
        db.execute(delete(EmailOtp).where(EmailOtp.user_id == user.id))
        db.commit()
        raise


def _needs_code(email: str) -> dict:
    return {"verification_required": True, "email": email}


@router.post("/signup")
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.auth_allow_signup:
        raise UnauthorizedError("Sign-up is disabled. Ask an administrator for an account.")
    _throttle(request)
    email = _normalize_email(body.email)
    if len(body.password) < 8:
        raise InvalidRequestError("Use at least 8 characters for the password.")
    user = db.scalar(select(User).where(User.email == email))
    if not settings.email_verification_required:
        # No email service: accounts work straight away, so an existing address can't be re-claimed.
        if user is not None:
            raise ConflictError("An account with this email already exists. Sign in instead.")
        user = User(id=uuid.uuid4(), email=email, name=body.name.strip(), password_hash=hash_password(body.password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConflictError("An account with this email already exists.") from None
        _set_cookie(response, user)
        return {"user": _public(user)}
    if user is not None and user.email_verified_at is not None:
        raise ConflictError("An account with this email already exists.")
    if user is None:
        user = User(id=uuid.uuid4(), email=email)
        db.add(user)
    # An unconfirmed account can be taken over by whoever now proves they own the address,
    # so nobody can squat on someone else's email by signing up with it first.
    user.name = body.name.strip()
    user.password_hash = hash_password(body.password)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists.") from None
    _send_new_code(db, user, respect_cooldown=True)
    return _needs_code(email)


@router.post("/verify")
def verify(body: VerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _throttle(request)
    settings = get_settings()
    wrong = UnauthorizedError("That code isn't right. Check it or ask for a new one.")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    otp = (
        db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id).order_by(EmailOtp.created_at.desc()))
        if user else None
    )
    if user is None or otp is None:
        raise wrong
    if _aware(otp.expires_at) < _now():
        db.delete(otp)
        db.commit()
        raise UnauthorizedError("That code has expired. Ask for a new one.")
    if otp.attempts >= settings.otp_max_attempts:
        db.delete(otp)
        db.commit()
        raise RateLimitedError("Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(otp.code_hash, hash_code(str(user.id), body.code.strip())):
        otp.attempts += 1
        db.commit()
        raise wrong
    db.execute(delete(EmailOtp).where(EmailOtp.user_id == user.id))
    user.email_verified_at = _now()
    db.commit()
    _set_cookie(response, user)
    return {"user": _public(user)}


@router.post("/resend")
def resend(body: EmailOnly, request: Request, db: Session = Depends(get_db)) -> dict:
    _throttle(request)
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Same answer whether or not the address has an unconfirmed account, so this can't be used to probe emails.
    if user is not None and user.email_verified_at is None:
        _send_new_code(db, user, respect_cooldown=True)
    return {"ok": True}


@router.post("/forgot")
def forgot_password(body: EmailOnly, request: Request, db: Session = Depends(get_db)) -> dict:
    """Email a one-time code that lets the owner of the address choose a new password."""
    _throttle(request)
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is not None:
        try:
            _send_new_code(db, user, respect_cooldown=True)
        except (RateLimitedError, AppError) as exc:
            # Same answer whether or not the address has an account (and whether or not the mail went out),
            # so this can't be used to find out who is registered. The failure is in the server log.
            logger.warning("Password reset code for %s was not sent: %s", user.email, exc)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: ResetRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _throttle(request)
    settings = get_settings()
    if len(body.new_password) < 8:
        raise InvalidRequestError("Use at least 8 characters for the new password.")
    wrong = UnauthorizedError("That code isn't right. Check it or ask for a new one.")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    otp = (
        db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id).order_by(EmailOtp.created_at.desc()))
        if user else None
    )
    if user is None or otp is None:
        raise wrong
    if _aware(otp.expires_at) < _now():
        db.delete(otp)
        db.commit()
        raise UnauthorizedError("That code has expired. Ask for a new one.")
    if otp.attempts >= settings.otp_max_attempts:
        db.delete(otp)
        db.commit()
        raise RateLimitedError("Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(otp.code_hash, hash_code(str(user.id), body.code.strip())):
        otp.attempts += 1
        db.commit()
        raise wrong
    db.execute(delete(EmailOtp).where(EmailOtp.user_id == user.id))
    user.password_hash = hash_password(body.new_password)
    if user.email_verified_at is None:
        user.email_verified_at = _now()  # they just proved they own the address
    db.commit()
    if user.totp_enabled_at is not None:
        # Email access alone must not bypass the authenticator: they sign in the normal way next.
        return {"password_updated": True, "login_required": True}
    _set_cookie(response, user)
    return {"user": _public(user)}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _throttle(request)
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Always run one hash verification so timing doesn't reveal which emails exist.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise UnauthorizedError("Incorrect email or password.")
    if user.email_verified_at is None and get_settings().email_verification_required:
        try:
            _send_new_code(db, user, respect_cooldown=True)
        except RateLimitedError:
            pass  # a code was just sent; the page lets them enter it
        return _needs_code(email)
    if user.totp_enabled_at is not None:
        # Password accepted; no session yet. The authenticator code completes the sign-in.
        return {"mfa_required": True, "mfa_token": issue_mfa_token(str(user.id)), "email": email}
    _set_cookie(response, user)
    return {"user": _public(user)}



# ── authenticator app ──────────────────────────────────────────────────
class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(max_length=600)
    code: str = Field(max_length=32)


class MfaEnableRequest(BaseModel):
    code: str = Field(max_length=16)


class MfaDisableRequest(BaseModel):
    password: str = Field(max_length=256)
    code: str = Field(max_length=32)


def _signed_in_user(request: Request, db: Session) -> User:
    user_id = read_session(request.cookies.get(SESSION_COOKIE))
    user = db.get(User, uuid.UUID(user_id)) if user_id else None
    if user is None:
        raise UnauthorizedError("Sign in to continue.")
    return user


def _qr_data_url(text: str) -> str:
    """The QR code as an SVG data URL (reportlab is already a dependency)."""
    import base64

    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing

    widget = qr.QrCodeWidget(text, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    size = 220
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    svg = renderSVG.drawToString(drawing)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _check_second_factor(user: User, code: str, *, consume: bool = True) -> bool:
    """A current authenticator code, or an unused backup code. Marks it used when `consume`."""
    secret = unseal(user.totp_secret_enc)
    if secret:
        step = verify_totp(secret, code, last_step=user.totp_last_step)
        if step is not None:
            if consume:
                user.totp_last_step = step
            return True
    candidate = hash_backup(str(user.id), code)
    hashes = list(user.mfa_backup_hashes or [])
    for stored in hashes:
        if hmac.compare_digest(stored, candidate):
            if consume:
                user.mfa_backup_hashes = [h for h in hashes if h != stored]
            return True
    return False


def _note_mfa_failure(db: Session, user: User) -> None:
    user.mfa_failures = (user.mfa_failures or 0) + 1
    if user.mfa_failures >= get_settings().otp_max_attempts:
        user.mfa_failures = 0
        user.mfa_locked_until = _now() + timedelta(minutes=5)
    db.commit()


def _refuse_if_locked(user: User) -> None:
    if user.mfa_locked_until is not None and _aware(user.mfa_locked_until) > _now():
        wait = int((_aware(user.mfa_locked_until) - _now()).total_seconds()) + 1
        raise RateLimitedError(f"Too many wrong codes. Try again in {wait} seconds.", retry_after=wait)


@router.post("/mfa/verify")
def mfa_verify(body: MfaVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Second step of sign-in: the code from the authenticator app (or a backup code)."""
    _throttle(request)
    user_id = read_mfa_token(body.mfa_token)
    user = db.get(User, uuid.UUID(user_id)) if user_id else None
    if user is None or user.totp_enabled_at is None:
        raise UnauthorizedError("That sign-in expired. Enter your password again.")
    _refuse_if_locked(user)
    if not _check_second_factor(user, body.code):
        _note_mfa_failure(db, user)
        raise UnauthorizedError("That code isn't right. Check the app and try again.")
    user.mfa_failures = 0
    user.mfa_locked_until = None
    db.commit()
    _set_cookie(response, user)
    return {"user": _public(user)}


@router.post("/mfa/setup")
def mfa_setup(request: Request, db: Session = Depends(get_db)) -> dict:
    """Start enrolling an authenticator app: returns the QR code and the key to type in by hand."""
    user = _signed_in_user(request, db)
    if user.totp_enabled_at is not None:
        raise ConflictError("Two-step sign-in is already on. Turn it off first to set it up again.")
    secret = new_totp_secret()
    user.totp_secret_enc = seal(secret)  # pending until the first code is confirmed
    db.commit()
    uri = totp_uri(secret, user.email)
    return {"secret": secret, "otpauth_uri": uri, "qr": _qr_data_url(uri)}


@router.post("/mfa/enable")
def mfa_enable(body: MfaEnableRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """Confirm the first code from the app. Returns the backup codes, once."""
    _throttle(request)
    user = _signed_in_user(request, db)
    if user.totp_enabled_at is not None:
        raise ConflictError("Two-step sign-in is already on.")
    secret = unseal(user.totp_secret_enc)
    if not secret:
        raise InvalidRequestError("Start the setup again to get a new QR code.")
    step = verify_totp(secret, body.code)
    if step is None:
        raise UnauthorizedError("That code isn't right. Check the app and try again.")
    codes = new_backup_codes()
    user.totp_enabled_at = _now()
    user.totp_last_step = step
    user.mfa_backup_hashes = [hash_backup(str(user.id), c) for c in codes]
    user.mfa_failures = 0
    db.commit()
    return {"enabled": True, "backup_codes": codes}


@router.post("/mfa/disable")
def mfa_disable(body: MfaDisableRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """Turning it off needs the password and a current code, so a borrowed session can't do it."""
    _throttle(request)
    user = _signed_in_user(request, db)
    if user.totp_enabled_at is None:
        return {"enabled": False}
    _refuse_if_locked(user)
    if not verify_password(body.password, user.password_hash) or not _check_second_factor(user, body.code):
        _note_mfa_failure(db, user)
        raise UnauthorizedError("Your password or code isn't right.")
    user.totp_secret_enc = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    user.mfa_backup_hashes = []
    user.mfa_failures = 0
    user.mfa_locked_until = None
    db.commit()
    return {"enabled": False}



# ── Sign in with Google ────────────────────────────────────────────────
_OAUTH_COOKIE = "rfp_oauth"


def _origin(request: Request) -> str:
    configured = get_settings().public_url.rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc)).split(",")[0].strip()
    return f"{proto}://{host}"


def _safe_next(path: str | None) -> str:
    """Only same-site paths, so the login can't be used to bounce people to another site."""
    return path if path and path.startswith("/") and not path.startswith("//") and "\\" not in path else "/"


def _login_error(request: Request, code: str) -> RedirectResponse:
    response = RedirectResponse(f"{_origin(request)}/login?google_error={code}", status_code=302)
    response.delete_cookie(_OAUTH_COOKIE, path="/")
    return response


@router.get("/google/start")
def google_start(request: Request, next: str | None = None) -> RedirectResponse:
    if not get_settings().google_enabled:
        return _login_error(request, "not_configured")
    _throttle(request)
    state = secrets.token_urlsafe(24)
    verifier, challenge = google_oauth.new_pkce()
    redirect_uri = f"{_origin(request)}/api/auth/google/callback"
    response = RedirectResponse(
        google_oauth.authorization_url(redirect_uri=redirect_uri, state=state, challenge=challenge), status_code=302,
    )
    response.set_cookie(
        _OAUTH_COOKIE, seal_blob("oauth", {"state": state, "verifier": verifier, "next": _safe_next(next)}),
        max_age=600, httponly=True, samesite="lax", secure=get_settings().environment == "production", path="/",
    )
    return response


@router.get("/google/callback")
def google_callback(
    request: Request, code: str | None = None, state: str | None = None, error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_enabled:
        return _login_error(request, "not_configured")
    saved = open_blob("oauth", request.cookies.get(_OAUTH_COOKIE))
    if error or not code or not state or saved is None or not hmac.compare_digest(str(saved.get("state", "")), state):
        return _login_error(request, "cancelled" if error else "expired")
    try:
        profile = google_oauth.fetch_profile(
            code=code, verifier=saved["verifier"], redirect_uri=f"{_origin(request)}/api/auth/google/callback",
        )
    except AppError:
        return _login_error(request, "failed")
    if not profile["sub"] or not profile["email"] or not profile["email_verified"]:
        return _login_error(request, "unverified_email")  # only emails Google itself has verified are trusted

    user = db.scalar(select(User).where(User.google_sub == profile["sub"]))
    if user is None:
        user = db.scalar(select(User).where(User.email == profile["email"]))
        if user is None:
            if not settings.auth_allow_signup:
                return _login_error(request, "signup_disabled")
            user = User(
                id=uuid.uuid4(), email=profile["email"], name=profile["name"],
                password_hash=hash_password(secrets.token_urlsafe(32)),  # no password: they sign in with Google
            )
            db.add(user)
        user.google_sub = profile["sub"]
        if user.email_verified_at is None:
            user.email_verified_at = _now()  # Google confirmed this address
        if not user.name:
            user.name = profile["name"]
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return _login_error(request, "failed")

    destination = _safe_next(saved.get("next"))
    if user.totp_enabled_at is not None:
        # Their account has an authenticator: Google alone is not enough. The token travels in the URL
        # fragment, which browsers never send to servers.
        response = RedirectResponse(f"{_origin(request)}/login#mfa={issue_mfa_token(str(user.id))}&next={destination}", status_code=302)
    else:
        response = RedirectResponse(f"{_origin(request)}{destination}", status_code=302)
        _set_cookie(response, user)
    response.delete_cookie(_OAUTH_COOKIE, path="/")
    return response


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)) -> dict:
    """Never 401s: the web app calls this on load to decide whether to show the login page."""
    settings = get_settings()
    user = None
    user_id = read_session(request.cookies.get(SESSION_COOKIE))
    if user_id:
        try:
            user = db.get(User, uuid.UUID(user_id))
        except ValueError:
            user = None
    return {
        "user": _public(user) if user else None,
        "auth_required": settings.auth_required,
        "signup_enabled": settings.auth_allow_signup,
        "google_enabled": settings.google_enabled,
    }
