from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.redis import redis_status
from app.db.session import engine
from app.domain.profile import load_profile
from app.services.llm_service import get_llm_service

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    """Readiness: database, Redis, LLM configuration, and the default profile."""
    settings = get_settings()
    checks: dict[str, dict] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["database"] = {"ok": True, "migration": version}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"ok": False, "error": str(exc).splitlines()[0]}
    redis = redis_status()
    checks["redis"] = {**redis, "required": settings.redis_required}
    llm = get_llm_service().describe()
    checks["llm"] = {
        "ok": llm["configured"] or llm["degraded_mode_allowed"],
        "configured": llm["configured"],
        "provider": llm["provider"],
        "organization_id": llm["organization_id"],
        "frontier_model": llm["frontier_model"],
        "fast_model": llm["fast_model"],
    }
    try:
        profile = load_profile()
        checks["profile"] = {"ok": True, "name": profile.name, "version": profile.version}
    except Exception as exc:  # noqa: BLE001
        checks["profile"] = {"ok": False, "error": str(exc)}

    ready = (
        checks["database"]["ok"]
        and checks["llm"]["ok"]
        and checks["profile"]["ok"]
        and (redis["ok"] or not settings.redis_required)
    )
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready", "checks": checks})
