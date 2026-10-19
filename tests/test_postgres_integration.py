"""Integration tests against a real Postgres + pgvector database.

Run against a disposable, migrated database:

    createdb rfp_test
    RFP_DATABASE_URL=postgresql+psycopg://localhost:5432/rfp_test alembic upgrade head
    RFP_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/rfp_test pytest -m postgres
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

DB_URL = os.getenv("RFP_TEST_DATABASE_URL")
pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not DB_URL, reason="RFP_TEST_DATABASE_URL not set")]
SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples" / "rfp_records.sample.jsonl"


@pytest.fixture(scope="module")
def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DB_URL, future=True)
    db = sessionmaker(bind=engine, future=True)()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture(scope="module")
def embeddings():
    from app.services.embedding_service import EmbeddingService

    return EmbeddingService()


def _records() -> list[dict]:
    return [json.loads(line) for line in SAMPLES.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ingest_search_and_idempotency(session, embeddings):
    from app.domain.profile import load_profile
    from app.services.ingestion_service import IngestionService
    from app.services.retrieval_service import RetrievalService

    source = f"it-{uuid.uuid4().hex[:6]}"
    service = IngestionService(session, embeddings)
    first = service.ingest_historical(_records(), source)
    assert first["ingested_count"] == 3 and first["chunk_count"] > 3
    again = service.ingest_historical(_records(), source)
    assert again["ingested_count"] == 0 and again["skipped_duplicates"] == 3

    profile = load_profile()
    retrieval = RetrievalService(session, embeddings)
    hits = retrieval.search(
        "phased rollout with accessibility testing and staff training",
        section_codes=profile.section_codes("implementation_plan"),
        industries=profile.industry_match_values("public sector"),
        top_k=3,
    )
    assert hits and hits[0]["industry"] == "Government & Public Sector"
    assert all(h["section_key"] == "implementation_plan" for h in hits)
    relaxed = retrieval.search_relaxed("data quality scorecard", solution_type="does_not_exist",
                                       section_codes=profile.section_codes("risk_management"), top_k=2)
    assert relaxed["results"] and "solution_type" not in relaxed["filters_applied"]


def test_run_store_round_trip(session):
    from app.llm.types import UsageRecord
    from app.services.run_store import RunStore

    store = RunStore(session)
    workflow_id = str(uuid.uuid4())
    usage = [
        UsageRecord(agent="generation", model="openai/gpt-oss-120b", tier="frontier", section_key="executive_summary",
                    prompt_tokens=1200, cached_prompt_tokens=600, completion_tokens=400, total_tokens=1600, cost_usd=0.0004),
        UsageRecord(agent="generation", model="openai/gpt-oss-120b", tier="frontier", section_key="pricing_notes",
                    cache_hit=True, saved_tokens=1500, saved_cost_usd=0.0003),
    ]
    ids = store.save_workflow(
        workflow_id=workflow_id, workflow_type="proposal_generation", status="completed", profile="default",
        payload={"request_text": "x"}, result={"status": "completed"},
        sections=[{"section_key": "executive_summary", "draft_text": "Draft one.", "citations": ["c1"]},
                  {"section_key": "pricing_notes", "draft_text": "", "error": "boom"}],
        usage_records=[u.to_dict() for u in usage],
    )
    assert list(ids) == ["executive_summary"]
    section_id = ids["executive_summary"]["section_id"]
    loaded = store.load_section(section_id)
    assert loaded["draft_text"] == "Draft one." and loaded["revision_number"] == 1

    saved = store.save_section_revision(section_id=section_id, instruction="Shorter",
                                        revision={"draft_text": "Draft two.", "revision_summary": "Shortened"},
                                        validation={"validation_score": 0.5})
    assert saved["revision_number"] == 2
    assert store.load_section(section_id)["draft_text"] == "Draft two."
    revisions = store.list_section_revisions(section_id)
    assert [r["revision_number"] for r in revisions] == [1, 2] and revisions[1]["instruction"] == "Shorter"

    report = store.usage_for_workflow(workflow_id)
    assert report["totals"]["total_tokens"] == 1600 and report["totals"]["cache_hits"] == 1
    assert report["totals"]["prompt_cache_rate"] == 0.5
    summary = store.usage_summary(days=1)
    assert summary["workflows"] >= 1 and summary["by_day"]
    assert store.get_workflow(workflow_id)["status"] == "completed"
