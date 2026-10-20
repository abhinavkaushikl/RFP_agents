"""Sign up, sign in and session endpoints for the web app."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.security import SESSION_COOKIE, UnauthorizedError, _api_limiter
from app.core.auth_crypto import DUMMY_HASH, hash_password, issue_session, read_session, verify_password
from app.core.config import get_settings
from app.core.errors import AppError, InvalidRequestError, RateLimitedError
from app.db.models import User

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


@router.post("/signup")
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.auth_allow_signup:
        raise UnauthorizedError("Sign-up is disabled. Ask an administrator for an account.")
    _throttle(request)
    email = _normalize_email(body.email)
    if len(body.password) < 8:
        raise InvalidRequestError("Use at least 8 characters for the password.")
    user = User(id=uuid.uuid4(), email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists.") from None
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
