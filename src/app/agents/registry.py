from __future__ import annotations

from app.agents.generation import GenerationAgent
from app.agents.planner import PlannerAgent
from app.agents.request_structuring import RequestStructuringAgent
from app.agents.retrieval import RetrievalAgent
from app.agents.revision import RevisionAgent
from app.agents.scoring import ScoringAgent
from app.agents.solution_comparison import SolutionComparisonAgent
from app.agents.validation import ValidationAgent


def build_agent_registry() -> dict[str, object]:
    return {
        "request_structuring": RequestStructuringAgent(),
        "planner": PlannerAgent(),
        "retrieval": RetrievalAgent(),
        "solution_comparison": SolutionComparisonAgent(),
        "generation": GenerationAgent(),
        "revision": RevisionAgent(),
        "validation": ValidationAgent(),
        "scoring": ScoringAgent(),
    }
