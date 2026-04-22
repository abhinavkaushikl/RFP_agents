from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class SolutionComparisonInput(BaseModel):
    solution_type: str
    requirements: list[str] = Field(default_factory=list)


class SolutionComparisonTool(BaseTool):
    name: str = "solution_comparison_tool"
    description: str = "Compare a structured request against known solution offerings."
    args_schema: type[BaseModel] = SolutionComparisonInput

    def _run(self, solution_type: str, requirements: list[str] | None = None) -> dict[str, Any]:
        requirements = requirements or []
        offerings = {
            "aiops_operations": ["event correlation", "incident automation", "noise reduction"],
            "aiops_observability": ["observability", "topology intelligence", "service health analytics"],
            "aiops_general": ["platform integration", "managed services", "analytics"],
        }
        matches = offerings.get(solution_type, offerings["aiops_general"])
        gaps = [req for req in requirements if not any(match in req.lower() for match in matches)]
        return {
            "solution_type": solution_type,
            "matching_offerings": matches,
            "gaps": gaps,
            "fit_explanation": f"Matched request to {solution_type} offering family.",
        }
