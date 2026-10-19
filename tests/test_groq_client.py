"""GroqChatClient against a mocked HTTP transport (no network)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.llm.errors import LLMAuthError, LLMBadRequestError, LLMRateLimitError
from app.llm.groq_client import GroqChatClient

COMPLETION = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1760000000,
    "model": "openai/gpt-oss-120b",
    "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": "  Hello section  ", "reasoning": "hidden"}}],
    "usage": {
        "prompt_tokens": 1200, "completion_tokens": 300, "total_tokens": 1500, "queue_time": 0.02,
        "prompt_tokens_details": {"cached_tokens": 1024},
        "completion_tokens_details": {"reasoning_tokens": 120},
    },
    "x_groq": {"id": "req_abc"},
}


def _client(handler) -> tuple[GroqChatClient, list[dict]]:
    seen: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(wrapped))
    return GroqChatClient("gsk_test", max_retries=0, http_client=http), seen


def test_request_body_and_usage_parsing():
    client, seen = _client(lambda r: httpx.Response(
        200, json=COMPLETION, headers={"x-ratelimit-remaining-tokens": "7000", "x-ratelimit-limit-tokens": "8000"}))
    result = client.chat(
        model="openai/gpt-oss-120b",
        messages=[{"role": "system", "content": "rules"}, {"role": "user", "content": "go"}],
        temperature=0.3,
        max_completion_tokens=2000,
        reasoning_effort="medium",
        include_reasoning=False,
        response_format={"type": "json_schema", "json_schema": {"name": "x", "strict": True, "schema": {"type": "object"}}},
    )
    body = seen[0]["body"]
    assert seen[0]["url"].endswith("/openai/v1/chat/completions")
    assert seen[0]["headers"]["authorization"] == "Bearer gsk_test"
    assert body["model"] == "openai/gpt-oss-120b" and body["max_completion_tokens"] == 2000
    assert body["reasoning_effort"] == "medium" and body["include_reasoning"] is False
    assert body["response_format"]["json_schema"]["strict"] is True
    assert result.text == "Hello section"
    assert (result.prompt_tokens, result.cached_prompt_tokens, result.completion_tokens) == (1200, 1024, 300)
    assert result.reasoning_tokens == 120 and result.total_tokens == 1500
    assert result.headers["x-ratelimit-remaining-tokens"] == "7000"
    assert result.request_id == "req_abc"


@pytest.mark.parametrize(
    "status,headers,error",
    [
        (429, {"retry-after": "12"}, LLMRateLimitError),
        (401, {}, LLMAuthError),
        (400, {}, LLMBadRequestError),
    ],
)
def test_error_mapping(status, headers, error):
    client, _ = _client(lambda r: httpx.Response(status, json={"error": {"message": "nope"}}, headers=headers))
    with pytest.raises(error) as info:
        client.chat(model="openai/gpt-oss-20b", messages=[{"role": "user", "content": "x"}],
                    temperature=0, max_completion_tokens=10)
    assert "nope" in str(info.value)
    if status == 429:
        assert info.value.retry_after == 12.0
