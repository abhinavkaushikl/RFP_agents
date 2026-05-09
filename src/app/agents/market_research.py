from __future__ import annotations

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.services.market_research_service import MarketResearchService


class MarketResearchAgent(PlatformAgent):
    name = "market_research"

    def __init__(self, service: MarketResearchService) -> None:
        self.service = service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        offerings = [o.strip() for o in payload.get("offerings", []) if o and o.strip()]
        requirement_summary = (payload.get("requirement_summary") or "").strip()
        industry = (payload.get("industry") or "").strip() or None
        max_companies = int(payload.get("max_companies", 8))

        hits = self.service.research(
            offerings=offerings,
            requirement_summary=requirement_summary,
            industry=industry,
            max_companies=max_companies,
        )
        rows = [hit.to_row() for hit in hits]
        return AgentResult(
            self.name,
            {
                "rows": rows,
                "offerings": offerings,
                "requirement_summary": requirement_summary,
                "industry": industry,
            },
            f"Researched {len(rows)} companies for {len(offerings)} offerings.",
            0.7,
        )
