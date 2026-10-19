"""Rate limiting.

`SlidingWindowLimiter` is a 60-second sliding-window counter (current window
plus the overlapping share of the previous one). With Redis it is shared by
every API worker; without Redis it falls back to a per-process store.

`LLMRateLimiter` uses it to keep each model under its requests-per-minute and
tokens-per-minute ceilings. It also reads Groq's `x-ratelimit-*` headers and
`retry-after` on 429s, and pauses that model until the provider window resets.
"""
from __future__ import annotations

import random
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.llm.errors import LLMRateLimitError

logger = get_logger(__name__)

WINDOW_S = 60

_ACQUIRE_LUA = """
local weight = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local n = #KEYS / 2
for i = 1, n do
  local limit = tonumber(ARGV[1 + 2 * i])
  local cost = tonumber(ARGV[2 + 2 * i])
  if limit > 0 then
    local cur = tonumber(redis.call('GET', KEYS[2 * i - 1]) or '0')
    local prev = tonumber(redis.call('GET', KEYS[2 * i]) or '0')
    local used = cur + prev * weight
    if used > 0 and used + cost > limit then
      return 0
    end
  end
end
for i = 1, n do
  local cost = tonumber(ARGV[2 + 2 * i])
  redis.call('INCRBY', KEYS[2 * i - 1], cost)
  redis.call('EXPIRE', KEYS[2 * i - 1], ttl)
end
return 1
"""

_ADJUST_LUA = """
local v = redis.call('INCRBY', KEYS[1], ARGV[1])
if v < 0 then redis.call('SET', KEYS[1], 0) end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return v
"""

_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration(value: str | None) -> float | None:
    """Parse Groq reset values such as '7.66s', '2m59.56s', '1h2m', '350ms', or '12'."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    total = 0.0
    matched = False
    for number, unit in _DURATION_PART.findall(text):
        matched = True
        n = float(number)
        total += {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}[unit] * n
    return total if matched else None


class _MemoryStore:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._pauses: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, pairs: list[tuple[str, str]], limits: list[tuple[int, int]], weight: float) -> bool:
        with self._lock:
            for (cur, prev), (limit, cost) in zip(pairs, limits):
                if limit <= 0:
                    continue
                used = self._counts.get(cur, 0) + self._counts.get(prev, 0) * weight
                if used > 0 and used + cost > limit:
                    return False
            for (cur, _), (_, cost) in zip(pairs, limits):
                self._counts[cur] = self._counts.get(cur, 0) + cost
            if len(self._counts) > 10_000:
                self._counts.clear()
            return True

    def adjust(self, key: str, delta: int) -> None:
        with self._lock:
            self._counts[key] = max(0, self._counts.get(key, 0) + delta)

    def get_pause(self, name: str) -> float:
        with self._lock:
            return self._pauses.get(name, 0.0)

    def set_pause(self, name: str, until: float) -> None:
        with self._lock:
            self._pauses[name] = max(until, self._pauses.get(name, 0.0))


class SlidingWindowLimiter:
    def __init__(self, redis_getter: Callable[[], Any], *, namespace: str = "rfp") -> None:
        self._redis_getter = redis_getter
        self.namespace = namespace
        self._memory = _MemoryStore()
        self._scripts: dict[int, tuple[Any, Any]] = {}

    def _redis(self):
        return self._redis_getter()

    def _script(self, client):
        cached = self._scripts.get(id(client))
        if cached is None:
            cached = (client.register_script(_ACQUIRE_LUA), client.register_script(_ADJUST_LUA))
            self._scripts[id(client)] = cached
        return cached

    def _key(self, name: str, window: int) -> str:
        return f"{self.namespace}:rl:{name}:{window}"

    def try_acquire(self, counters: list[tuple[str, int, int]], now: float | None = None) -> tuple[bool, int]:
        """Atomically add `cost` to every counter if all stay within `limit`.

        `counters` is a list of (name, limit, cost); limit <= 0 means unlimited.
        Returns (acquired, window_index).
        """
        now = time.time() if now is None else now
        window = int(now // WINDOW_S)
        weight = 1.0 - (now % WINDOW_S) / WINDOW_S
        pairs = [(self._key(name, window), self._key(name, window - 1)) for name, _, _ in counters]
        limits = [(int(limit), int(cost)) for _, limit, cost in counters]
        client = self._redis()
        if client is not None:
            try:
                acquire, _ = self._script(client)
                keys = [k for pair in pairs for k in pair]
                args: list[Any] = [weight, WINDOW_S * 2]
                for limit, cost in limits:
                    args.extend([limit, cost])
                return bool(acquire(keys=keys, args=args)), window
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis rate limiter failed, using memory: %s", exc)
        return self._memory.acquire(pairs, limits, weight), window

    def adjust(self, name: str, window: int, delta: int) -> None:
        if delta == 0:
            return
        key = self._key(name, window)
        client = self._redis()
        if client is not None:
            try:
                _, adjust = self._script(client)
                adjust(keys=[key], args=[int(delta), WINDOW_S * 2])
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis rate limiter adjust failed: %s", exc)
        self._memory.adjust(key, int(delta))

    def get_pause(self, name: str) -> float:
        client = self._redis()
        if client is not None:
            try:
                raw = client.get(f"{self.namespace}:rl:{name}:pause")
                return float(raw) if raw else 0.0
            except Exception:  # noqa: BLE001
                pass
        return self._memory.get_pause(name)

    def set_pause(self, name: str, until: float) -> None:
        ttl_ms = max(1, int((until - time.time()) * 1000))
        client = self._redis()
        if client is not None:
            try:
                key = f"{self.namespace}:rl:{name}:pause"
                current = client.get(key)
                if not current or float(current) < until:
                    client.set(key, f"{until:.3f}", px=ttl_ms)
                return
            except Exception:  # noqa: BLE001
                pass
        self._memory.set_pause(name, until)


@dataclass
class Reservation:
    model: str
    window: int
    tokens: int


class LLMRateLimiter:
    """Per-model RPM/TPM limiter that blocks (up to `max_wait_s`) instead of failing fast."""

    def __init__(
        self,
        limiter: SlidingWindowLimiter,
        limits_for: Callable[[str], tuple[int, int]],
        *,
        max_wait_s: float = 90.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.limiter = limiter
        self.limits_for = limits_for
        self.max_wait_s = max_wait_s
        self._sleep = sleep

    def acquire(self, model: str, est_tokens: int) -> Reservation:
        rpm, tpm = self.limits_for(model)
        est_tokens = max(1, int(est_tokens))
        deadline = time.time() + self.max_wait_s
        while True:
            now = time.time()
            pause_until = self.limiter.get_pause(model)
            if pause_until > now:
                wait = pause_until - now
                if now + wait > deadline:
                    raise LLMRateLimitError(
                        f"{model} is paused by the provider rate limit for {wait:.0f}s more",
                        retry_after=wait,
                    )
                self._sleep(min(wait, 5.0))
                continue
            acquired, window = self.limiter.try_acquire(
                [(f"{model}:req", rpm, 1), (f"{model}:tok", tpm, est_tokens)], now=now
            )
            if acquired:
                return Reservation(model=model, window=window, tokens=est_tokens)
            if now >= deadline:
                retry = WINDOW_S - (now % WINDOW_S)
                raise LLMRateLimitError(
                    f"Local rate limit for {model} ({rpm} req/min, {tpm} tokens/min) still exhausted "
                    f"after waiting {self.max_wait_s:.0f}s",
                    retry_after=retry,
                )
            self._sleep(min(1.0 + random.random() * 0.5, max(0.05, deadline - now)))

    def settle(self, reservation: Reservation, actual_tokens: int) -> None:
        """Replace the reserved token estimate with what the call actually used."""
        delta = int(actual_tokens) - reservation.tokens
        self.limiter.adjust(f"{reservation.model}:tok", reservation.window, delta)

    def penalize(self, model: str, retry_after: float | None) -> None:
        wait = retry_after if retry_after and retry_after > 0 else 5.0
        self.limiter.set_pause(model, time.time() + wait)
        logger.warning("Provider rate limit hit for %s; pausing %.1fs", model, wait)

    def observe_headers(self, model: str, headers: dict[str, str] | None) -> None:
        """Pause the model early when the provider says its window is nearly spent."""
        if not headers:
            return
        lowered = {k.lower(): v for k, v in headers.items()}
        try:
            remaining_tokens = int(float(lowered.get("x-ratelimit-remaining-tokens", "")))
            limit_tokens = int(float(lowered.get("x-ratelimit-limit-tokens", "")))
        except ValueError:
            remaining_tokens = limit_tokens = -1
        if limit_tokens > 0 and 0 <= remaining_tokens < max(1, int(limit_tokens * 0.05)):
            reset = parse_duration(lowered.get("x-ratelimit-reset-tokens"))
            if reset:
                self.limiter.set_pause(model, time.time() + reset)
        try:
            remaining_requests = int(float(lowered.get("x-ratelimit-remaining-requests", "")))
        except ValueError:
            remaining_requests = -1
        if remaining_requests == 0:
            reset = parse_duration(lowered.get("x-ratelimit-reset-requests"))
            if reset:
                self.limiter.set_pause(model, time.time() + reset)


class ApiRateLimiter:
    """Inbound request limiter keyed by API key or client address."""

    def __init__(self, limiter: SlidingWindowLimiter) -> None:
        self.limiter = limiter

    def hit(self, identity: str, limit_per_minute: int) -> tuple[bool, float]:
        if limit_per_minute <= 0:
            return True, 0.0
        now = time.time()
        acquired, _ = self.limiter.try_acquire([(f"api:{identity}", limit_per_minute, 1)], now=now)
        return acquired, (0.0 if acquired else WINDOW_S - (now % WINDOW_S))
