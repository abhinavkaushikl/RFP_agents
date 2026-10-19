from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_orchestration_service, get_run_store
from app.api.security import rate_limit_requests, require_api_key
from app.core.errors import NotFoundError
from app.domain.profile import ProfileNotFoundError, load_profile
from app.services.export import export_markdown, export_pdf
from app.schemas.api import (
    DocumentMatchRequest,
    DocumentMatchResponse,
    IntentDetectionRequest,
    IntentDetectionResponse,
    MarketResearchRequest,
    MarketResearchResponse,
    RevisionRequest,
    RevisionResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.orchestration_service import OrchestrationService
from app.services.run_store import RunStore

# Model-backed endpoints are rate limited; read endpoints only need a key.
router = APIRouter(tags=["workflows"], dependencies=[Depends(require_api_key)])
limited = [Depends(rate_limit_requests)]


@router.post("/workflow-runs", response_model=WorkflowRunResponse, dependencies=limited)
def create_workflow_run(
    payload: WorkflowRunRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> dict:
    return service.run_proposal(payload.model_dump())


@router.get("/workflow-runs")
def list_workflow_runs(
    limit: int = Query(20, ge=1, le=100),
    workflow_type: str | None = Query(None, description="e.g. proposal_generation, intent_detection"),
    store: RunStore = Depends(get_run_store),
) -> dict:
    return {"runs": store.list_workflows(limit=limit, workflow_type=workflow_type)}


@router.get("/workflow-runs/{workflow_id}")
def get_workflow_run(workflow_id: str, store: RunStore = Depends(get_run_store)) -> dict:
    run = store.get_workflow(workflow_id)
    if run is None:
        raise NotFoundError(f"Workflow run {workflow_id} not found")
    return run


@router.get("/workflow-runs/{workflow_id}/export")
def export_workflow_run(
    workflow_id: str,
    format: Literal["pdf", "md"] = Query("pdf"),
    store: RunStore = Depends(get_run_store),
) -> Response:
    run = store.get_workflow(workflow_id)
    if run is None:
        raise NotFoundError(f"Workflow run {workflow_id} not found")
    result = run["result"]
    try:
        organization = load_profile(run.get("profile")).organization.name
    except ProfileNotFoundError:
        organization = ""
    title = (result.get("request") or {}).get("title") or "proposal"
    stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "proposal"
    if format == "md":
        return Response(export_markdown(result, organization=organization), media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.md"'})
    return Response(export_pdf(result, organization=organization), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'})


@router.post("/generated-sections/{section_id}/revise", response_model=RevisionResponse, dependencies=limited)
def revise_generated_section(
    section_id: str,
    payload: RevisionRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> dict:
    return service.run_revision(payload.model_dump(), section_id)


@router.get("/generated-sections/{section_id}/revisions")
def get_generated_section_revisions(section_id: str, store: RunStore = Depends(get_run_store)) -> dict:
    return {"section_id": section_id, "revisions": store.list_section_revisions(section_id)}


@router.post("/document-match-runs", response_model=DocumentMatchResponse, dependencies=limited)
def run_document_match(
    payload: DocumentMatchRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> dict:
    return service.run_document_match(payload.model_dump())


@router.post("/intent-detection-runs", response_model=IntentDetectionResponse, dependencies=limited)
def run_intent_detection(
    payload: IntentDetectionRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> dict:
    return service.run_intent_detection(payload.model_dump())


@router.post("/market-research-runs", response_model=MarketResearchResponse, dependencies=limited)
def run_market_research(
    payload: MarketResearchRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> dict:
    return service.run_market_research(payload.model_dump())
