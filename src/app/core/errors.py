"""Application errors and their HTTP mapping."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_var
from app.llm.errors import (
    LLMAuthError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMServiceError,
)

logger = get_logger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class InvalidRequestError(AppError):
    status_code = 422
    code = "invalid_request"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


def describe_exception(exc: Exception) -> tuple[int, str, str, float | None]:
    """(status, code, message, retry_after) for any exception, matching the HTTP handlers."""
    if isinstance(exc, AppError):
        return exc.status_code, exc.code, exc.message, exc.retry_after
    if isinstance(exc, LLMConfigurationError):
        return 503, "llm_not_configured", str(exc), None
    if isinstance(exc, LLMAuthError):
        return 502, "llm_auth_failed", str(exc), None
    if isinstance(exc, LLMRateLimitError):
        return 429, "llm_rate_limited", str(exc), exc.retry_after or 10
    if isinstance(exc, LLMServiceError):
        return 502, "llm_error", str(exc), None
    return 500, "internal_error", "Unexpected server error. Check the API logs with this request id.", None


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}


def _response(status: int, code: str, message: str, retry_after: float | None = None) -> JSONResponse:
    headers = {"Retry-After": str(max(1, int(round(retry_after))))} if retry_after else None
    return JSONResponse(status_code=status, content=_body(code, message), headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _response(exc.status_code, exc.code, exc.message, exc.retry_after)

    @app.exception_handler(LLMConfigurationError)
    async def _llm_config(_: Request, exc: LLMConfigurationError) -> JSONResponse:
        return _response(503, "llm_not_configured", str(exc))

    @app.exception_handler(LLMAuthError)
    async def _llm_auth(_: Request, exc: LLMAuthError) -> JSONResponse:
        return _response(502, "llm_auth_failed", str(exc))

    @app.exception_handler(LLMRateLimitError)
    async def _llm_rate(_: Request, exc: LLMRateLimitError) -> JSONResponse:
        return _response(429, "llm_rate_limited", str(exc), exc.retry_after or 10)

    @app.exception_handler(LLMServiceError)
    async def _llm_error(_: Request, exc: LLMServiceError) -> JSONResponse:
        return _response(502, "llm_error", str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return _response(500, "internal_error", "Unexpected server error. Check the API logs with this request id.")
