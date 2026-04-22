"""Initial multi-agent platform schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_multi_agent_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    actor_type = sa.Enum("system", "user", "agent", "import", name="actortype")
    source_type = sa.Enum("historical", "uploaded", "generated", name="sourcetype")
    workflow_status = sa.Enum("pending", "running", "completed", "failed", name="workflowstatus")
    agent_type = sa.Enum(
        "planner",
        "request_structuring",
        "retrieval",
        "generation",
        "revision",
        "validation",
        "scoring",
        "solution_comparison",
        "orchestrator",
        name="agenttype",
    )

    actor_type.create(op.get_bind(), checkfirst=True)
    source_type.create(op.get_bind(), checkfirst=True)
    workflow_status.create(op.get_bind(), checkfirst=True)
    agent_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "section_types",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_section_types_code", "section_types", ["code"], unique=True)

    op.create_table(
        "solution_types",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_solution_types_code", "solution_types", ["code"], unique=True)

    op.create_table(
        "request_documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255)),
        sa.Column("solution_type_id", sa.UUID(), sa.ForeignKey("solution_types.id")),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "request_document_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("request_document_id", sa.UUID(), sa.ForeignKey("request_documents.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("structured_summary", sa.JSON(), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_type", actor_type, nullable=False),
        sa.Column("created_by_id", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_document_id", "revision_number"),
    )

    op.create_table(
        "proposal_documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("external_id", sa.String(length=255)),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("client_name", sa.String(length=255)),
        sa.Column("industry", sa.String(length=255)),
        sa.Column("solution_type_id", sa.UUID(), sa.ForeignKey("solution_types.id")),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_proposal_documents_external_id", "proposal_documents", ["external_id"])

    op.create_table(
        "proposal_document_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("proposal_document_id", sa.UUID(), sa.ForeignKey("proposal_documents.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_reason", sa.String(length=255)),
        sa.Column("document_json", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text()),
        sa.Column("normalized_text", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_type", actor_type, nullable=False),
        sa.Column("created_by_id", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("proposal_document_id", "revision_number"),
    )

    op.create_table(
        "proposal_sections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("proposal_document_id", sa.UUID(), sa.ForeignKey("proposal_documents.id"), nullable=False),
        sa.Column("section_type_id", sa.UUID(), sa.ForeignKey("section_types.id")),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_proposal_sections_section_key", "proposal_sections", ["section_key"])

    op.create_table(
        "proposal_section_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("proposal_section_id", sa.UUID(), sa.ForeignKey("proposal_sections.id"), nullable=False),
        sa.Column("proposal_document_revision_id", sa.UUID(), sa.ForeignKey("proposal_document_revisions.id")),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=255)),
        sa.Column("created_by_type", actor_type, nullable=False),
        sa.Column("created_by_id", sa.String(length=255)),
        sa.Column("generation_context_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("proposal_section_id", "revision_number"),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("request_document_id", sa.UUID(), sa.ForeignKey("request_documents.id")),
        sa.Column("proposal_document_id", sa.UUID(), sa.ForeignKey("proposal_documents.id")),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"])

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_run_id", sa.UUID(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("agent_type", agent_type, nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_step_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_step_id", sa.UUID(), sa.ForeignKey("workflow_steps.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("input_payload_json", sa.JSON(), nullable=False),
        sa.Column("output_payload_json", sa.JSON(), nullable=False),
        sa.Column("decision_summary", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workflow_step_id", "revision_number"),
    )

    op.create_table(
        "generated_sections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_run_id", sa.UUID(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("section_type_id", sa.UUID(), sa.ForeignKey("section_types.id")),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generated_sections_section_key", "generated_sections", ["section_key"])

    op.create_table(
        "generated_section_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("generated_section_id", sa.UUID(), sa.ForeignKey("generated_sections.id"), nullable=False),
        sa.Column("workflow_step_revision_id", sa.UUID(), sa.ForeignKey("workflow_step_revisions.id")),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("base_revision_id", sa.UUID()),
        sa.Column("revision_instruction", sa.Text()),
        sa.Column("revision_summary", sa.Text()),
        sa.Column("changed_topics_json", sa.JSON(), nullable=False),
        sa.Column("preserved_constraints_json", sa.JSON(), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("generation_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("generated_section_id", "revision_number"),
    )

    op.create_table(
        "embedding_chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("proposal_document_id", sa.UUID(), sa.ForeignKey("proposal_documents.id")),
        sa.Column("proposal_section_revision_id", sa.UUID(), sa.ForeignKey("proposal_section_revisions.id"), nullable=False),
        sa.Column("solution_type_id", sa.UUID(), sa.ForeignKey("solution_types.id")),
        sa.Column("section_type_id", sa.UUID(), sa.ForeignKey("section_types.id")),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_embedding_chunks_content_hash", "embedding_chunks", ["content_hash"])
    op.create_index("ix_embedding_chunks_solution_type_id", "embedding_chunks", ["solution_type_id"])
    op.create_index("ix_embedding_chunks_section_type_id", "embedding_chunks", ["section_type_id"])

    op.create_table(
        "retrieval_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_run_id", sa.UUID(), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("workflow_step_revision_id", sa.UUID(), sa.ForeignKey("workflow_step_revisions.id")),
        sa.Column("target_section", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("retrieval_strategy", sa.String(length=100), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "validation_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "validation_run_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("validation_run_id", sa.UUID(), sa.ForeignKey("validation_runs.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("requirement_coverage_json", sa.JSON(), nullable=False),
        sa.Column("unsupported_claims_json", sa.JSON(), nullable=False),
        sa.Column("missing_items_json", sa.JSON(), nullable=False),
        sa.Column("validation_notes", sa.Text()),
        sa.Column("validation_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("validation_run_id", "revision_number"),
    )

    op.create_table(
        "document_match_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_document_id", sa.UUID(), sa.ForeignKey("proposal_documents.id"), nullable=False),
        sa.Column("target_request_document_id", sa.UUID(), sa.ForeignKey("request_documents.id"), nullable=False),
        sa.Column("latest_revision_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "document_match_run_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_match_run_id", sa.UUID(), sa.ForeignKey("document_match_runs.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("requirement_coverage_score", sa.Float(), nullable=False),
        sa.Column("historical_similarity_score", sa.Float(), nullable=False),
        sa.Column("solution_fit_score", sa.Float(), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("matched_evidence_json", sa.JSON(), nullable=False),
        sa.Column("scoring_explanation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_match_run_id", "revision_number"),
    )


def downgrade() -> None:
    for table_name in [
        "document_match_run_revisions",
        "document_match_runs",
        "validation_run_revisions",
        "validation_runs",
        "retrieval_events",
        "embedding_chunks",
        "generated_section_revisions",
        "generated_sections",
        "workflow_step_revisions",
        "workflow_steps",
        "workflow_runs",
        "proposal_section_revisions",
        "proposal_sections",
        "proposal_document_revisions",
        "proposal_documents",
        "request_document_revisions",
        "request_documents",
        "solution_types",
        "section_types",
    ]:
        op.drop_table(table_name)

    sa.Enum(name="agenttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="workflowstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sourcetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="actortype").drop(op.get_bind(), checkfirst=True)
