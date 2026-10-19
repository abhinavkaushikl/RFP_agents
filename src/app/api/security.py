"""API key authentication and inbound rate limiting."""
from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from fastapi import Depends, Header, Request

from app.core.config import get_settings
from app.core.errors import AppError, RateLimitedError
from app.core.redis import get_redis
from app.llm.rate_limiter import ApiRateLimiter, SlidingWindowLimiter


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


def require_api_key(x_api_key: str | None = Header(default=None)) -> str | None:
    """Enforced only when RFP_API_KEYS is set."""
    keys = get_settings().api_key_list
    if not keys:
        return None
    if not x_api_key or not any(hmac.compare_digest(x_api_key, key) for key in keys):
        raise UnauthorizedError("Missing or invalid X-API-Key header.")
    return x_api_key


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
