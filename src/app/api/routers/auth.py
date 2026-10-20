"""Sign up, sign in and session endpoints for the web app."""
from __future__ import annotations

import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.security import SESSION_COOKIE, UnauthorizedError, _api_limiter
from app.core.auth_crypto import DUMMY_HASH, hash_code, hash_password, issue_session, new_code, read_session, verify_password
from app.core.config import get_settings
from app.core.errors import AppError, InvalidRequestError, RateLimitedError
from app.db.models import EmailOtp, User
from app.services.mailer import send_code

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
    return {"id": str(user.id), "email": user.email, "name": user.name}


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
    send_code(user.email, code)


def _needs_code(email: str) -> dict:
    return {"verification_required": True, "email": email}


@router.post("/signup")
def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.auth_allow_signup:
        raise UnauthorizedError("Sign-up is disabled. Ask an administrator for an account.")
    _throttle(request)
    email = _normalize_email(body.email)
    if len(body.password) < 8:
        raise InvalidRequestError("Use at least 8 characters for the password.")
    user = db.scalar(select(User).where(User.email == email))
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


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _throttle(request)
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Always run one hash verification so timing doesn't reveal which emails exist.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise UnauthorizedError("Incorrect email or password.")
    if user.email_verified_at is None:
        try:
            _send_new_code(db, user, respect_cooldown=True)
        except RateLimitedError:
            pass  # a code was just sent; the page lets them enter it
        return _needs_code(email)
    _set_cookie(response, user)
    return {"user": _public(user)}


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
    }
