"""Each person's library of existing solutions."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_scope
from app.api.security import require_api_key
from app.core.access import AccessScope
from app.services.solution_store import SolutionStore

router = APIRouter(prefix="/solutions", tags=["solutions"], dependencies=[Depends(require_api_key)])


def get_solution_store(db: Session = Depends(get_db), scope: AccessScope = Depends(get_scope)) -> SolutionStore:
    return SolutionStore(db, scope)


def _clean_capabilities(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        text = " ".join(value.split())
        if text:
            seen.setdefault(text[:100], None)
    return list(seen)[:30]


class SolutionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    status: Literal["active", "planned", "retired"] = "active"
    description: str = Field(default="", max_length=4000)
    capabilities: list[str] = Field(default_factory=list, max_length=60)
    url: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Give the solution a name.")
        return value

    @field_validator("category")
    @classmethod
    def _category(cls, value: str | None) -> str | None:
        return " ".join(value.split()) or None if value else None

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("The link must start with http:// or https://")
        return value

    def fields(self) -> dict:
        data = self.model_dump()
        data["capabilities"] = _clean_capabilities(data["capabilities"])
        return data


@router.get("")
def list_solutions(
    q: str | None = Query(None, max_length=100),
    everyone: bool = Query(False, description="Admins only: include other people's solutions"),
    store: SolutionStore = Depends(get_solution_store),
) -> dict:
    return {"solutions": store.list(query=q, everyone=everyone)}


@router.post("", status_code=201)
def create_solution(body: SolutionIn, store: SolutionStore = Depends(get_solution_store)) -> dict:
    return store.create(body.fields())


@router.get("/{solution_id}")
def get_solution(solution_id: str, store: SolutionStore = Depends(get_solution_store)) -> dict:
    return store.get(solution_id)


@router.put("/{solution_id}")
def update_solution(solution_id: str, body: SolutionIn, store: SolutionStore = Depends(get_solution_store)) -> dict:
    return store.update(solution_id, body.fields())


@router.delete("/{solution_id}", status_code=204)
def delete_solution(solution_id: str, store: SolutionStore = Depends(get_solution_store)) -> Response:
    store.delete(solution_id)
    return Response(status_code=204)
