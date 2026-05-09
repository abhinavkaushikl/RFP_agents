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
    ) -> list[dict]:
        return self.tool.search(
            query=query,
            section_type=section_type,
            solution_type=solution_type,
            industry=industry,
            top_k=top_k,
        )
