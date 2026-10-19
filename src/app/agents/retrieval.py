from __future__ import annotations

from dataclasses import asdict

from app.agents.base import PlatformAgent
from app.domain.profile import load_profile
from app.schemas.domain import AgentContext, AgentResult, RetrievalCandidate
from app.services.retrieval_service import RetrievalService


class RetrievalAgent(PlatformAgent):
    """Semantic search over historical proposal chunks, relaxing filters when results are thin."""

    name = "retrieval"

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        query = (payload.get("query") or "").strip()
        if not query:
            return AgentResult(self.name, {"results": [], "query": "", "filters": {}}, "No query; skipped.", 0.0)
        section_type = payload.get("section_type")
        found = self.retrieval_service.search_relaxed(
            query=query,
            section_codes=profile.section_codes(section_type) if section_type else None,
            solution_type=payload.get("solution_type"),
            industries=profile.industry_match_values(payload.get("industry")),
            top_k=int(payload.get("top_k") or 4),
        )
        results = [
            asdict(
                RetrievalCandidate(
                    chunk_id=item["id"],
                    score=item["score"],
                    section_key=item.get("section_key", "unknown"),
                    proposal_id=item.get("proposal_id", ""),
                    content=item.get("content", ""),
                    metadata={k: item.get(k) for k in ("industry", "solution_type", "chunk_index")},
                )
            )
            for item in found["results"]
        ]
        output = {"results": results, "query": query, "filters": found["filters_applied"]}
        return AgentResult(
            self.name,
            output,
            f"Retrieved {len(results)} chunks (filters: {', '.join(found['filters_applied']) or 'none'}).",
            0.75,
        )
