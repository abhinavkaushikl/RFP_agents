from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_ingestion_service
from app.api.security import rate_limit_requests, require_api_key
from app.core.errors import InvalidRequestError, NotFoundError
from app.db.models import ProposalDocumentRevision
from app.domain.profile import ProfileNotFoundError, load_profile
from app.ingestion.documents import UnsupportedDocumentError, document_to_record, extract_text, split_into_sections
from app.schemas.api import ExtractTextResponse, HistoricalProposalIngestRequest, IngestionJobResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["ingestion"], dependencies=[Depends(require_api_key), Depends(rate_limit_requests)])


def _profile(name: str | None):
    try:
        return load_profile(name)
    except ProfileNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc


@router.post("/historical-proposals/ingest", response_model=IngestionJobResponse)
def ingest_historical_proposals(
    payload: HistoricalProposalIngestRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    _profile(payload.profile)
    if not payload.records:
        raise InvalidRequestError("records is empty")
    result = service.ingest_historical(payload.records, payload.source_name, payload.profile)
    return {"accepted": True, **result}


@router.post("/historical-proposals/upload", response_model=IngestionJobResponse)
async def upload_historical_proposals(
    files: list[UploadFile] = File(..., description="PDF, DOCX, Markdown, or text proposals"),
    source_name: str = Form("upload"),
    profile: str | None = Form(None),
    client_name: str | None = Form(None),
    industry: str | None = Form(None),
    solution_type: str | None = Form(None),
    service: IngestionService = Depends(get_ingestion_service),
) -> dict:
    prof = _profile(profile)
    records, file_report = [], []
    for upload in files:
        data = await upload.read()
        try:
            record = document_to_record(
                upload.filename or "document.txt", data, prof,
                client_name=client_name, industry=industry, solution_type=solution_type,
            )
        except UnsupportedDocumentError as exc:
            file_report.append({"file_name": upload.filename, "ok": False, "error": str(exc)})
            continue
        records.append(record)
        file_report.append({"file_name": upload.filename, "ok": True, "sections": sorted(record["proposal_sections"])})
    if not records:
        raise InvalidRequestError("None of the uploaded files contained readable text: " + "; ".join(
            f"{f['file_name']}: {f.get('error')}" for f in file_report))
    result = service.ingest_historical(records, source_name, prof.name)
    return {"accepted": True, **result, "files": file_report}


@router.post("/documents/extract-text", response_model=ExtractTextResponse)
async def extract_document_text(file: UploadFile = File(...), profile: str | None = Form(None)) -> dict:
    """Return the text of an uploaded RFP, proposal, or transcript (used by the UI upload boxes)."""
    data = await file.read()
    try:
        text = extract_text(file.filename or "document.txt", data)
    except UnsupportedDocumentError as exc:
        raise InvalidRequestError(str(exc)) from exc
    sections = sorted(split_into_sections(text, _profile(profile)))
    return {"file_name": file.filename or "", "characters": len(text), "text": text, "sections": sections}


@router.get("/proposal-documents/{document_id}/revisions")
def get_proposal_document_revisions(document_id: str, db: Session = Depends(get_db)) -> dict:
    import uuid

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as exc:
        raise NotFoundError(f"Proposal document {document_id} not found") from exc
    rows = db.execute(
        select(ProposalDocumentRevision)
        .where(ProposalDocumentRevision.proposal_document_id == doc_uuid)
        .order_by(ProposalDocumentRevision.revision_number)
    ).scalars()
    return {
        "document_id": document_id,
        "revisions": [
            {
                "revision_id": str(r.id),
                "revision_number": r.revision_number,
                "reason": r.revision_reason,
                "metadata": r.metadata_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
