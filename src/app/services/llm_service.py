"""LLM service.

Talks to Ollama's local HTTP API (default: http://localhost:11434) using the
`/api/chat` endpoint. The default model is `mistral:latest` (Mistral 7B Instruct
quantized, ~4.4 GB) which runs with Metal acceleration on Apple Silicon.

Why Ollama over transformers/HF directly:
- Quantized GGUF weights -> 5–10x faster on Mac M-series
- Daemon-based: model stays in memory between requests
- Single HTTP dep -> no torch/transformers in the request path
"""
from __future__ import annotations

from functools import lru_cache

import requests

from app.core.config import get_settings


class LLMServiceError(RuntimeError):
    """Raised when the LLM backend is unreachable, times out, or returns an error."""


class LLMService:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_s: int | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.context_window = settings.llm_context_window
        self.timeout_s = timeout_s or settings.llm_request_timeout_s

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": self.context_window,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=body,
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout as exc:
            raise LLMServiceError(f"LLM call timed out after {self.timeout_s}s") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMServiceError(f"LLM request failed: {exc}") from exc
        except ValueError as exc:  # JSON decode error
            raise LLMServiceError(f"LLM returned invalid JSON: {exc}") from exc

        return (data.get("message", {}).get("content") or "").strip()


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()
