from __future__ import annotations

from dataclasses import asdict

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult, RetrievalCandidate
from app.services.retrieval_service import RetrievalService


class RetrievalAgent(PlatformAgent):
    name = "retrieval"

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        results_raw = self.retrieval_service.search(
            query=payload["query"],
            section_type=payload.get("section_type"),
            solution_type=payload.get("solution_type"),
            industry=payload.get("industry"),
            top_k=payload.get("top_k", 5),
        )
        results = [
            asdict(
                RetrievalCandidate(
                    chunk_id=item["id"],
                    score=item["score"],
                    section_key=item.get("section_key", "unknown"),
                    proposal_id=item.get("proposal_id", ""),
                    content=item.get("content", ""),
                    metadata=item,
                )
            )
            for item in results_raw
        ]
        output = {
            "results": results,
            "query": payload["query"],
            "filters": {
                "section_type": payload.get("section_type"),
                "solution_type": payload.get("solution_type"),
                "industry": payload.get("industry"),
            },
        }
        return AgentResult(self.name, output, f"Retrieved {len(results)} evidence chunks.", 0.77)
