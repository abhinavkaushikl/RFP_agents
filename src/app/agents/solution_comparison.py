from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.tools.solution_comparison_tool import SolutionComparisonTool


class SolutionComparisonAgent(PlatformAgent):
    name = "solution_comparison"

    def __init__(self) -> None:
        self.tool = SolutionComparisonTool()

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        output = self.tool.invoke(
            {
                "solution_type": payload.get("solution_type", "aiops_general"),
                "requirements": payload.get("requirements", []),
            }
        )
        output["positioning_notes"] = [f"Emphasize {output['matching_offerings'][0]} in the proposal."]
        return AgentResult(self.name, output, "Compared request against internal offerings.", 0.8)
