"""Live progress events from a running workflow.

A caller installs a sink with `event_sink(callback)`; trace entries and per-section
progress are passed to it as they happen. Worker threads started with
`contextvars.copy_context()` inherit the sink, so the callback must be thread-safe
(`queue.Queue.put` is).
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_sink: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("workflow_event_sink", default=None)


@contextmanager
def event_sink(callback: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    token = _sink.set(callback)
    try:
        yield
    finally:
        _sink.reset(token)


def emit(event_type: str, **data: Any) -> None:
    callback = _sink.get()
    if callback is None:
        return
    try:
        callback({"type": event_type, **data})
    except Exception as exc:  # noqa: BLE001 — progress reporting must never break a run
        logger.warning("Event sink failed: %s", exc)
