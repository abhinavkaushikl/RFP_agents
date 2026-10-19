from __future__ import annotations

import sys
from pathlib import Path

import fakeredis
import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from app.core.config import get_settings  # noqa: E402
from app.core.redis import set_redis_client  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Every test gets fresh settings, no real Groq key, and an in-memory Redis."""
    monkeypatch.setenv("RFP_GROQ_API_KEY", "")
    monkeypatch.setenv("RFP_CACHE_NAMESPACE", "test")
    monkeypatch.setenv("RFP_LLM_RATE_LIMIT_MAX_WAIT_S", "2")
    monkeypatch.setenv("RFP_API_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("RFP_LLM_ALLOW_DEGRADED", "false")
    get_settings.cache_clear()
    fake = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client(fake)
    yield fake
    set_redis_client(None)
    get_settings.cache_clear()


@pytest.fixture
def fake_client():
    from fakes import FakeGroqClient

    return FakeGroqClient()


@pytest.fixture
def llm(fake_client):
    from app.llm.service import LLMService

    return LLMService(client=fake_client)


@pytest.fixture
def orchestrator(llm):
    from fakes import FakeEmbeddingService, FakeRetrievalService

    from app.agents.registry import build_agent_registry
    from app.orchestration.orchestrator import ProposalWorkflowOrchestrator

    retrieval = FakeRetrievalService()
    agents = build_agent_registry(retrieval, llm, embedding_service=FakeEmbeddingService())
    return ProposalWorkflowOrchestrator(retrieval_service=retrieval, llm_service=llm, agent_registry=agents)
