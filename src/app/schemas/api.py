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


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    status: str
    sections: list[dict[str, Any]]
    step_summaries: list[str]


class IngestionJobResponse(BaseModel):
    accepted: bool
    ingested_count: int
    section_count: int
    chunk_count: int
    source_name: str
