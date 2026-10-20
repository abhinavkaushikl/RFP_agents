"""A signed-in member only ever sees their own runs; admins and API-key scripts see everything."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access import AccessScope

SECTION = {"section_key": "executive_summary", "title": "Executive Summary", "draft_text": "Secret plan", "citations": []}


@pytest.fixture
def world(monkeypatch):
    from app.api.deps import get_db
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.db import models as m

    monkeypatch.setenv("RFP_AUTH_REQUIRED", "true")
    monkeypatch.setenv("RFP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("RFP_ADMIN_EMAILS", "boss@example.com")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for table in (m.User, m.WorkflowRun, m.GeneratedSection, m.GeneratedSectionRevision, m.LLMUsageEvent, m.SectionType):
        table.__table__.create(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override
    return app, Session


def _client(app):
    return TestClient(app)


def _signup(app, email):
    c = _client(app)
    r = c.post("/api/auth/signup", json={"email": email, "password": "correct horse", "name": email})
    assert r.status_code == 200, r.text
    return c, uuid.UUID(r.json()["user"]["id"])


def _seed_run(Session, owner_id):
    """Store one proposal run (with a section and token usage) as `owner_id` would have."""
    from app.services.run_store import RunStore

    db = Session()
    store = RunStore(db, AccessScope(owner_id=owner_id, restricted=True))
    wid = str(uuid.uuid4())
    ids = store.save_workflow(
        workflow_id=wid, workflow_type="proposal_generation", status="completed", profile="default",
        payload={"client_name": "Acme"}, result={"request": {"title": "Acme deal"}, "sections": [dict(SECTION)]},
        sections=[dict(SECTION)],
        usage_records=[{"agent": "generation", "model": "m", "section_key": "executive_summary", "total_tokens": 100}],
    )
    db.close()
    return wid, ids["executive_summary"]["section_id"]


def test_members_cannot_see_each_others_runs(world):
    app, Session = world
    alice, alice_id = _signup(app, "alice@example.com")
    bob, _ = _signup(app, "bob@example.com")
    wid, section_id = _seed_run(Session, alice_id)

    assert [r["workflow_id"] for r in alice.get("/api/workflow-runs").json()["runs"]] == [wid]
    assert alice.get(f"/api/workflow-runs/{wid}").status_code == 200

    # Bob gets "not found" for everything of Alice's, so he can't even tell the run exists.
    assert bob.get("/api/workflow-runs").json()["runs"] == []
    assert bob.get(f"/api/workflow-runs/{wid}").status_code == 404
    assert bob.get(f"/api/workflow-runs/{wid}/export?format=md").status_code == 404
    assert bob.get(f"/api/generated-sections/{section_id}/revisions").json()["revisions"] == []
    assert bob.get(f"/api/usage/workflows/{wid}").status_code == 404
    assert bob.get("/api/usage/summary?days=7").json()["totals"]["total_tokens"] == 0
    assert bob.get("/api/usage/runs?days=7").json()["runs"] == []
    assert alice.get("/api/usage/runs?days=7").json()["runs"][0]["workflow_id"] == wid


def test_admin_sees_everyones_runs(world):
    app, Session = world
    _, alice_id = _signup(app, "alice@example.com")
    boss, _ = _signup(app, "boss@example.com")
    wid, _ = _seed_run(Session, alice_id)

    assert [r["workflow_id"] for r in boss.get("/api/workflow-runs").json()["runs"]] == [wid]
    assert boss.get(f"/api/workflow-runs/{wid}").status_code == 200


def test_api_key_scripts_are_not_restricted(world, monkeypatch):
    from app.core.config import get_settings

    app, Session = world
    _, alice_id = _signup(app, "alice@example.com")
    wid, _ = _seed_run(Session, alice_id)
    monkeypatch.setenv("RFP_API_KEYS", "script-key")
    get_settings.cache_clear()

    r = _client(app).get("/api/workflow-runs", headers={"X-API-Key": "script-key"})
    assert [x["workflow_id"] for x in r.json()["runs"]] == [wid]


def test_runs_made_before_accounts_existed_are_hidden_from_members(world):
    from app.db.models import WorkflowRun, WorkflowStatus

    app, Session = world
    alice, _ = _signup(app, "alice@example.com")
    db = Session()
    db.add(WorkflowRun(id=uuid.uuid4(), workflow_type="proposal_generation", status=WorkflowStatus.completed,
                       payload_json={}, result_json={}))
    db.commit()
    db.close()
    assert alice.get("/api/workflow-runs").json()["runs"] == []


def test_new_runs_record_their_owner(world):
    from app.db.models import LLMUsageEvent, WorkflowRun

    app, Session = world
    _, alice_id = _signup(app, "alice@example.com")
    _seed_run(Session, alice_id)
    db = Session()
    assert db.query(WorkflowRun).one().owner_id == alice_id
    assert db.query(LLMUsageEvent).one().owner_id == alice_id
    db.close()
