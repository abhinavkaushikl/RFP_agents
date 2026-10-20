from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.ingestion import router as ingestion_router
from app.api.routers.profiles import router as profiles_router
from app.api.routers.retrieval import router as retrieval_router
from app.api.routers.streams import router as streams_router
from app.api.routers.usage import router as usage_router
from app.api.routers.workflows import router as workflows_router
from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import NotFoundError, register_error_handlers
from app.core.logging import configure_logging, get_logger, request_id_var

logger = get_logger(__name__)

WEB_DIST = PROJECT_ROOT / "web" / "dist"


def _mount_web_app(app: FastAPI, api_prefix: str) -> None:
    """Serve the built web app (web/dist) with client-side routing fallback, when it exists."""
    index = WEB_DIST / "index.html"
    if not index.is_file():
        return
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def web_app(full_path: str) -> FileResponse:
        if full_path.startswith(api_prefix.strip("/") + "/") or full_path == api_prefix.strip("/"):
            raise NotFoundError(f"No API route /{full_path}")
        candidate = (WEB_DIST / full_path).resolve()
        if full_path and candidate.is_file() and WEB_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app = FastAPI(title=settings.app_name, version="0.2.0")

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "Retry-After"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s in %dms", request.method, request.url.path, response.status_code,
            int((time.perf_counter() - started) * 1000),
        )
        return response

    register_error_handlers(app)
    for router in (auth_router, health_router, profiles_router, ingestion_router, retrieval_router, streams_router,
                   workflows_router, usage_router):
        app.include_router(router, prefix=settings.api_prefix)
    _mount_web_app(app, settings.api_prefix)

    logger.info(
        "Started %s (%s) frontier=%s fast=%s groq_configured=%s profile=%s",
        settings.app_name, settings.environment, settings.llm_frontier_model, settings.llm_fast_model,
        bool(settings.groq_key()), settings.default_profile,
    )
    return app
