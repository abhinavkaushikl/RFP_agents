from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _parse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.split("\n\n"):
        lines = [line for line in block.splitlines() if line and not line.startswith(":")]
        if not lines:
            continue
        kind = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads("".join(line[6:] for line in lines if line.startswith("data: ")))
        events.append((kind, data))
    return events


@pytest.fixture
def client(orchestrator):
    from app.api.routers.streams import get_orchestrator_factory
    from app.bootstrap import create_app

    app = create_app()
    app.dependency_overrides[get_orchestrator_factory] = lambda: (lambda db: orchestrator)
    return TestClient(app)


def test_proposal_stream_emits_live_progress_then_result(client):
    resp = client.post("/api/workflow-runs/stream", json={
        "request_text": "We need a CRM. Must integrate with Outlook. Must support SSO.",
        "client_name": "Contoso", "target_sections": ["executive_summary", "pricing_notes"],
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse(resp.text)
    kinds = [k for k, _ in events]
    assert kinds[-1] == "result"
    assert kinds.index("sections_planned") < kinds.index("section_started") < kinds.index("section_done")
    done = [d for k, d in events if k == "section_done"]
    assert {d["section_key"] for d in done} == {"executive_summary", "pricing_notes"}
    assert all(d["ok"] and d["tokens"] > 0 and d["preview"] for d in done)
    traces = [d["entry"]["type"] for k, d in events if k == "trace"]
    assert traces[:2] == ["pick_intent", "make_plan"]
    result = events[-1][1]
    assert result["status"] == "completed" and len(result["sections"]) == 2
    assert result["token_usage"]["totals"]["total_tokens"] > 0


def test_stream_reports_errors_as_events(client):
    resp = client.post("/api/workflow-runs/stream", json={"request_text": "x", "profile": "missing_profile"})
    kind, data = _parse(resp.text)[-1]
    assert kind == "error" and data["status"] == 404 and data["code"] == "not_found"


def test_intent_stream(client):
    resp = client.post("/api/intent-detection-runs/stream", json={"transcript_text": "Client: Contoso\nWe need pricing by Q3."})
    kind, data = _parse(resp.text)[-1]
    assert kind == "result" and data["client_overview"]["client_name"]
