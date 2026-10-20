"""Shared Redis client with graceful degradation.

Redis backs the response cache and the rate limiters. If it is unreachable the
platform keeps working with process-local fallbacks, and retries the connection
every `_RETRY_AFTER_S` seconds.
"""
from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.logging import get_logger

try:
    import redis as redis_lib
except ImportError:  # pragma: no cover
    redis_lib = None  # type: ignore[assignment]

logger = get_logger(__name__)

_RETRY_AFTER_S = 30.0
_lock = threading.Lock()
_client = None
_last_failure = 0.0
_override = None  # tests inject a fake client here


def set_redis_client(client) -> None:
    """Replace the shared client (used by tests and scripts)."""
    global _override, _client
    _override = client
    _client = None


def _is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}


def get_redis():
    """Return a connected Redis client, or None when Redis is unavailable."""
    global _client, _last_failure
    if _override is not None:
        return _override
    if redis_lib is None:
        return None
    if _client is not None:
        return _client
    if time.monotonic() - _last_failure < _RETRY_AFTER_S and _last_failure:
        return None
    with _lock:
        if _client is not None:
            return _client
        settings = get_settings()
        if os.environ.get("VERCEL") and _is_local(settings.redis_url):
            # A serverless function has no Redis on localhost; trying costs ~2 s every retry window.
            _last_failure = time.monotonic()
            return None
        try:
            client = redis_lib.Redis.from_url(
                settings.redis_url,
                socket_timeout=2,
                socket_connect_timeout=2,
                health_check_interval=30,
                decode_responses=True,
            )
            client.ping()
        except Exception as exc:  # noqa: BLE001
            _last_failure = time.monotonic()
            logger.warning("Redis unavailable (%s); using in-process cache and rate limits", exc)
            return None
        _client = client
        return _client


def redis_status() -> dict:
    client = get_redis()
    if client is None:
        return {"ok": False, "backend": "memory"}
    try:
        client.ping()
        return {"ok": True, "backend": "redis"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "backend": "memory", "error": str(exc)}
