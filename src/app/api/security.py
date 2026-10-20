"""API key authentication and inbound rate limiting."""
from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from fastapi import Depends, Header, Request

from app.core.auth_crypto import read_session
from app.core.config import get_settings
from app.core.errors import AppError, RateLimitedError
from app.core.redis import get_redis
from app.llm.rate_limiter import ApiRateLimiter, SlidingWindowLimiter


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


SESSION_COOKIE = "rfp_session"


class SignInRequiredError(UnauthorizedError):
    code = "auth_required"


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> str | None:
    """Accept a signed-in session or an API key. Enforced when RFP_AUTH_REQUIRED or RFP_API_KEYS is set."""
    settings = get_settings()
    user_id = read_session(request.cookies.get(SESSION_COOKIE))
    if user_id:
        return f"user:{user_id}"
    keys = settings.api_key_list
    if keys and x_api_key and any(hmac.compare_digest(x_api_key, key) for key in keys):
        return x_api_key
    if settings.auth_required:
        raise SignInRequiredError("Sign in to continue.")
    if keys:
        raise UnauthorizedError("Missing or invalid X-API-Key header.")
    return None


@lru_cache
def _api_limiter() -> ApiRateLimiter:
    return ApiRateLimiter(SlidingWindowLimiter(get_redis, namespace=get_settings().cache_namespace))


def rate_limit_requests(request: Request, api_key: str | None = Depends(require_api_key)) -> None:
    limit = get_settings().api_rate_limit_per_minute
    if limit <= 0:
        return
    if api_key:
        identity = "key:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
    else:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        identity = "ip:" + (forwarded or (request.client.host if request.client else "unknown"))
    allowed, retry_after = _api_limiter().hit(identity, limit)
    if not allowed:
        raise RateLimitedError(f"Rate limit of {limit} requests per minute exceeded.", retry_after=retry_after)

