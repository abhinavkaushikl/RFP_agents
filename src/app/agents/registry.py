from __future__ import annotations

from app.agents.buyer_intelligence import BuyerIntelligenceAgent
from app.agents.generation import GenerationAgent
from app.agents.intent_detection import IntentDetectionAgent
from app.agents.market_research import MarketResearchAgent
from app.agents.planner import PlannerAgent
from app.agents.problem_framing import ProblemFramingAgent
from app.agents.product_fit import ProductFitAgent
from app.agents.request_structuring import RequestStructuringAgent
from app.agents.retrieval import RetrievalAgent
from app.agents.revision import RevisionAgent
from app.agents.scoring import ScoringAgent
from app.agents.solution_comparison import SolutionComparisonAgent
from app.agents.validation import ValidationAgent
from app.services.llm_service import LLMService
from app.services.market_research_service import MarketResearchService
from app.services.retrieval_service import RetrievalService


def build_agent_registry(
    retrieval_service: RetrievalService,
    llm_service: LLMService,
    market_research_service: MarketResearchService | None = None,
) -> dict[str, object]:
    return {
        "request_structuring": RequestStructuringAgent(),
        "planner": PlannerAgent(),
        "retrieval": RetrievalAgent(retrieval_service),
        "solution_comparison": SolutionComparisonAgent(),
        "generation": GenerationAgent(llm_service),
        "revision": RevisionAgent(llm_service),
        "validation": ValidationAgent(),
        "scoring": ScoringAgent(),
        "market_research": MarketResearchAgent(
            market_research_service or MarketResearchService(llm_service=llm_service)
        ),
        "intent_detection": IntentDetectionAgent(),
        "problem_framing": ProblemFramingAgent(llm_service),
        "buyer_intelligence": BuyerIntelligenceAgent(llm_service),
        "product_fit": ProductFitAgent(llm_service),
    }
