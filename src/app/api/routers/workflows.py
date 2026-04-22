from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_chunk_store, get_orchestration_service
from app.schemas.api import DocumentMatchRequest, RevisionRequest, WorkflowRunRequest, WorkflowRunResponse

router = APIRouter(tags=["workflows"])


@router.post("/workflow-runs", response_model=WorkflowRunResponse)
def create_workflow_run(
    payload: WorkflowRunRequest,
    orchestration_service=Depends(get_orchestration_service),
    chunk_store: list[dict] = Depends(get_chunk_store),
) -> WorkflowRunResponse:
    result = orchestration_service.run_proposal(payload.model_dump(), chunk_store)
    return WorkflowRunResponse(
        workflow_id=result["workflow_id"],
        status=result["status"],
        sections=result["sections"],
        step_summaries=result["step_summaries"],
    )


@router.post("/generated-sections/{section_id}/revise")
def revise_generated_section(
    section_id: str,
    payload: RevisionRequest,
    orchestration_service=Depends(get_orchestration_service),
    chunk_store: list[dict] = Depends(get_chunk_store),
) -> dict:
    base_section = {
        "section_id": section_id,
        "section_key": payload.section_key or "implementation_plan",
        "draft_text": "Current draft emphasizes phased deployment and measurable business outcomes.",
    }
    return orchestration_service.run_revision(payload.model_dump(), base_section, chunk_store)


@router.post("/document-match-runs")
def run_document_match(
    payload: DocumentMatchRequest,
    orchestration_service=Depends(get_orchestration_service),
    chunk_store: list[dict] = Depends(get_chunk_store),
) -> dict:
    return orchestration_service.run_document_match(payload.model_dump(), chunk_store)


@router.get("/proposal-documents/{document_id}/revisions")
def get_proposal_document_revisions(document_id: str) -> dict:
    return {"document_id": document_id, "revisions": []}


@router.get("/generated-sections/{section_id}/revisions")
def get_generated_section_revisions(section_id: str) -> dict:
    return {"section_id": section_id, "revisions": []}
