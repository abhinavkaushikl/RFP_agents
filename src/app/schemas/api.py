from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CachePolicy = Literal["use", "refresh", "off"]

_PROFILE = Field(default=None, description="Domain profile name (configs/domain_profiles/<name>.yaml); defaults to RFP_DEFAULT_PROFILE")
_CACHE = Field(default="use", description="use: reuse cached model outputs; refresh: regenerate and overwrite; off: no cache")


class HistoricalProposalIngestRequest(BaseModel):
    records: list[dict[str, Any]]
    source_name: str = "api"
    profile: str | None = _PROFILE


class IngestionJobResponse(BaseModel):
    accepted: bool
    ingested_count: int
    section_count: int
    chunk_count: int
    source_name: str
    profile: str | None = None
    skipped_duplicates: int = 0
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowRunRequest(BaseModel):
    request_text: str = Field(min_length=1)
    title: str = "Proposal request"
    client_name: str | None = None
    industry: str | None = None
    solution_type: str | None = None
    user_instruction: str | None = None
    target_sections: list[str] | None = None
    profile: str | None = _PROFILE
    cache_policy: CachePolicy = _CACHE
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionRequest(BaseModel):
    instruction: str = Field(min_length=1)
    section_key: str | None = None
    base_text: str | None = None
    requirements: list[str] = Field(default_factory=list)
    profile: str | None = _PROFILE
    cache_policy: CachePolicy = _CACHE
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    section_type: str | None = None
    solution_type: str | None = None
    industry: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    profile: str | None = _PROFILE


class DocumentMatchRequest(BaseModel):
    request_text: str = Field(min_length=1)
    document_text: str = Field(min_length=1)
    solution_type: str | None = None
    industry: str | None = None
    profile: str | None = _PROFILE
    cache_policy: CachePolicy = _CACHE
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketResearchRequest(BaseModel):
    offerings: list[str] = Field(min_length=1)
    requirement_summary: str = ""
    industry: str | None = None
    max_companies: int = Field(default=8, ge=1, le=25)
    profile: str | None = _PROFILE
    cache_policy: CachePolicy = _CACHE


class IntentDetectionRequest(BaseModel):
    transcript_text: str = Field(min_length=1)
    file_name: str | None = None
    profile: str | None = _PROFILE
    cache_policy: CachePolicy = _CACHE


class _RunResponse(BaseModel):
    workflow_id: str
    status: str
    intent: str | None = None
    profile: str | None = None
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    persisted: bool | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowRunResponse(_RunResponse):
    sections: list[dict[str, Any]]
    step_summaries: list[str] = Field(default_factory=list)
    scores: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    solution_comparison: dict[str, Any] = Field(default_factory=dict)


class RevisionResponse(_RunResponse):
    section_id: str
    revision: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)


class DocumentMatchResponse(_RunResponse):
    scores: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    solution_comparison: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    step_summaries: list[str] = Field(default_factory=list)


class MarketResearchResponse(_RunResponse):
    rows: list[dict[str, Any]]
    offerings: list[str]
    industry: str | None = None


class IntentDetectionResponse(_RunResponse):
    client_overview: dict[str, Any] = Field(default_factory=dict)
    buyer_readiness: dict[str, Any] = Field(default_factory=dict)
    product_fit: dict[str, Any] = Field(default_factory=dict)


class ExtractTextResponse(BaseModel):
    file_name: str
    characters: int
    text: str
    sections: list[str] = Field(default_factory=list)
