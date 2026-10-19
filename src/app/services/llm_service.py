"""Compatibility shim: the LLM service now lives in `app.llm`."""
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService, get_llm_service

__all__ = ["LLMService", "LLMServiceError", "get_llm_service"]
