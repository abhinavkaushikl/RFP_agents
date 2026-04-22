from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_chunk_store, get_ingestion_service
from app.schemas.api import HistoricalProposalIngestRequest, IngestionJobResponse

router = APIRouter(prefix="/historical-proposals", tags=["ingestion"])


@router.post("/ingest", response_model=IngestionJobResponse)
def ingest_historical_proposals(
    payload: HistoricalProposalIngestRequest,
    ingestion_service=Depends(get_ingestion_service),
    chunk_store: list[dict] = Depends(get_chunk_store),
) -> IngestionJobResponse:
    result = ingestion_service.ingest_historical(payload.records, payload.source_name)
    chunk_store.extend(result["chunks"])
    return IngestionJobResponse(
        accepted=True,
        ingested_count=result["ingested_count"],
        section_count=result["section_count"],
        chunk_count=result["chunk_count"],
        source_name=result["source_name"],
    )


@router.get("/jobs/{job_id}")
def get_ingestion_job(job_id: str) -> dict:
    return {"job_id": job_id, "status": "completed", "note": "Async ingestion job hook is ready for Celery/RQ."}
