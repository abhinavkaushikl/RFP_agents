from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_orchestration_service
from app.schemas.api import (
    DocumentMatchRequest,
    IntentDetectionRequest,
    IntentDetectionResponse,
    MarketResearchRequest,
    MarketResearchResponse,
    RevisionRequest,
    WorkflowRunRequest,
    WorkflowRunResponse,
)

router = APIRouter(tags=["workflows"])


@router.post("/workflow-runs", response_model=WorkflowRunResponse)
def create_workflow_run(
    payload: WorkflowRunRequest,
    orchestration_service=Depends(get_orchestration_service),
) -> WorkflowRunResponse:
    result = orchestration_service.run_proposal(payload.model_dump())
    return WorkflowRunResponse(
        workflow_id=result["workflow_id"],
        status=result["status"],
        sections=result["sections"],
        step_summaries=result["step_summaries"],
        scores=result.get("scores", {}),
        request=result.get("request", {}),
        solution_comparison=result.get("solution_comparison", {}),
        agent_trace=result.get("agent_trace", []),
    )


@router.post("/generated-sections/{section_id}/revise")
def revise_generated_section(
    section_id: str,
    payload: RevisionRequest,
    orchestration_service=Depends(get_orchestration_service),
) -> dict:
    base_section = {
        "section_id": section_id,
        "section_key": payload.section_key or "implementation_plan",
        "draft_text": payload.base_text
        or "Current draft emphasizes phased deployment and measurable business outcomes.",
    }
    return orchestration_service.run_revision(payload.model_dump(), base_section)


@router.post("/document-match-runs")
def run_document_match(
    payload: DocumentMatchRequest,
    orchestration_service=Depends(get_orchestration_service),
) -> dict:
    return orchestration_service.run_document_match(payload.model_dump())


@router.post("/intent-detection-runs", response_model=IntentDetectionResponse)
def run_intent_detection(
    payload: IntentDetectionRequest,
    orchestration_service=Depends(get_orchestration_service),
) -> IntentDetectionResponse:
    result = orchestration_service.run_intent_detection(payload.model_dump())
    return IntentDetectionResponse(
        workflow_id=result["workflow_id"],
        status=result["status"],
        client_overview=result.get("client_overview", {}),
        buyer_readiness=result.get("buyer_readiness", {}),
        product_fit=result.get("product_fit", {}),
        summary=result.get("summary", ""),
        agent_trace=result.get("agent_trace", []),
    )


@router.post("/market-research-runs", response_model=MarketResearchResponse)
def run_market_research(
    payload: MarketResearchRequest,
    orchestration_service=Depends(get_orchestration_service),
) -> MarketResearchResponse:
    result = orchestration_service.run_market_research(payload.model_dump())
    return MarketResearchResponse(
        workflow_id=result["workflow_id"],
        status=result["status"],
        rows=result["rows"],
        offerings=result["offerings"],
        industry=result.get("industry"),
        summary=result.get("summary", ""),
        agent_trace=result.get("agent_trace", []),
    )


@router.get("/proposal-documents/{document_id}/revisions")
def get_proposal_document_revisions(document_id: str) -> dict:
    return {"document_id": document_id, "revisions": []}


@router.get("/generated-sections/{section_id}/revisions")
def get_generated_section_revisions(section_id: str) -> dict:
    return {"section_id": section_id, "revisions": []}
