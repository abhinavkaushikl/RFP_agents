"""Existing solutions: private per account, role-based visibility."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SOLUTION = {
    "name": "Acme CRM",
    "category": "Sales software",
    "status": "active",
    "description": "A CRM we built for field sales teams.",
    "capabilities": ["Pipeline tracking", "Outlook sync", "pipeline tracking"],
    "url": "https://acme.example.com",
}


@pytest.fixture
def world(monkeypatch, sent_codes):
    from app.api.deps import get_db
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.db import models as m

    monkeypatch.setenv("RFP_AUTH_REQUIRED", "true")
    monkeypatch.setenv("RFP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("RFP_EMAIL_VERIFICATION_REQUIRED", "false")
    monkeypatch.setenv("RFP_ADMIN_EMAILS", "boss@example.com")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for table in (m.User, m.EmailOtp, m.ExistingSolution):
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
    app.state.Session = Session
    return app


def _user(app, email):
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"email": email, "password": "correct horse", "name": email})
    assert r.status_code == 200, r.text
    return c


def test_create_list_get_update_delete_your_own(world):
    alice = _user(world, "alice@example.com")
    created = alice.post("/api/solutions", json=SOLUTION)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Acme CRM" and body["mine"] is True
    assert body["capabilities"] == ["Pipeline tracking", "Outlook sync", "pipeline tracking"]  # kept as typed, trimmed
    sid = body["id"]

    assert [s["id"] for s in alice.get("/api/solutions").json()["solutions"]] == [sid]
    assert alice.get(f"/api/solutions/{sid}").json()["name"] == "Acme CRM"

    updated = alice.put(f"/api/solutions/{sid}", json={**SOLUTION, "name": "Acme CRM Pro", "status": "retired"})
    assert updated.status_code == 200 and updated.json()["name"] == "Acme CRM Pro" and updated.json()["status"] == "retired"

    assert alice.delete(f"/api/solutions/{sid}").status_code == 204
    assert alice.get("/api/solutions").json()["solutions"] == []
    assert alice.get(f"/api/solutions/{sid}").status_code == 404


def test_members_cannot_see_edit_or_delete_each_others_solutions(world):
    alice, bob = _user(world, "alice@example.com"), _user(world, "bob@example.com")
    sid = alice.post("/api/solutions", json=SOLUTION).json()["id"]

    assert bob.get("/api/solutions").json()["solutions"] == []
    assert bob.get("/api/solutions?everyone=true").json()["solutions"] == []  # members can't ask for everyone's
    assert bob.get(f"/api/solutions/{sid}").status_code == 404
    assert bob.put(f"/api/solutions/{sid}", json=SOLUTION).status_code == 404
    assert bob.delete(f"/api/solutions/{sid}").status_code == 404
    assert alice.get(f"/api/solutions/{sid}").status_code == 200  # still there


def test_two_people_can_use_the_same_name_but_not_one_person_twice(world):
    alice, bob = _user(world, "alice@example.com"), _user(world, "bob@example.com")
    assert alice.post("/api/solutions", json=SOLUTION).status_code == 201
    assert bob.post("/api/solutions", json=SOLUTION).status_code == 201
    assert alice.post("/api/solutions", json=SOLUTION).status_code == 409


def test_admin_sees_everyones_and_can_delete_but_not_edit_others(world):
    alice, boss = _user(world, "alice@example.com"), _user(world, "boss@example.com")
    sid = alice.post("/api/solutions", json=SOLUTION).json()["id"]
    boss.post("/api/solutions", json={**SOLUTION, "name": "Boss tool"})

    mine_only = boss.get("/api/solutions").json()["solutions"]
    assert [s["name"] for s in mine_only] == ["Boss tool"]
    everyone = boss.get("/api/solutions?everyone=true").json()["solutions"]
    assert {s["name"] for s in everyone} == {"Acme CRM", "Boss tool"}
    assert {s["name"]: s["owner_email"] for s in everyone}["Acme CRM"] == "alice@example.com"
    assert boss.get(f"/api/solutions/{sid}").status_code == 200

    assert boss.put(f"/api/solutions/{sid}", json={**SOLUTION, "name": "Hijacked"}).status_code == 403
    assert alice.get(f"/api/solutions/{sid}").json()["name"] == "Acme CRM"
    assert boss.delete(f"/api/solutions/{sid}").status_code == 204
    assert alice.get("/api/solutions").json()["solutions"] == []


def test_the_role_column_makes_an_admin_and_members_never_see_owner_emails(world):
    from app.db.models import User

    alice, carol = _user(world, "alice@example.com"), _user(world, "carol@example.com")
    alice.post("/api/solutions", json=SOLUTION)
    assert "owner_email" not in alice.get("/api/solutions").json()["solutions"][0]
    assert alice.get("/api/auth/me").json()["user"]["role"] == "member"

    db = world.state.Session()
    db.query(User).filter(User.email == "carol@example.com").update({"role": "admin"})
    db.commit()
    db.close()
    assert carol.get("/api/auth/me").json()["user"]["role"] == "admin"
    assert [s["name"] for s in carol.get("/api/solutions?everyone=true").json()["solutions"]] == ["Acme CRM"]


def test_search_and_validation(world):
    alice = _user(world, "alice@example.com")
    alice.post("/api/solutions", json=SOLUTION)
    alice.post("/api/solutions", json={**SOLUTION, "name": "Billing engine", "category": "Finance", "description": "Invoices"})
    assert [s["name"] for s in alice.get("/api/solutions?q=billing").json()["solutions"]] == ["Billing engine"]
    assert [s["name"] for s in alice.get("/api/solutions?q=finance").json()["solutions"]] == ["Billing engine"]

    assert alice.post("/api/solutions", json={**SOLUTION, "name": "   "}).status_code == 422
    assert alice.post("/api/solutions", json={**SOLUTION, "name": "X", "url": "javascript:alert(1)"}).status_code == 422
    assert alice.post("/api/solutions", json={**SOLUTION, "name": "Y", "status": "weird"}).status_code == 422
    assert alice.get("/api/solutions/not-a-uuid").status_code == 404


def test_signed_out_requests_are_refused(world):
    assert TestClient(world).get("/api/solutions").status_code == 401
