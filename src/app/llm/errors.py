"""LLM error hierarchy. Every provider failure maps to one of these."""
from __future__ import annotations


class LLMServiceError(RuntimeError):
    """Base class: the model call failed or could not be made."""


class LLMConfigurationError(LLMServiceError):
    """The provider is not configured (for example, no API key)."""


class LLMAuthError(LLMServiceError):
    """The provider rejected the credentials."""


class LLMRateLimitError(LLMServiceError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMBadRequestError(LLMServiceError):
    """The provider rejected the request body (schema, params, context length)."""


class LLMTimeoutError(LLMServiceError):
    pass


class LLMUnavailableError(LLMServiceError):
    """Network failure or 5xx from the provider."""


class LLMEmptyResponseError(LLMServiceError):
    """The model returned no usable content."""


class LLMInvalidJSONError(LLMServiceError):
    """The model did not return parseable JSON after a repair attempt."""
