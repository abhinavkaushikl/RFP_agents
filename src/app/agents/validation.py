from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.services.coverage import CoverageAnalyzer


class ValidationAgent(PlatformAgent):
    """Checks which requirements a draft addresses (no model call)."""

    name = "validation"

    def __init__(self, coverage: CoverageAnalyzer | None = None) -> None:
        self.coverage = coverage or CoverageAnalyzer()

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        analysis = self.coverage.analyze(payload.get("requirements") or [], payload.get("draft_text") or "")
        score = analysis["coverage_score"]
        output = {
            "requirement_coverage": analysis["requirement_coverage"],
            "coverage_details": analysis["details"],
            "unsupported_claims": [],
            "missing_items": analysis["missing_items"],
            "validation_score": score,
            "method": analysis["method"],
        }
        if score is None:
            summary = "No requirements to validate against."
        else:
            covered = len(analysis["details"]) - len(analysis["missing_items"])
            summary = f"Covers {covered}/{len(analysis['details'])} requirements ({analysis['method']})."
        return AgentResult(self.name, output, summary, score or 0.0)
