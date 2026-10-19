"""LLM service used by every agent.

Responsibilities, in call order:

1. **Routing** – each agent maps to a tier (`fast` or `frontier`), and each tier
   maps to a Groq model (see `Settings.llm_routes`).
2. **Response cache** – identical requests are served from Redis without a
   model call (sections, extractions, plans). Controlled per run with
   `cache_policy("use" | "refresh" | "off")`.
3. **Rate limiting** – per-model RPM/TPM ceilings, shared across workers via
   Redis, plus adaptive pauses from Groq's rate-limit headers.
4. **Provider prompt caching** – Groq caches prompt prefixes automatically on
   gpt-oss models. Agents put static instructions first and per-request data
   last so prefixes repeat byte-for-byte; cached tokens are recorded.
5. **Usage accounting** – every call (and every cache hit) becomes a
   `UsageRecord` in the active run, with tokens, cached tokens, cost and latency.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.llm.cache import ResponseCache
from app.llm.errors import (
    LLMBadRequestError,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMInvalidJSONError,
    LLMRateLimitError,
    LLMServiceError,
    LLMUnavailableError,
)
from app.llm.json_utils import parse_json
from app.llm.pricing import cost_usd
from app.llm.rate_limiter import LLMRateLimiter, SlidingWindowLimiter
from app.llm.types import ChatCompletion, LLMResult, UsageRecord
from app.llm.usage import current_cache_policy, current_tags, record_usage

logger = get_logger(__name__)

# Bump to invalidate every cached model response (for example after prompt changes
# that keep the same wording but should not reuse old outputs).
PROMPT_CACHE_VERSION = "2026-10-19.1"

_MAX_COMPLETION_CAP = 16384


@dataclass(frozen=True)
class ModelCapabilities:
    reasoning: bool
    strict_json_schema: bool
    prompt_caching: bool


def model_capabilities(model: str) -> ModelCapabilities:
    gpt_oss = model.startswith("openai/gpt-oss")
    return ModelCapabilities(reasoning=gpt_oss, strict_json_schema=gpt_oss, prompt_caching=gpt_oss)


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    chars = sum(len(m.get("content") or "") for m in messages)
    return chars // 3 + 8 * len(messages)


class LLMService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any = None,
        cache: ResponseCache | None = None,
        rate_limiter: LLMRateLimiter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        s = self.settings
        self._client = client
        self._client_lock = threading.Lock()
        self.cache = cache or ResponseCache(
            get_redis,
            namespace=s.cache_namespace,
            enabled=s.cache_enabled,
            local_max_items=s.cache_local_max_items,
        )
        self.rate_limiter = rate_limiter or LLMRateLimiter(
            SlidingWindowLimiter(get_redis, namespace=s.cache_namespace),
            self._limits_for,
            max_wait_s=s.llm_rate_limit_max_wait_s,
        )

    # ── configuration ─────────────────────────────────────────────────
    def _limits_for(self, model: str) -> tuple[int, int]:
        limits = self.settings.llm_rate_limits.get(model) or {}
        return (
            int(limits.get("rpm", self.settings.llm_default_rpm)),
            int(limits.get("tpm", self.settings.llm_default_tpm)),
        )

    @property
    def configured(self) -> bool:
        return self._client is not None or bool(self.settings.groq_key())

    @property
    def degraded_allowed(self) -> bool:
        return self.settings.llm_allow_degraded

    def ensure_configured(self) -> None:
        if not self.configured and not self.settings.llm_allow_degraded:
            raise LLMConfigurationError(
                "Groq is not configured. Set RFP_GROQ_API_KEY (or GROQ_API_KEY) to an API key "
                "created in your Groq organization."
            )

    @property
    def client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    key = self.settings.groq_key()
                    if not key:
                        if self.settings.llm_allow_degraded:
                            # Recoverable on purpose: agents fall back to heuristics in degraded mode.
                            raise LLMUnavailableError("No Groq API key configured; running in degraded mode.")
                        raise LLMConfigurationError("No Groq API key configured (RFP_GROQ_API_KEY).")
                    from app.llm.groq_client import GroqChatClient

                    self._client = GroqChatClient(
                        key,
                        base_url=self.settings.groq_base_url,
                        timeout_s=self.settings.llm_request_timeout_s,
                        max_retries=self.settings.llm_max_retries,
                    )
        return self._client

    @property
    def model(self) -> str:
        """Frontier model id (kept for callers that only need one name)."""
        return self.settings.llm_frontier_model

    def route(self, agent: str, tier: str | None = None) -> tuple[str, str]:
        chosen = tier or self.settings.llm_routes.get(agent, "frontier")
        if chosen not in ("fast", "frontier"):
            chosen = "frontier"
        model = self.settings.llm_fast_model if chosen == "fast" else self.settings.llm_frontier_model
        return chosen, model

    def describe(self) -> dict[str, Any]:
        s = self.settings
        return {
            "provider": s.llm_provider,
            "configured": self.configured,
            "organization_id": s.groq_org_id,
            "frontier_model": s.llm_frontier_model,
            "fast_model": s.llm_fast_model,
            "routes": s.llm_routes,
            "structured_outputs": s.llm_structured_outputs,
            "cache_backend": self.cache.backend(),
            "degraded_mode_allowed": s.llm_allow_degraded,
        }

    # ── public API ────────────────────────────────────────────────────
    def complete(
        self,
        *,
        agent: str,
        prompt: str | None = None,
        system: str | None = None,
        messages: list[dict[str, str]] | None = None,
        tier: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        expected_tokens: int | None = None,
        reasoning_effort: str | None = None,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "result",
        json_mode: bool = False,
        cache: bool = True,
        cache_kind: str = "llm",
        cache_ttl_s: int | None = None,
        purpose: str = "",
        section_key: str | None = None,
    ) -> LLMResult:
        s = self.settings
        msgs = list(messages) if messages else []
        if not msgs:
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt or ""})

        tier_name, model = self.route(agent, tier)
        caps = model_capabilities(model)
        want_json = json_mode or json_schema is not None
        response_format = self._response_format(caps, json_schema, schema_name, want_json)
        temp = temperature if temperature is not None else (0.0 if want_json else s.llm_temperature)
        max_tok = min(int(max_tokens or s.llm_max_completion_tokens), _MAX_COMPLETION_CAP)
        effort = None
        if caps.reasoning:
            effort = reasoning_effort or (
                s.llm_reasoning_effort_fast if tier_name == "fast" else s.llm_reasoning_effort_frontier
            )

        tags = current_tags()
        section = section_key or tags.get("section_key")
        tool = tags.get("tool")
        policy = current_cache_policy() if cache else "off"
        ttl = cache_ttl_s
        if ttl is None:
            ttl = s.cache_section_ttl_s if cache_kind == "section" else s.cache_llm_ttl_s
        cache_key = ResponseCache.make_key(
            cache_kind,
            {
                "v": PROMPT_CACHE_VERSION,
                "model": model,
                "messages": msgs,
                "temperature": temp,
                "max_tokens": max_tok,
                "effort": effort,
                "format": response_format,
            },
        )

        if policy == "use":
            hit = self.cache.get(cache_key)
            if hit and hit.get("text"):
                parsed = parse_json(hit["text"]) if want_json else None
                if not want_json or parsed is not None:
                    original = hit.get("usage") or {}
                    rec = UsageRecord(
                        agent=agent,
                        model=model,
                        tier=tier_name,
                        purpose=purpose,
                        tool=tool,
                        section_key=section,
                        cache_hit=True,
                        saved_tokens=int(original.get("total_tokens") or 0),
                        saved_cost_usd=float(original.get("cost_usd") or 0.0),
                        finish_reason=hit.get("finish_reason"),
                    )
                    record_usage(rec)
                    logger.info(
                        "llm cache hit agent=%s model=%s section=%s saved_tokens=%s",
                        agent, model, section, rec.saved_tokens,
                    )
                    return LLMResult(
                        text=hit["text"],
                        model=model,
                        tier=tier_name,
                        usage=rec,
                        cache_hit=True,
                        parsed=parsed,
                        finish_reason=hit.get("finish_reason"),
                    )

        completion, rec = self._call_with_recovery(
            agent=agent,
            model=model,
            tier=tier_name,
            messages=msgs,
            temperature=temp,
            max_tokens=max_tok,
            effort=effort,
            response_format=response_format,
            json_schema=json_schema,
            expected_tokens=expected_tokens,
            purpose=purpose,
            tool=tool,
            section=section,
        )
        parsed = parse_json(completion.text) if want_json else None
        if policy in ("use", "refresh") and completion.text and (not want_json or parsed is not None):
            self.cache.set(
                cache_key,
                {
                    "text": completion.text,
                    "model": completion.model,
                    "finish_reason": completion.finish_reason,
                    "usage": {
                        "prompt_tokens": rec.prompt_tokens,
                        "completion_tokens": rec.completion_tokens,
                        "total_tokens": rec.total_tokens,
                        "cost_usd": rec.cost_usd,
                    },
                    "created_at": rec.created_at,
                },
                ttl,
            )
        return LLMResult(
            text=completion.text,
            model=model,
            tier=tier_name,
            usage=rec,
            parsed=parsed,
            finish_reason=completion.finish_reason,
        )

    def complete_json(
        self,
        *,
        agent: str,
        system: str | None = None,
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        schema: dict[str, Any] | None = None,
        schema_name: str = "result",
        **kwargs: Any,
    ) -> LLMResult:
        """Call the model for a JSON object; repair once if the output does not parse."""
        purpose = kwargs.pop("purpose", "")
        result = self.complete(
            agent=agent,
            system=system,
            prompt=prompt,
            messages=messages,
            json_schema=schema,
            schema_name=schema_name,
            json_mode=True,
            purpose=purpose,
            **kwargs,
        )
        if isinstance(result.parsed, dict):
            return result
        base = list(messages) if messages else (
            ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt or ""}]
        )
        repair = base + [
            {"role": "assistant", "content": (result.text or "")[:4000]},
            {"role": "user", "content": "That was not a valid JSON object. Return only the JSON object, with no prose."},
        ]
        kwargs.pop("cache", None)
        kwargs.pop("reasoning_effort", None)
        retry = self.complete(
            agent=agent,
            messages=repair,
            json_schema=schema,
            schema_name=schema_name,
            json_mode=True,
            purpose=f"{purpose}:repair" if purpose else "repair",
            cache=False,
            reasoning_effort="low",
            **kwargs,
        )
        if isinstance(retry.parsed, dict):
            return retry
        raise LLMInvalidJSONError(f"{agent}: the model did not return valid JSON")

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        agent: str = "general",
        **kwargs: Any,
    ) -> str:
        """Text-only convenience wrapper kept for older call sites."""
        return self.complete(
            agent=agent,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ).text

    # ── internals ─────────────────────────────────────────────────────
    def _response_format(
        self,
        caps: ModelCapabilities,
        schema: dict[str, Any] | None,
        name: str,
        want_json: bool,
    ) -> dict[str, Any] | None:
        if not want_json:
            return None
        if schema is not None and caps.strict_json_schema and self.settings.llm_structured_outputs:
            return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
        return {"type": "json_object"}

    def _call_with_recovery(
        self,
        *,
        agent: str,
        model: str,
        tier: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        effort: str | None,
        response_format: dict[str, Any] | None,
        json_schema: dict[str, Any] | None,
        expected_tokens: int | None,
        purpose: str,
        tool: str | None,
        section: str | None,
    ) -> tuple[ChatCompletion, UsageRecord]:
        call = dict(
            agent=agent, model=model, tier=tier, temperature=temperature,
            expected_tokens=expected_tokens, purpose=purpose, tool=tool, section=section,
        )
        try:
            completion, rec = self._call_once(
                messages=messages, max_tokens=max_tokens, effort=effort, response_format=response_format, **call
            )
        except LLMBadRequestError as exc:
            if not (response_format and response_format.get("type") == "json_schema"):
                raise
            # Fall back to JSON-object mode with the schema described in the prompt.
            logger.warning("Structured output rejected for %s (%s); retrying in JSON object mode", model, exc)
            response_format = {"type": "json_object"}
            messages = messages[:-1] + [
                {
                    "role": messages[-1]["role"],
                    "content": messages[-1]["content"]
                    + "\n\nReturn a JSON object that matches this JSON Schema:\n"
                    + json.dumps(json_schema, ensure_ascii=False),
                }
            ]
            completion, rec = self._call_once(
                messages=messages, max_tokens=max_tokens, effort=effort, response_format=response_format, **call
            )

        if not completion.text and completion.finish_reason == "length":
            # Reasoning used the whole budget. Retry once with more room and less reasoning.
            completion, rec = self._call_once(
                messages=messages,
                max_tokens=min(max_tokens * 2, _MAX_COMPLETION_CAP),
                effort="low" if effort else None,
                response_format=response_format,
                **call,
            )
        if not completion.text:
            raise LLMEmptyResponseError(
                f"{model} returned no content for {agent} (finish_reason={completion.finish_reason})"
            )
        return completion, rec

    def _call_once(
        self,
        *,
        agent: str,
        model: str,
        tier: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        effort: str | None,
        response_format: dict[str, Any] | None,
        expected_tokens: int | None,
        purpose: str,
        tool: str | None,
        section: str | None,
    ) -> tuple[ChatCompletion, UsageRecord]:
        base = dict(agent=agent, model=model, tier=tier, purpose=purpose, tool=tool, section_key=section)
        prompt_est = estimate_tokens(messages)
        estimate = prompt_est + int(expected_tokens or min(max_tokens, 1500))
        try:
            reservation = self.rate_limiter.acquire(model, estimate)
        except LLMRateLimitError as exc:
            record_usage(UsageRecord(**base, status="rate_limited", error=str(exc)))
            raise

        caps = model_capabilities(model)
        started = time.perf_counter()
        actual_tokens = 0
        try:
            completion = self.client.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                reasoning_effort=effort,
                include_reasoning=False if caps.reasoning else None,
                response_format=response_format,
            )
            actual_tokens = completion.total_tokens or (prompt_est + completion.completion_tokens)
        except LLMRateLimitError as exc:
            self.rate_limiter.penalize(model, exc.retry_after)
            record_usage(UsageRecord(**base, status="rate_limited", error=str(exc),
                                     latency_ms=int((time.perf_counter() - started) * 1000)))
            raise
        except LLMServiceError as exc:
            record_usage(UsageRecord(**base, status="error", error=str(exc),
                                     latency_ms=int((time.perf_counter() - started) * 1000)))
            raise
        finally:
            self.rate_limiter.settle(reservation, actual_tokens)

        self.rate_limiter.observe_headers(model, completion.headers)
        latency_ms = int((time.perf_counter() - started) * 1000)
        rec = UsageRecord(
            **base,
            prompt_tokens=completion.prompt_tokens,
            cached_prompt_tokens=completion.cached_prompt_tokens,
            completion_tokens=completion.completion_tokens,
            reasoning_tokens=completion.reasoning_tokens,
            total_tokens=completion.total_tokens,
            cost_usd=cost_usd(
                self.settings.llm_pricing,
                model,
                prompt_tokens=completion.prompt_tokens,
                cached_prompt_tokens=completion.cached_prompt_tokens,
                completion_tokens=completion.completion_tokens,
            ),
            latency_ms=latency_ms,
            queue_time_ms=int(completion.queue_time_s * 1000),
            finish_reason=completion.finish_reason,
            status="ok" if completion.text else "empty",
        )
        record_usage(rec)
        logger.info(
            "llm call agent=%s model=%s section=%s prompt=%s cached=%s completion=%s latency_ms=%s",
            agent, model, section, rec.prompt_tokens, rec.cached_prompt_tokens, rec.completion_tokens, latency_ms,
        )
        return completion, rec


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()


__all__ = [
    "LLMService",
    "LLMServiceError",
    "PROMPT_CACHE_VERSION",
    "estimate_tokens",
    "get_llm_service",
    "model_capabilities",
]
