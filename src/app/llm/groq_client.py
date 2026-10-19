"""Thin wrapper over the official Groq SDK.

Returns a provider-neutral `ChatCompletion` with token usage (including
`prompt_tokens_details.cached_tokens` from Groq's automatic prompt caching)
and the response headers the rate limiter needs.
"""
from __future__ import annotations

from typing import Any

from app.llm.errors import (
    LLMAuthError,
    LLMBadRequestError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.rate_limiter import parse_duration
from app.llm.types import ChatCompletion


def _retry_after(response: Any) -> float | None:
    if response is None:
        return None
    headers = getattr(response, "headers", None) or {}
    return parse_duration(headers.get("retry-after")) or parse_duration(headers.get("x-ratelimit-reset-tokens"))


def _error_detail(exc: Any) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        message = err.get("message") if isinstance(err, dict) else None
        if message:
            return str(message)
    return str(exc)


class GroqChatClient:
    provider = "groq"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout_s: float = 90.0,
        max_retries: int = 3,
        http_client: Any = None,
    ) -> None:
        import groq

        self._groq = groq
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_s, "max_retries": max_retries}
        if base_url:
            kwargs["base_url"] = base_url
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = groq.Groq(**kwargs)

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_completion_tokens: int,
        reasoning_effort: str | None = None,
        include_reasoning: bool | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        groq = self._groq
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
        }
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
        if include_reasoning is not None:
            params["include_reasoning"] = include_reasoning
        if response_format:
            params["response_format"] = response_format

        try:
            raw = self._client.chat.completions.with_raw_response.create(**params)
            completion = raw.parse()
        except groq.RateLimitError as exc:
            raise LLMRateLimitError(
                f"Groq rate limit for {model}: {_error_detail(exc)}",
                retry_after=_retry_after(getattr(exc, "response", None)),
            ) from exc
        except (groq.AuthenticationError, groq.PermissionDeniedError) as exc:
            raise LLMAuthError(f"Groq rejected the API key: {_error_detail(exc)}") from exc
        except (groq.BadRequestError, groq.UnprocessableEntityError, groq.NotFoundError) as exc:
            raise LLMBadRequestError(f"Groq rejected the request for {model}: {_error_detail(exc)}") from exc
        except groq.APITimeoutError as exc:
            raise LLMTimeoutError(f"Groq request to {model} timed out") from exc
        except groq.APIConnectionError as exc:
            raise LLMUnavailableError(f"Could not reach Groq: {exc}") from exc
        except groq.APIStatusError as exc:
            raise LLMUnavailableError(f"Groq returned HTTP {exc.status_code}: {_error_detail(exc)}") from exc

        choice = completion.choices[0] if completion.choices else None
        text = (choice.message.content or "") if choice and choice.message else ""
        usage = completion.usage
        cached = 0
        reasoning = 0
        if usage is not None:
            details = getattr(usage, "prompt_tokens_details", None)
            cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
            cdetails = getattr(usage, "completion_tokens_details", None)
            reasoning = int(getattr(cdetails, "reasoning_tokens", 0) or 0) if cdetails else 0
        x_groq = getattr(completion, "x_groq", None)
        request_id = getattr(x_groq, "id", None) if x_groq is not None else None
        return ChatCompletion(
            text=text.strip(),
            model=completion.model or model,
            finish_reason=getattr(choice, "finish_reason", None) if choice else None,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            cached_prompt_tokens=cached,
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            reasoning_tokens=reasoning,
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            queue_time_s=float(getattr(usage, "queue_time", 0.0) or 0.0),
            headers={k.lower(): v for k, v in raw.headers.items()},
            request_id=request_id,
        )
