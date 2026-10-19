"""Application settings.

Every value can be overridden with an environment variable prefixed `RFP_`
(for example `RFP_LLM_FRONTIER_MODEL`) or through a `.env` file at the
project root. Dict-valued settings take JSON.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Which model tier each agent uses. Fast = small, cheap, low-latency decisions
# and light extraction. Frontier = long-form writing and deep analysis.
DEFAULT_LLM_ROUTES: dict[str, str] = {
    "supervisor": "fast",
    "intent_detection": "fast",
    "problem_framing": "fast",
    "market_research": "fast",
    "request_structuring": "frontier",
    "solution_comparison": "frontier",
    "generation": "frontier",
    "revision": "frontier",
    "scoring": "frontier",
    "buyer_intelligence": "frontier",
    "product_fit": "frontier",
}

# USD per 1M tokens, from Groq's model pages (October 2026). Override with
# RFP_LLM_PRICING if your contract differs.
DEFAULT_LLM_PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-oss-120b": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.075, "cached_input": 0.037, "output": 0.30},
}

# Client-side ceilings per model. Defaults match Groq's lowest published tier so
# the platform never trips 429s out of the box; raise them to your org's limits.
DEFAULT_LLM_RATE_LIMITS: dict[str, dict[str, int]] = {
    "openai/gpt-oss-120b": {"rpm": 30, "tpm": 8000},
    "openai/gpt-oss-20b": {"rpm": 30, "tpm": 8000},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RFP_",
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────
    app_name: str = "RFP Proposal Platform"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False
    api_prefix: str = "/api"
    api_keys: str = Field(default="", description="Comma-separated API keys; empty disables auth")
    cors_origins: str = "http://localhost:5173,http://localhost:8501"
    api_rate_limit_per_minute: int = Field(default=60, ge=0, description="Per client; 0 disables")

    # ── Storage ────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://localhost:5432/proposal_platform"
    redis_url: str = "redis://localhost:6379/0"
    redis_required: bool = False
    persist_runs: bool = True

    # ── Domain ─────────────────────────────────────────────────────────
    domain_profile_dir: str = "configs/domain_profiles"
    default_profile: str = "default"

    # ── Embeddings ─────────────────────────────────────────────────────
    embedding_dimensions: int = Field(default=384, ge=1)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── LLM (Groq) ─────────────────────────────────────────────────────
    llm_provider: Literal["groq"] = "groq"
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("RFP_GROQ_API_KEY", "GROQ_API_KEY")
    )
    # Groq scopes API keys to an organization, so the org is chosen by the key.
    # This id is recorded in usage reports and the readiness check for traceability.
    groq_org_id: str | None = None
    groq_base_url: str | None = None
    llm_frontier_model: str = "openai/gpt-oss-120b"
    llm_fast_model: str = "openai/gpt-oss-20b"
    llm_route_overrides: dict[str, str] = Field(default_factory=dict)
    llm_reasoning_effort_frontier: Literal["low", "medium", "high"] = "medium"
    llm_reasoning_effort_fast: Literal["low", "medium", "high"] = "low"
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_max_completion_tokens: int = Field(default=4096, ge=64)
    llm_request_timeout_s: float = Field(default=90, ge=5)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_structured_outputs: bool = True
    # When False (production default) a missing API key or a failed model call is
    # reported as an error. When True, agents fall back to heuristics instead.
    llm_allow_degraded: bool = False
    llm_pricing: dict[str, dict[str, float]] = Field(default_factory=lambda: dict(DEFAULT_LLM_PRICING))
    llm_rate_limits: dict[str, dict[str, int]] = Field(
        default_factory=lambda: dict(DEFAULT_LLM_RATE_LIMITS)
    )
    llm_default_rpm: int = Field(default=30, ge=0)
    llm_default_tpm: int = Field(default=8000, ge=0)
    llm_rate_limit_max_wait_s: float = Field(default=90, ge=0)

    # ── Caching ────────────────────────────────────────────────────────
    cache_enabled: bool = True
    cache_namespace: str = "rfp"
    cache_section_ttl_s: int = Field(default=7 * 24 * 3600, ge=0)
    cache_llm_ttl_s: int = Field(default=24 * 3600, ge=0)
    cache_local_max_items: int = Field(default=512, ge=0)

    # ── Agentic runtime ────────────────────────────────────────────────
    agent_budget: int = Field(default=12, ge=1)
    agent_max_replans: int = Field(default=2, ge=0)
    supervisor_trust_endpoint_intent: bool = True
    supervisor_llm_planning: bool = True
    section_concurrency: int = Field(default=3, ge=1, le=16)
    retrieval_top_k: int = Field(default=4, ge=1, le=20)
    validation_similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    scoring_llm_rubric: bool = True

    # ── Derived helpers ────────────────────────────────────────────────
    @property
    def api_key_list(self) -> list[str]:
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def profile_dir(self) -> Path:
        path = Path(self.domain_profile_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def llm_routes(self) -> dict[str, str]:
        return {**DEFAULT_LLM_ROUTES, **self.llm_route_overrides}

    def groq_key(self) -> str | None:
        return self.groq_api_key.get_secret_value() if self.groq_api_key else None


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["DEFAULT_LLM_ROUTES", "PROJECT_ROOT", "Settings", "get_settings"]
