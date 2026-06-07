from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HistoricalProposalIngestRequest(BaseModel):
    records: list[dict[str, Any]]
    source_name: str = "api"


class RequestCreatePayload(BaseModel):
    title: str
    request_text: str
    industry: str | None = None
    solution_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunRequest(BaseModel):
    request_text: str
    title: str = "AIOps Proposal Request"
    industry: str | None = None
    solution_type: str | None = None
    user_instruction: str | None = None
    target_sections: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionRequest(BaseModel):
    instruction: str
    base_revision_id: str | None = None
    section_key: str | None = None
    base_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalSearchRequest(BaseModel):
    query: str
    section_type: str | None = None
    solution_type: str | None = None
    industry: str | None = None
    top_k: int = 5


class DocumentMatchRequest(BaseModel):
    request_text: str
    document_text: str
    solution_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketResearchRequest(BaseModel):
    offerings: list[str]
    requirement_summary: str = ""
    industry: str | None = None
    max_companies: int = 8


class MarketResearchResponse(BaseModel):
    workflow_id: str
    status: str
    rows: list[dict[str, Any]]
    offerings: list[str]
    industry: str | None = None
    summary: str = ""
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class IntentDetectionRequest(BaseModel):
    transcript_text: str
    file_name: str | None = None


class IntentDetectionResponse(BaseModel):
    workflow_id: str
    status: str
    client_overview: dict[str, Any] = Field(default_factory=dict)
    buyer_readiness: dict[str, Any] = Field(default_factory=dict)
    product_fit: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    status: str
    sections: list[dict[str, Any]]
    step_summaries: list[str]
    scores: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    solution_comparison: dict[str, Any] = Field(default_factory=dict)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class IngestionJobResponse(BaseModel):
    accepted: bool
    ingested_count: int
    section_count: int
    chunk_count: int
    source_name: str
