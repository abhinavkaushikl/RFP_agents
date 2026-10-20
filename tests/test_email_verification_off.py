from __future__ import annotations

from fastapi.testclient import TestClient

CREDS = {"email": "Ada@Example.com", "password": "correct horse", "name": "Ada"}




def _app(monkeypatch, sent_codes):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.api.deps import get_db
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.db.models import EmailOtp, User

    monkeypatch.setenv("RFP_AUTH_REQUIRED", "true")
    monkeypatch.setenv("RFP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("RFP_EMAIL_VERIFICATION_REQUIRED", "false")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    User.__table__.create(engine)
    EmailOtp.__table__.create(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_no_code_is_needed_and_none_is_sent(monkeypatch, sent_codes):
    client = _app(monkeypatch, sent_codes)
    resp = client.post("/api/auth/signup", json=CREDS)
    assert resp.status_code == 200 and resp.json()["user"]["email"] == "ada@example.com"
    assert "httponly" in resp.headers["set-cookie"].lower()
    assert client.get("/api/profiles").status_code == 200
    assert sent_codes == []


def test_existing_addresses_cannot_be_signed_up_again_and_unconfirmed_ones_can_sign_in(monkeypatch, sent_codes):
    client = _app(monkeypatch, sent_codes)
    client.post("/api/auth/signup", json=CREDS)
    other = TestClient(client.app)
    assert other.post("/api/auth/signup", json=CREDS).status_code == 409
    assert other.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}).status_code == 200
