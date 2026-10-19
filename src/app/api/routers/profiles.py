from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.security import require_api_key
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.domain.profile import ProfileNotFoundError, list_profiles, load_profile
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/profiles", tags=["profiles"], dependencies=[Depends(require_api_key)])


@router.get("")
def get_profiles() -> dict:
    return {"default": get_settings().default_profile, "profiles": list_profiles()}


@router.get("/{name}")
def get_profile(name: str) -> dict:
    """Profile contents the UI needs (industries, sections, offerings, categories) plus model routing."""
    try:
        profile = load_profile(name)
    except ProfileNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    llm = get_llm_service().describe()
    return {**profile.public_view(), "llm": {k: v for k, v in llm.items() if k != "organization_id"}}
