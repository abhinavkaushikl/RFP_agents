from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(orchestrator):
    from app.api.deps import get_orchestration_service
    from app.bootstrap import create_app
    from app.services.orchestration_service import OrchestrationService

    app = create_app()
    app.dependency_overrides[get_orchestration_service] = lambda: OrchestrationService(orchestrator)
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_profiles(client):
    body = client.get("/api/profiles").json()
    assert body["default"] == "default"
    assert {p["name"] for p in body["profiles"]} >= {"default", "example_company"}
    detail = client.get("/api/profiles/default").json()
    assert detail["llm"]["frontier_model"] == "openai/gpt-oss-120b"
    assert "executive_summary" in detail["default_sections"]
    assert client.get("/api/profiles/nope").status_code == 404


def test_workflow_run_returns_token_usage(client):
    resp = client.post("/api/workflow-runs", json={
        "request_text": "We need a CRM. Must integrate with Outlook.", "client_name": "Contoso",
        "target_sections": ["executive_summary"],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["token_usage"]["totals"]["total_tokens"] > 0
    assert body["sections"][0]["section_key"] == "executive_summary"
    assert resp.headers["X-Request-ID"]


def test_validation_error_for_empty_request(client):
    assert client.post("/api/workflow-runs", json={"request_text": ""}).status_code == 422


def test_api_key_and_rate_limit(monkeypatch, orchestrator):
    from app.api.deps import get_orchestration_service
    from app.api.security import _api_limiter
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.services.orchestration_service import OrchestrationService

    monkeypatch.setenv("RFP_API_KEYS", "secret-1,secret-2")
    monkeypatch.setenv("RFP_API_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    _api_limiter.cache_clear()
    app = create_app()
    app.dependency_overrides[get_orchestration_service] = lambda: OrchestrationService(orchestrator)
    c = TestClient(app)
    body = {"request_text": "Need a portal. Must support SSO.", "target_sections": ["executive_summary"]}
    assert c.post("/api/workflow-runs", json=body).status_code == 401
    assert c.post("/api/workflow-runs", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/api/workflow-runs", json=body, headers={"X-API-Key": "secret-2"}).status_code == 200
    limited = c.post("/api/workflow-runs", json=body, headers={"X-API-Key": "secret-2"})
    assert limited.status_code == 429 and limited.headers["Retry-After"]
    assert limited.json()["error"]["code"] == "rate_limited"
    assert c.get("/api/health").status_code == 200  # health is never gated
    _api_limiter.cache_clear()


def test_missing_groq_key_returns_503(monkeypatch):
    from fakes import FakeRetrievalService

    from app.api.deps import get_orchestration_service
    from app.bootstrap import create_app
    from app.llm.service import LLMService
    from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
    from app.services.orchestration_service import OrchestrationService

    app = create_app()
    app.dependency_overrides[get_orchestration_service] = lambda: OrchestrationService(
        ProposalWorkflowOrchestrator(FakeRetrievalService(), LLMService())
    )
    resp = TestClient(app).post("/api/workflow-runs", json={"request_text": "Need a CRM."})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "llm_not_configured"


def test_extract_text_endpoint(client):
    resp = client.post(
        "/api/documents/extract-text",
        files={"file": ("rfp.md", b"# Scope\nBuild a portal for 500 users with SSO and audit logging.\n", "text/markdown")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["characters"] > 20
