from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UsageRecord:
    """One model call (or one cache hit that avoided a call)."""

    agent: str
    model: str
    tier: str
    provider: str = "groq"
    purpose: str = ""
    tool: str | None = None
    section_key: str | None = None
    workflow_id: str | None = None
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    saved_tokens: int = 0
    saved_cost_usd: float = 0.0
    latency_ms: int = 0
    queue_time_ms: int = 0
    finish_reason: str | None = None
    status: str = "ok"
    error: str | None = None
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatCompletion:
    """Provider-neutral result of one chat completion."""

    text: str
    model: str
    finish_reason: str | None
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    queue_time_s: float = 0.0
    headers: dict[str, str] = field(default_factory=dict)
    request_id: str | None = None


@dataclass
class LLMResult:
    text: str
    model: str
    tier: str
    usage: UsageRecord
    cache_hit: bool = False
    parsed: Any = None
    finish_reason: str | None = None
