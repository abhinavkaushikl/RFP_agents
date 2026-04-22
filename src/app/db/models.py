from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WorkflowStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SourceType(str, enum.Enum):
    historical = "historical"
    uploaded = "uploaded"
    generated = "generated"


class ActorType(str, enum.Enum):
    system = "system"
    user = "user"
    agent = "agent"
    import_job = "import"


class AgentType(str, enum.Enum):
    planner = "planner"
    request_structuring = "request_structuring"
    retrieval = "retrieval"
    generation = "generation"
    revision = "revision"
    validation = "validation"
    scoring = "scoring"
    solution_comparison = "solution_comparison"
    orchestrator = "orchestrator"


class SectionType(Base):
    __tablename__ = "section_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = now_column()


class SolutionType(Base):
    __tablename__ = "solution_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = now_column()


class RequestDocument(Base):
    __tablename__ = "request_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    solution_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("solution_types.id"))
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    revisions: Mapped[list["RequestDocumentRevision"]] = relationship(back_populates="request_document")


class RequestDocumentRevision(Base):
    __tablename__ = "request_document_revisions"
    __table_args__ = (UniqueConstraint("request_document_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    request_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("request_documents.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    request_text: Mapped[str] = mapped_column(Text)
    structured_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    requirements_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_type: Mapped[ActorType] = mapped_column(Enum(ActorType))
    created_by_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = now_column()

    request_document: Mapped["RequestDocument"] = relationship(back_populates="revisions")


class ProposalDocument(Base):
    __tablename__ = "proposal_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    client_name: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    solution_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("solution_types.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(100), default="active")
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    revisions: Mapped[list["ProposalDocumentRevision"]] = relationship(back_populates="proposal_document")
    sections: Mapped[list["ProposalSection"]] = relationship(back_populates="proposal_document")


class ProposalDocumentRevision(Base):
    __tablename__ = "proposal_document_revisions"
    __table_args__ = (UniqueConstraint("proposal_document_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    proposal_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_documents.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    revision_reason: Mapped[str | None] = mapped_column(String(255))
    document_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_type: Mapped[ActorType] = mapped_column(Enum(ActorType))
    created_by_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = now_column()

    proposal_document: Mapped["ProposalDocument"] = relationship(back_populates="revisions")


class ProposalSection(Base):
    __tablename__ = "proposal_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposal_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_documents.id"), index=True)
    section_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("section_types.id"))
    section_key: Mapped[str] = mapped_column(String(100), index=True)
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    proposal_document: Mapped["ProposalDocument"] = relationship(back_populates="sections")
    revisions: Mapped[list["ProposalSectionRevision"]] = relationship(back_populates="proposal_section")


class ProposalSectionRevision(Base):
    __tablename__ = "proposal_section_revisions"
    __table_args__ = (UniqueConstraint("proposal_section_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    proposal_section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_sections.id"), index=True)
    proposal_document_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proposal_document_revisions.id")
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    content_text: Mapped[str] = mapped_column(Text)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    change_summary: Mapped[str | None] = mapped_column(String(255))
    created_by_type: Mapped[ActorType] = mapped_column(Enum(ActorType))
    created_by_id: Mapped[str | None] = mapped_column(String(255))
    generation_context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = now_column()

    proposal_section: Mapped["ProposalSection"] = relationship(back_populates="revisions")


class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposal_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposal_documents.id"), index=True)
    proposal_section_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposal_section_revisions.id"), index=True
    )
    solution_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("solution_types.id"), index=True)
    section_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("section_types.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dimensions))
    created_at: Mapped[datetime] = now_column()


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.pending)
    request_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("request_documents.id"))
    proposal_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposal_documents.id"))
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    steps: Mapped[list["WorkflowStep"]] = relationship(back_populates="workflow_run")


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType))
    step_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.pending)
    sequence_number: Mapped[int] = mapped_column(Integer)
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="steps")
    revisions: Mapped[list["WorkflowStepRevision"]] = relationship(back_populates="workflow_step")


class WorkflowStepRevision(Base):
    __tablename__ = "workflow_step_revisions"
    __table_args__ = (UniqueConstraint("workflow_step_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_steps.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    input_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = now_column()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workflow_step: Mapped["WorkflowStep"] = relationship(back_populates="revisions")


class GeneratedSection(Base):
    __tablename__ = "generated_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    section_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("section_types.id"))
    section_key: Mapped[str] = mapped_column(String(100), index=True)
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    revisions: Mapped[list["GeneratedSectionRevision"]] = relationship(back_populates="generated_section")


class GeneratedSectionRevision(Base):
    __tablename__ = "generated_section_revisions"
    __table_args__ = (UniqueConstraint("generated_section_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    generated_section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_sections.id"), index=True)
    workflow_step_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_step_revisions.id"))
    revision_number: Mapped[int] = mapped_column(Integer)
    base_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revision_instruction: Mapped[str | None] = mapped_column(Text)
    revision_summary: Mapped[str | None] = mapped_column(Text)
    changed_topics_json: Mapped[list] = mapped_column(JSON, default=list)
    preserved_constraints_json: Mapped[list] = mapped_column(JSON, default=list)
    draft_text: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    prompt_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = now_column()

    generated_section: Mapped["GeneratedSection"] = relationship(back_populates="revisions")


class RetrievalEvent(Base):
    __tablename__ = "retrieval_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    workflow_step_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_step_revisions.id"))
    target_section: Mapped[str] = mapped_column(String(100))
    query_text: Mapped[str] = mapped_column(Text)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieval_strategy: Mapped[str] = mapped_column(String(100))
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    results_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = now_column()


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    revisions: Mapped[list["ValidationRunRevision"]] = relationship(back_populates="validation_run")


class ValidationRunRevision(Base):
    __tablename__ = "validation_run_revisions"
    __table_args__ = (UniqueConstraint("validation_run_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    validation_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("validation_runs.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    requirement_coverage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    unsupported_claims_json: Mapped[list] = mapped_column(JSON, default=list)
    missing_items_json: Mapped[list] = mapped_column(JSON, default=list)
    validation_notes: Mapped[str | None] = mapped_column(Text)
    validation_score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = now_column()

    validation_run: Mapped["ValidationRun"] = relationship(back_populates="revisions")


class DocumentMatchRun(Base):
    __tablename__ = "document_match_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_documents.id"))
    target_request_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("request_documents.id"))
    latest_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = now_column()

    revisions: Mapped[list["DocumentMatchRunRevision"]] = relationship(back_populates="document_match_run")


class DocumentMatchRunRevision(Base):
    __tablename__ = "document_match_run_revisions"
    __table_args__ = (UniqueConstraint("document_match_run_id", "revision_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    document_match_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_match_runs.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    requirement_coverage_score: Mapped[float] = mapped_column(default=0.0)
    historical_similarity_score: Mapped[float] = mapped_column(default=0.0)
    solution_fit_score: Mapped[float] = mapped_column(default=0.0)
    completeness_score: Mapped[float] = mapped_column(default=0.0)
    composite_score: Mapped[float] = mapped_column(default=0.0)
    matched_evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    scoring_explanation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = now_column()

    document_match_run: Mapped["DocumentMatchRun"] = relationship(back_populates="revisions")
