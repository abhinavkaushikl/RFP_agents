from __future__ import annotations

from app.agents.buyer_intelligence import BuyerIntelligenceAgent
from app.agents.generation import GenerationAgent
from app.agents.intent_detection import IntentDetectionAgent
from app.agents.market_research import MarketResearchAgent
from app.agents.problem_framing import ProblemFramingAgent
from app.agents.product_fit import ProductFitAgent
from app.agents.request_structuring import RequestStructuringAgent
from app.agents.retrieval import RetrievalAgent
from app.agents.revision import RevisionAgent
from app.agents.scoring import ScoringAgent
from app.agents.solution_comparison import SolutionComparisonAgent
from app.agents.validation import ValidationAgent
from app.core.config import get_settings
from app.llm.service import LLMService
from app.services.coverage import CoverageAnalyzer
from app.services.market_research_service import MarketResearchService
from app.services.retrieval_service import RetrievalService


def build_agent_registry(
    retrieval_service: RetrievalService,
    llm_service: LLMService,
    market_research_service: MarketResearchService | None = None,
    embedding_service=None,
) -> dict[str, object]:
    coverage = CoverageAnalyzer(
        embedding_service=embedding_service,
        threshold=get_settings().validation_similarity_threshold,
    )
    return {
        "request_structuring": RequestStructuringAgent(llm_service),
        "retrieval": RetrievalAgent(retrieval_service),
        "solution_comparison": SolutionComparisonAgent(llm_service),
        "generation": GenerationAgent(llm_service),
        "revision": RevisionAgent(llm_service),
        "validation": ValidationAgent(coverage),
        "scoring": ScoringAgent(llm_service, coverage),
        "market_research": MarketResearchAgent(
            market_research_service or MarketResearchService(llm_service=llm_service)
        ),
        "intent_detection": IntentDetectionAgent(llm_service),
        "problem_framing": ProblemFramingAgent(llm_service),
        "buyer_intelligence": BuyerIntelligenceAgent(llm_service),
        "product_fit": ProductFitAgent(llm_service),
    }
