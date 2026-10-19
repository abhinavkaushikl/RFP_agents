from __future__ import annotations

import pytest

from app.core.errors import InvalidRequestError, NotFoundError
from app.llm.errors import LLMConfigurationError

RFP = (
    "Northwind Foods is issuing an RFP for a warehouse management system.\n"
    "Requirements:\n"
    "- Integrate with SAP ERP\n"
    "- Barcode scanning on handheld devices\n"
    "- Train 200 warehouse staff\n"
    "Go-live within 6 months."
)


def _payload(**extra):
    return {"request_text": RFP, "title": "WMS RFP", "client_name": "Northwind Foods",
            "target_sections": ["executive_summary", "implementation_plan", "pricing_notes"], **extra}


def test_proposal_workflow_end_to_end(orchestrator, fake_client):
    result = orchestrator.run_proposal_workflow(_payload())
    assert result["status"] == "completed"
    assert [s["section_key"] for s in result["sections"]] == ["executive_summary", "implementation_plan", "pricing_notes"]
    assert all(s["draft_text"] and s["generation_mode"] == "llm" for s in result["sections"])
    assert result["request"]["requirements"][0] == "Integrate with SAP ERP"
    assert result["request"]["industry"] == "Transportation & Logistics"  # "logistics" canonicalized by the profile
    assert result["solution_comparison"]["catalog_configured"] is False

    scores = result["scores"]
    assert 0 < scores["composite_score"] <= 1
    assert scores["requirement_coverage_score"] == 1.0  # every requirement is in the drafted text
    assert scores["quality_score"] == 0.75
    assert scores["historical_similarity_score"] is not None

    usage = result["token_usage"]
    agents = {row["agent"] for row in usage["by_agent"]}
    assert {"supervisor", "request_structuring", "solution_comparison", "generation", "scoring"} <= agents
    assert {row["section_key"] for row in usage["by_section"]} == {"executive_summary", "implementation_plan", "pricing_notes"}
    assert {row["model"] for row in usage["by_model"]} == {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}
    assert usage["totals"]["cost_usd"] > 0
    tool_calls = [t for t in result["agent_trace"] if t["type"] == "tool_call"]
    assert all("usage" in t for t in tool_calls)
    gen = next(t for t in tool_calls if t["tool"] == "generate_proposal_sections")
    assert gen["usage"]["model_calls"] == 3
    assert result["agent_trace"][0] == {"type": "pick_intent", "intent": "proposal_generation",
                                        "hint": "proposal_generation", "how": "endpoint"}


def test_second_identical_run_is_served_from_cache(orchestrator, fake_client):
    orchestrator.run_proposal_workflow(_payload())
    calls_after_first = len(fake_client.calls)
    second = orchestrator.run_proposal_workflow(_payload())
    assert len(fake_client.calls) == calls_after_first  # nothing new sent to the model
    assert all(s["cache_hit"] for s in second["sections"])
    totals = second["token_usage"]["totals"]
    assert totals["model_calls"] == 0 and totals["cache_hits"] > 0 and totals["saved_tokens"] > 0


def test_cache_refresh_regenerates(orchestrator, fake_client):
    orchestrator.run_proposal_workflow(_payload())
    before = len(fake_client.calls)
    result = orchestrator.run_proposal_workflow(_payload(cache_policy="refresh"))
    assert len(fake_client.calls) > before
    assert not any(s["cache_hit"] for s in result["sections"])


def test_requires_groq_key_unless_degraded(monkeypatch):
    from fakes import FakeRetrievalService

    from app.core.config import get_settings
    from app.llm.service import LLMService
    from app.orchestration.orchestrator import ProposalWorkflowOrchestrator

    orch = ProposalWorkflowOrchestrator(FakeRetrievalService(), LLMService())
    with pytest.raises(LLMConfigurationError):
        orch.run_proposal_workflow(_payload())

    monkeypatch.setenv("RFP_LLM_ALLOW_DEGRADED", "true")
    get_settings.cache_clear()
    from fakes import FakeEmbeddingService

    from app.agents.registry import build_agent_registry

    llm = LLMService()
    orch = ProposalWorkflowOrchestrator(
        FakeRetrievalService(), llm,
        agent_registry=build_agent_registry(FakeRetrievalService(), llm, embedding_service=FakeEmbeddingService()),
    )
    result = orch.run_proposal_workflow(_payload())
    assert result["sections"] and all(s["generation_mode"] == "fallback" for s in result["sections"])
    assert any(w.startswith("Degraded mode") for w in result["warnings"])
    assert result["request"]["extraction_mode"] == "heuristic"
    assert "Integrate with SAP ERP" in result["request"]["requirements"]


def test_unknown_profile_is_404(orchestrator):
    with pytest.raises(NotFoundError):
        orchestrator.run_proposal_workflow(_payload(profile="does_not_exist"))


def test_empty_request_rejected(orchestrator):
    with pytest.raises(InvalidRequestError):
        orchestrator.run_proposal_workflow({"request_text": "  "})


def test_profile_with_catalog_matches_offerings(orchestrator):
    result = orchestrator.run_proposal_workflow(_payload(profile="example_company"))
    comparison = result["solution_comparison"]
    assert comparison["catalog_configured"] is True
    assert comparison["matching_offerings"] == ["Digital Platform Delivery"]
    assert "Barcode scanning on handheld devices" in comparison["gaps"]
    assert comparison["solution_fit_score"] == pytest.approx(1 / 3, abs=0.01)


def test_revision_uses_base_text_and_evidence(orchestrator, fake_client):
    result = orchestrator.run_revision_workflow(
        {"instruction": "Mention ISO 27001", "base_text": "Original section.", "section_key": "compliance",
         "requirements": ["ISO 27001 controls"]},
        "section-123",
    )
    assert result["status"] == "completed"
    assert "ISO 27001" in result["revision"]["draft_text"]
    assert result["revision"]["section_key"] == "compliance_response"
    assert result["validation"]["validation_score"] == 1.0
    revise_prompt = next(c for c in fake_client.calls
                         if (c["response_format"] or {}).get("json_schema", {}).get("name") == "revision")
    assert "Phased rollout with SAP integration" in revise_prompt["messages"][-1]["content"]  # retrieved precedent is used


def test_revision_without_text_is_404(orchestrator):
    with pytest.raises(NotFoundError):
        orchestrator.run_revision_workflow({"instruction": "x"}, "missing")


def test_document_match_returns_scores(orchestrator):
    result = orchestrator.run_document_match_workflow(
        {"request_text": RFP, "document_text": "We integrate with SAP ERP and provide barcode scanning on handheld devices."}
    )
    assert result["scores"]["requirement_coverage_score"] == pytest.approx(2 / 3, abs=0.01)
    assert result["scores"]["composite_score"] > 0


def test_intent_detection_uses_fast_and_frontier_models(orchestrator, fake_client):
    transcript = open("dummy_transcript.txt", encoding="utf-8").read()
    result = orchestrator.run_intent_detection_workflow({"transcript_text": transcript})
    assert result["client_overview"]["client_name"] == "Meridian Healthcare Systems"
    assert result["client_overview"]["problem_statement"]
    assert result["buyer_readiness"]["readiness_stage"] == "High Intent"
    assert result["product_fit"]["fit_stage"] == "Strong Fit"
    models = {row["agent"]: row for row in result["token_usage"]["by_agent"]}
    by_call = {c["agent"]: c["model"] for c in result["token_usage"]["calls"]}
    assert by_call["intent_detection"] == "openai/gpt-oss-20b"
    assert by_call["problem_framing"] == "openai/gpt-oss-20b"
    assert by_call["buyer_intelligence"] == "openai/gpt-oss-120b"
    assert "product_fit" in models
    # all four analyses send the same system + transcript prefix
    prefixes = {c["messages"][1]["content"].split("TASK:")[0] for c in fake_client.calls if "TRANSCRIPT:" in c["messages"][-1]["content"]}
    assert len(prefixes) == 1
