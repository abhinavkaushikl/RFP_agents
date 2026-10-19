from __future__ import annotations

import pytest

from app.agents.schema import STR, obj
from app.llm.errors import LLMConfigurationError, LLMRateLimitError
from app.llm.service import LLMService
from app.llm.usage import cache_policy, usage_run, usage_tags


def test_routes_agents_to_tiers(llm):
    assert llm.route("supervisor") == ("fast", "openai/gpt-oss-20b")
    assert llm.route("intent_detection") == ("fast", "openai/gpt-oss-20b")
    assert llm.route("generation") == ("frontier", "openai/gpt-oss-120b")
    assert llm.route("unknown_agent") == ("frontier", "openai/gpt-oss-120b")


def test_route_overrides_from_env(monkeypatch, fake_client):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_LLM_ROUTE_OVERRIDES", '{"generation": "fast"}')
    get_settings.cache_clear()
    assert LLMService(client=fake_client).route("generation")[0] == "fast"


def test_strict_schema_and_reasoning_params(llm, fake_client):
    llm.complete_json(agent="generation", system="s", prompt="p", schema=obj(a=STR), schema_name="x")
    call = fake_client.calls[-1]
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["reasoning_effort"] == "medium"
    llm.complete(agent="supervisor", prompt="hello")
    assert fake_client.calls[-1]["reasoning_effort"] == "low"
    assert fake_client.calls[-1]["model"] == "openai/gpt-oss-20b"


def test_usage_records_tokens_cost_and_tags(llm):
    with usage_run("wf-1") as run:
        with usage_tags(tool="generate_proposal_sections", section_key="executive_summary"):
            llm.complete(agent="generation", system="rules", prompt="write it")
    rec = run.records[0]
    assert rec.workflow_id == "wf-1"
    assert rec.section_key == "executive_summary" and rec.tool == "generate_proposal_sections"
    assert rec.prompt_tokens > 0 and rec.completion_tokens > 0
    assert rec.cost_usd > 0
    report = run.report()
    assert report["totals"]["model_calls"] == 1
    assert report["by_section"][0]["section_key"] == "executive_summary"
    assert report["by_agent"][0]["agent"] == "generation"


def test_response_cache_avoids_second_call(llm, fake_client):
    with usage_run("wf") as run:
        first = llm.complete(agent="generation", system="rules", prompt="same", cache_kind="section")
        second = llm.complete(agent="generation", system="rules", prompt="same", cache_kind="section")
    assert len(fake_client.calls) == 1
    assert not first.cache_hit and second.cache_hit and second.text == first.text
    totals = run.report()["totals"]
    assert totals["cache_hits"] == 1 and totals["saved_tokens"] == first.usage.total_tokens


def test_cache_policy_refresh_and_off(llm, fake_client):
    llm.complete(agent="generation", prompt="x")
    with cache_policy("refresh"):
        llm.complete(agent="generation", prompt="x")
    with cache_policy("off"):
        llm.complete(agent="generation", prompt="x")
    assert len(fake_client.calls) == 3
    llm.complete(agent="generation", prompt="x")  # refreshed entry is reused
    assert len(fake_client.calls) == 3


def test_provider_prompt_cache_tokens_are_reported(llm):
    with usage_run("wf") as run:
        llm.complete(agent="generation", system="static rules " * 50, prompt="context A", cache=False)
        llm.complete(agent="generation", system="static rules " * 50, prompt="context A", cache=False)
    second = run.records[1]
    assert second.cached_prompt_tokens > 0
    assert run.report()["totals"]["prompt_cache_rate"] > 0


def test_schema_rejection_falls_back_to_json_object(fake_client):
    fake_client.schema_error_once = True
    service = LLMService(client=fake_client)
    result = service.complete_json(agent="scoring", system="s", prompt="p", schema=obj(a=STR), schema_name="rubric")
    assert isinstance(result.parsed, dict)
    assert fake_client.calls[-1]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in fake_client.calls[-1]["messages"][-1]["content"]


def test_missing_key_is_a_configuration_error():
    service = LLMService()
    assert not service.configured
    with pytest.raises(LLMConfigurationError):
        service.ensure_configured()


def test_provider_rate_limit_pauses_model(fake_client):
    fake_client.fail_with = LLMRateLimitError("429", retry_after=30)
    service = LLMService(client=fake_client)
    with usage_run("wf") as run, pytest.raises(LLMRateLimitError):
        service.complete(agent="generation", prompt="x", cache=False)
    assert run.records[-1].status == "rate_limited"
    fake_client.fail_with = None
    # The model is now paused for 30s, longer than the 2s max wait configured for tests.
    with pytest.raises(LLMRateLimitError):
        service.complete(agent="generation", prompt="y", cache=False)
