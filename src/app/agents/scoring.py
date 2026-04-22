from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


class ScoringAgent(PlatformAgent):
    name = "scoring"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        requirements = payload.get("requirements", [])
        candidate_text = payload["document_text"].lower()
        requirement_hits = sum(1 for item in requirements if item.lower() in candidate_text)
        coverage = 0.0 if not requirements else requirement_hits / len(requirements)
        retrieval_hint = min(1.0, payload.get("retrieval_score_hint", 0.5))
        output = {
            "requirement_coverage_score": coverage,
            "historical_similarity_score": retrieval_hint,
            "solution_fit_score": 0.85 if payload.get("solution_type") else 0.5,
            "completeness_score": 0.75,
            "composite_score": round((coverage + retrieval_hint + 0.75) / 3, 3),
            "matched_evidence": payload.get("matched_evidence", []),
        }
        return AgentResult(self.name, output, "Scored document against request and evidence.", 0.76)
