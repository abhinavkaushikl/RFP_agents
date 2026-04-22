from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class RetrievalToolInput(BaseModel):
    query: str
    section_type: str | None = None
    solution_type: str | None = None
    industry: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_chunks: list[dict[str, Any]] = Field(default_factory=list)


class RetrievalTool(BaseTool):
    name: str = "retrieval_tool"
    description: str = "Retrieve the most relevant proposal chunks for a given request and section."
    args_schema: type[BaseModel] = RetrievalToolInput

    def _run(
        self,
        query: str,
        section_type: str | None = None,
        solution_type: str | None = None,
        industry: str | None = None,
        top_k: int = 5,
        candidate_chunks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        candidate_chunks = candidate_chunks or []
        query_terms = {term for term in query.lower().split() if term}
        ranked: list[dict[str, Any]] = []
        for chunk in candidate_chunks:
            content = chunk.get("content", "").lower()
            score = sum(1 for term in query_terms if term in content)
            if section_type and chunk.get("section_key") == section_type:
                score += 3
            if solution_type and chunk.get("solution_type") == solution_type:
                score += 3
            if industry and chunk.get("industry") == industry:
                score += 1
            ranked.append({**chunk, "score": float(score)})
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]
