"""LLM usage events and persisted workflow results.

- llm_usage_events: one row per model call or cache hit (tokens, cached tokens, cost, latency)
- workflow_runs: profile, payload_json, result_json, completed_at
- removes the junk `source_dataset` section created by the old telecom importer
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_llm_usage_and_run_results"
down_revision = "0001_multi_agent_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workflow_id", sa.UUID()),
        sa.Column("workflow_type", sa.String(length=100)),
        sa.Column("agent", sa.String(length=100), nullable=False),
        sa.Column("tool", sa.String(length=100)),
        sa.Column("section_key", sa.String(length=100)),
        sa.Column("purpose", sa.String(length=100)),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="groq"),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=20)),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("saved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("saved_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_events_workflow_id", "llm_usage_events", ["workflow_id"])
    op.create_index("ix_llm_usage_events_workflow_type", "llm_usage_events", ["workflow_type"])
    op.create_index("ix_llm_usage_events_agent", "llm_usage_events", ["agent"])
    op.create_index("ix_llm_usage_events_model", "llm_usage_events", ["model"])
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])

    op.add_column("workflow_runs", sa.Column("profile", sa.String(length=64)))
    op.add_column("workflow_runs", sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("workflow_runs", sa.Column("result_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("workflow_runs", sa.Column("completed_at", sa.DateTime(timezone=True)))

    # The old importer stored the dataset file name as a "source_dataset" section and embedded it.
    op.execute(
        """
        DELETE FROM embedding_chunks
        WHERE section_type_id IN (SELECT id FROM section_types WHERE code = 'source_dataset')
        """
    )


def downgrade() -> None:
    op.drop_column("workflow_runs", "completed_at")
    op.drop_column("workflow_runs", "result_json")
    op.drop_column("workflow_runs", "payload_json")
    op.drop_column("workflow_runs", "profile")
    op.drop_index("ix_llm_usage_events_created_at", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_model", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_agent", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_workflow_type", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_workflow_id", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
