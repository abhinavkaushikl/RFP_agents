from __future__ import annotations

from app.llm.service import LLMService
from app.services.market_research_service import MarketResearchService

RESULTS = [
    {"title": "Top 10 AIOps Tools in 2026", "href": "https://blog.example-listicle.com/aiops", "body": "Aisera, BigPanda…"},
    {"title": "AIOps Platform Market Size, Share & Forecast", "href": "https://www.futuremarketinsights.com/x", "body": ""},
    {"title": "Aisera: Agentic AIOps for the enterprise", "href": "https://aisera.com/aiops", "body": "Founded in 2017. From $99/month."},
    {"title": "monday.com AI for IT teams", "href": "https://monday.com/it", "body": "Work OS"},
]


def _service(llm=None) -> MarketResearchService:
    svc = MarketResearchService(llm_service=llm, request_pause_s=0)
    svc._search = lambda query, max_results=None: RESULTS  # type: ignore[method-assign]
    svc._fetch = lambda url: ""  # type: ignore[method-assign]
    return svc


def test_listicles_and_report_publishers_are_not_companies():
    names = [h.name for h in _service().research(["AIOps platform"], max_companies=8)]
    assert "Aisera" in names
    assert not any("Listicle" in n or "Futuremarketinsights" in n for n in names)


def test_model_screens_out_non_vendors_and_describes_the_rest(fake_client):
    hits = _service(LLMService(client=fake_client)).research(["AIOps platform"], max_companies=8)
    assert [h.domain for h in hits] == ["aisera.com"]
    assert hits[0].description.startswith("AIOps and service management")
    row = hits[0].to_row()
    assert row["About"].startswith("AIOps") and row["Price"] == "$99/month"
