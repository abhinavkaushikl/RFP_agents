from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_retrieval_service
from app.api.security import rate_limit_requests, require_api_key
from app.core.errors import NotFoundError
from app.domain.profile import ProfileNotFoundError, load_profile
from app.schemas.api import RetrievalSearchRequest
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"], dependencies=[Depends(require_api_key), Depends(rate_limit_requests)])


@router.post("/search")
def retrieval_search(
    payload: RetrievalSearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> dict:
    try:
        profile = load_profile(payload.profile)
    except ProfileNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    results = retrieval_service.search(
        query=payload.query,
        solution_type=payload.solution_type,
        top_k=payload.top_k,
        section_codes=profile.section_codes(payload.section_type) if payload.section_type else None,
        industries=profile.industry_match_values(payload.industry),
    )
    return {"results": results}
