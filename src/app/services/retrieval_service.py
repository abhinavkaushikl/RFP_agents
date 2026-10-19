from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.embedding_service import EmbeddingService
from app.tools.retrieval_tool import RetrievalTool


class RetrievalService:
    def __init__(self, db: Session, embedding_service: EmbeddingService) -> None:
        self.tool = RetrievalTool(db=db, embedding_service=embedding_service)

    def search(
        self,
        query: str,
        section_type: str | None = None,
        solution_type: str | None = None,
        industry: str | None = None,
        top_k: int = 5,
        *,
        section_codes: list[str] | None = None,
        industries: list[str] | None = None,
    ) -> list[dict]:
        codes = section_codes or ([section_type] if section_type else None)
        inds = industries or ([industry.lower()] if industry else None)
        return self.tool.search(
            query=query,
            section_codes=codes,
            solution_type=solution_type,
            industries=inds,
            top_k=top_k,
        )

    def search_relaxed(
        self,
        query: str,
        *,
        section_codes: list[str] | None = None,
        solution_type: str | None = None,
        industries: list[str] | None = None,
        top_k: int = 4,
    ) -> dict:
        """Search with all filters, then drop the most specific ones until enough results come back.

        Solution-type labels are often free-form, so an exact solution filter is dropped first,
        then industry, then section.
        """
        attempts = [
            {"section_codes": section_codes, "solution_type": solution_type, "industries": industries},
            {"section_codes": section_codes, "solution_type": None, "industries": industries},
            {"section_codes": section_codes, "solution_type": None, "industries": None},
            {"section_codes": None, "solution_type": None, "industries": None},
        ]
        seen: set[tuple] = set()
        results: list[dict] = []
        applied: dict = attempts[-1]
        for filters in attempts:
            signature = tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in filters.items())
            if signature in seen:
                continue
            seen.add(signature)
            results = self.tool.search(query=query, top_k=top_k, **filters)
            applied = filters
            if len(results) >= max(1, (top_k + 1) // 2):
                break
        names = [name for name, value in (("section", applied["section_codes"]),
                                          ("solution_type", applied["solution_type"]),
                                          ("industry", applied["industries"])) if value]
        return {"results": results, "filters_applied": names}
