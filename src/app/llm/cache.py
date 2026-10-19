"""Response cache for model outputs (generated sections, extractions, plans).

Keys are SHA-256 hashes of everything that determines the output (model,
messages, sampling params, prompt version), so a cached value is only reused
when the exact same request would be sent again. Redis is the shared store;
when it is unavailable a bounded in-process LRU keeps the platform working.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ResponseCache:
    def __init__(
        self,
        redis_getter: Callable[[], Any],
        *,
        namespace: str = "rfp",
        enabled: bool = True,
        local_max_items: int = 512,
    ) -> None:
        self._redis_getter = redis_getter
        self.namespace = namespace
        self.enabled = enabled
        self._local_max = local_max_items
        self._local: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def make_key(kind: str, payload: Any) -> str:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return f"{kind}:{hashlib.sha256(blob.encode('utf-8')).hexdigest()}"

    def _full(self, key: str) -> str:
        return f"{self.namespace}:cache:{key}"

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        client = self._redis_getter()
        if client is not None:
            try:
                raw = client.get(self._full(key))
                return json.loads(raw) if raw else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cache read failed, falling back to memory: %s", exc)
        with self._lock:
            entry = self._local.get(key)
            if entry is None:
                return None
            expires_at, raw = entry
            if expires_at and expires_at < time.time():
                self._local.pop(key, None)
                return None
            self._local.move_to_end(key)
            return json.loads(raw)

    def set(self, key: str, value: dict, ttl_s: int) -> None:
        if not self.enabled:
            return
        raw = json.dumps(value, ensure_ascii=False, default=str)
        client = self._redis_getter()
        if client is not None:
            try:
                if ttl_s > 0:
                    client.set(self._full(key), raw, ex=ttl_s)
                else:
                    client.set(self._full(key), raw)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cache write failed, falling back to memory: %s", exc)
        if self._local_max <= 0:
            return
        with self._lock:
            self._local[key] = (time.time() + ttl_s if ttl_s > 0 else 0.0, raw)
            self._local.move_to_end(key)
            while len(self._local) > self._local_max:
                self._local.popitem(last=False)

    def delete(self, key: str) -> None:
        client = self._redis_getter()
        if client is not None:
            try:
                client.delete(self._full(key))
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self._local.pop(key, None)

    def backend(self) -> str:
        return "redis" if self._redis_getter() is not None else "memory"
