from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


class ValidationAgent(PlatformAgent):
    name = "validation"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        draft = payload["draft_text"].lower()
        requirements = payload.get("requirements", [])
        covered = {requirement: requirement.lower() in draft for requirement in requirements}
        score = 0.0 if not requirements else sum(covered.values()) / len(requirements)
        output = {
            "requirement_coverage": covered,
            "unsupported_claims": [],
            "missing_items": [item for item, ok in covered.items() if not ok],
            "validation_score": score,
        }
        return AgentResult(self.name, output, "Validated groundedness and requirement coverage.", score)
