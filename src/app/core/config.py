from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RFP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RFP Proposal Platform"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://abhinavkaushik@localhost:5432/proposal_platform"
    redis_url: str = "redis://localhost:6379/0"
    embedding_dimensions: int = Field(default=384, ge=1)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = "ollama"
    llm_model: str = "mistral:latest"
    llm_base_url: str = "http://localhost:11434"
    llm_temperature: float = Field(default=0.4, ge=0.0, le=1.5)
    llm_max_tokens: int = Field(default=450, ge=50)
    llm_context_window: int = Field(default=4096, ge=512)
    llm_request_timeout_s: int = Field(default=300, ge=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
