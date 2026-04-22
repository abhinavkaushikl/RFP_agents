from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_chunk_store, get_retrieval_service
from app.schemas.api import RetrievalSearchRequest

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search")
def retrieval_search(
    payload: RetrievalSearchRequest,
    retrieval_service=Depends(get_retrieval_service),
    chunk_store: list[dict] = Depends(get_chunk_store),
) -> dict:
    results = retrieval_service.search(
        query=payload.query,
        candidate_chunks=chunk_store,
        section_type=payload.section_type,
        solution_type=payload.solution_type,
        industry=payload.industry,
        top_k=payload.top_k,
    )
    return {"results": results}
