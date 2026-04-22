from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult, RetrievalCandidate
from app.tools.retrieval_tool import RetrievalTool


class RetrievalAgent(PlatformAgent):
    name = "retrieval"

    def __init__(self) -> None:
        self.tool = RetrievalTool()

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        results_raw = self.tool.invoke(payload)
        results = [
            RetrievalCandidate(
                chunk_id=item["id"],
                score=item["score"],
                section_key=item.get("section_key", "unknown"),
                proposal_id=item.get("proposal_id", ""),
                content=item.get("content", ""),
                metadata=item,
            ).__dict__
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
