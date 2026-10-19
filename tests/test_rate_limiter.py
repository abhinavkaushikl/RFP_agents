from __future__ import annotations

import time

import fakeredis
import pytest

from app.llm.errors import LLMRateLimitError
from app.llm.rate_limiter import ApiRateLimiter, LLMRateLimiter, SlidingWindowLimiter, parse_duration


@pytest.mark.parametrize(
    "value,expected",
    [("7.66s", 7.66), ("2m59.56s", 179.56), ("1h2m3s", 3723.0), ("350ms", 0.35), ("12", 12.0), (None, None), ("", None)],
)
def test_parse_duration(value, expected):
    result = parse_duration(value)
    assert (result is None and expected is None) or result == pytest.approx(expected)


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_sliding_window_blocks_over_limit(backend):
    client = fakeredis.FakeRedis(decode_responses=True) if backend == "redis" else None
    limiter = SlidingWindowLimiter(lambda: client, namespace="t")
    now = 1_000_000.0 * 60  # start of a window
    assert limiter.try_acquire([("m:tok", 100, 60)], now=now)[0]
    assert not limiter.try_acquire([("m:tok", 100, 60)], now=now + 1)[0]
    assert limiter.try_acquire([("m:tok", 100, 30)], now=now + 1)[0]


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_settle_returns_unused_tokens(backend):
    client = fakeredis.FakeRedis(decode_responses=True) if backend == "redis" else None
    limiter = SlidingWindowLimiter(lambda: client, namespace="t")
    now = 2_000_000.0 * 60
    ok, window = limiter.try_acquire([("m:tok", 100, 90)], now=now)
    assert ok
    limiter.adjust("m:tok", window, -80)  # call used 10, not 90
    assert limiter.try_acquire([("m:tok", 100, 80)], now=now + 1)[0]


def test_single_oversized_request_passes_in_empty_window():
    limiter = SlidingWindowLimiter(lambda: None, namespace="t")
    assert limiter.try_acquire([("m:tok", 100, 500)], now=3_000_000.0 * 60)[0]


def test_llm_limiter_waits_then_raises():
    limiter = LLMRateLimiter(SlidingWindowLimiter(lambda: None), lambda m: (1, 0), max_wait_s=0.2, sleep=lambda s: None)
    limiter.acquire("m", 10)
    with pytest.raises(LLMRateLimitError):
        limiter.acquire("m", 10)


def test_headers_trigger_pause():
    store = SlidingWindowLimiter(lambda: None)
    limiter = LLMRateLimiter(store, lambda m: (0, 0), max_wait_s=0.1, sleep=lambda s: None)
    limiter.observe_headers("m", {"x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "100",
                                  "x-ratelimit-reset-tokens": "30s"})
    assert store.get_pause("m") > time.time() + 20
    with pytest.raises(LLMRateLimitError):
        limiter.acquire("m", 10)


def test_api_rate_limiter_per_identity():
    shared = fakeredis.FakeRedis(decode_responses=True)
    api = ApiRateLimiter(SlidingWindowLimiter(lambda: shared))
    assert api.hit("a", 2)[0] and api.hit("a", 2)[0]
    allowed, retry = api.hit("a", 2)
    assert not allowed and retry > 0
    assert api.hit("b", 2)[0]
    assert api.hit("a", 0)[0]  # 0 disables
