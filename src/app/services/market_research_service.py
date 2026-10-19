"""Market research via DuckDuckGo search + light page scraping.

Pipeline per request:

1. **Search** — DDGS().text() with three query classes (combined coverage,
   per-offering, per-result enrichment) to discover candidate companies.
2. **Parse snippets** — cheap regex extraction for $-prices, ratings,
   "founded YYYY" mentions. Catches the easy cases.
3. **Scrape** — for each candidate company, fetch the homepage + /about +
   /pricing pages (short timeout, plain requests + BeautifulSoup) and
   extract clean text (~3 KB total).
4. **Model extraction** — if structured fields are still missing, the fast
   model extracts them from the scraped text as strict JSON.
"""
from __future__ import annotations

import contextvars
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover
    DDGS = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]

from app.llm.schema import BOOL, STR, arr, obj
from app.core.logging import get_logger
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService


_PRICE_RE = re.compile(
    r"\$[\s]?(\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?)"
    r"(?:\s?(?:/month|/mo|/year|/yr|k|K|m|M|per\s+\w+))?"
)
_RATING_RE = re.compile(r"(\d(?:\.\d)?)\s*(?:/\s*5|out of 5|stars?)", re.I)
_FOUNDED_RE = re.compile(
    r"\b(?:founded|established|since|incorporated|started)\s+(?:in\s+)?(\d{4})\b",
    re.I,
)
_AGGREGATOR_DOMAINS = {
    # search engines and ad redirects
    "bing.com", "google.com", "duckduckgo.com",
    # review sites
    "g2.com", "learn.g2.com", "gartner.com", "capterra.com", "trustradius.com",
    "peerspot.com", "selecthub.com", "softwareadvice.com", "getapp.com",
    "sourceforge.net",
    # encyclopedias / social / dev
    "wikipedia.org", "en.wikipedia.org", "linkedin.com", "youtube.com",
    "medium.com", "reddit.com", "github.com", "twitter.com", "x.com",
    # PR / press-release aggregators
    "businesswire.com", "prnewswire.com", "globenewswire.com",
    # business / data aggregators
    "forbes.com", "crunchbase.com", "glassdoor.com", "ambitionbox.com",
    "clutch.co", "cbinsights.com", "yahoo.com", "bloomberg.com", "marketwatch.com",
    # tech publications / listicle sites
    "techtarget.com", "cio.com", "datamation.com", "em360tech.com",
    "infoworld.com", "zdnet.com", "computerworld.com", "thectoclub.com",
    "eesel.ai", "openobserve.ai", "biz4group.com",
    # market-report publishers
    "futuremarketinsights.com", "marketsandmarkets.com", "grandviewresearch.com", "mordorintelligence.com",
    "gminsights.com", "fortunebusinessinsights.com", "precedenceresearch.com", "imarcgroup.com",
    "alliedmarketresearch.com", "researchandmarkets.com", "verifiedmarketresearch.com", "statista.com",
}

# Titles of pages that write *about* vendors rather than being one: listicles, comparisons, market reports.
_CONTENT_PAGE = re.compile(
    r"\b(?:top|best)\s+\d+|\b\d+\s+(?:best|top)\b|\blist of\b|\balternatives?\b|\s+vs\.?\s+|\bcompared\b|"
    r"\bmarket\s+(?:size|share|report|analysis|forecast|growth|trends?)\b|\bmagic quadrant\b",
    re.IGNORECASE,
)
logger = get_logger(__name__)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class CompanyHit:
    name: str
    domain: str
    matched_solutions: list[str] = field(default_factory=list)
    price: str | None = None
    review: str | None = None
    contact: str | None = None
    founded_year: int | None = None
    snippet: str = ""
    description: str = ""
    sources: list[str] = field(default_factory=list)
    scraped_text: str = ""

    def age_years(self) -> int | None:
        if self.founded_year is None:
            return None
        return max(0, datetime.now().year - self.founded_year)

    def to_row(self) -> dict:
        return {
            "Company": self.name,
            "About": self.description or (self.snippet[:180] + "…" if len(self.snippet) > 180 else self.snippet) or "—",
            "Matched solutions": ", ".join(self.matched_solutions) or "—",
            "Price": self.price or "—",
            "Review": self.review or "—",
            "Contact": self.contact or "—",
            "Age (years)": self.age_years() if self.age_years() is not None else "—",
            "Domain": self.domain,
            "Sources": " | ".join(self.sources[:3]),
        }


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _company_from_result(title: str, url: str) -> str | None:
    domain = _domain_of(url)
    if not domain or domain in _AGGREGATOR_DOMAINS:
        return None
    root = domain.split(".")[0]
    if root and root not in {"www", "blog", "docs", "support"}:
        return root.replace("-", " ").title()
    return None


def _extract_price(text: str) -> str | None:
    m = _PRICE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_rating(text: str) -> str | None:
    m = _RATING_RE.search(text)
    return f"{m.group(1)}/5" if m else None


def _extract_founded(text: str) -> int | None:
    m = _FOUNDED_RE.search(text)
    if m:
        try:
            year = int(m.group(1))
            if 1700 < year <= datetime.now().year:
                return year
        except ValueError:
            pass
    return None


def _clean_html_text(html: str, max_chars: int = 3000) -> str:
    if BeautifulSoup is None or not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""
    for tag in soup(["script", "style", "nav", "footer", "noscript", "svg", "form"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


class MarketResearchService:
    def __init__(
        self,
        *,
        max_per_query: int = 6,
        request_pause_s: float = 0.4,
        scrape_timeout_s: float = 6.0,
        max_scrape_pages: int = 2,
        llm_service: LLMService | None = None,
        use_llm_extraction: bool = True,
    ) -> None:
        self.max_per_query = max_per_query
        self.request_pause_s = request_pause_s
        self.scrape_timeout_s = scrape_timeout_s
        self.max_scrape_pages = max_scrape_pages
        self.llm_service = llm_service
        self.use_llm_extraction = use_llm_extraction and llm_service is not None

    # ── DDG search ────────────────────────────────────────────────────────
    def _search(self, query: str, max_results: int | None = None) -> list[dict]:
        if DDGS is None:
            return []
        try:
            with DDGS() as ddg:
                return list(ddg.text(query, max_results=max_results or self.max_per_query))
        except Exception:
            return []
        finally:
            time.sleep(self.request_pause_s)

    # ── Scraping ──────────────────────────────────────────────────────────
    def _fetch(self, url: str) -> str:
        try:
            resp = requests.get(
                url,
                timeout=self.scrape_timeout_s,
                headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
                allow_redirects=True,
            )
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", "").lower():
                return ""
            return resp.text
        except Exception:
            return ""

    def _scrape_company(self, hit: CompanyHit) -> str:
        if not hit.domain or BeautifulSoup is None:
            return ""
        base = f"https://{hit.domain}"
        candidate_paths = ["/", "/about", "/about-us", "/company", "/pricing", "/plans"]
        seen_text: list[str] = []
        for path in candidate_paths[: 1 + self.max_scrape_pages]:
            url = urljoin(base, path)
            html = self._fetch(url)
            if not html:
                continue
            text = _clean_html_text(html, max_chars=2000)
            if text:
                seen_text.append(text)
            if sum(len(t) for t in seen_text) > 4000:
                break
        return " ".join(seen_text)[:5000]

    # ── Model extraction (fast tier) ───────────────────────────────────────
    def _llm_extract(self, hit: CompanyHit) -> None:
        if not self.use_llm_extraction or not self.llm_service or not hit.scraped_text:
            return
        prompt = (
            f"Company: {hit.name}\n"
            "Extract these facts from the text. Use \"unknown\" when a fact is not present.\n"
            "- price: lowest or starting price as written (for example \"$99/month\")\n"
            "- review: a numeric rating such as \"4.5/5\"\n"
            "- contact: a named leader (CEO, founder, or head of sales)\n"
            "- founded_year: a 4-digit year\n\n"
            f"TEXT:\n{hit.scraped_text[:3000]}"
        )
        try:
            result = self.llm_service.complete_json(
                agent="market_research",
                system="You extract company facts from web page text and return JSON only.",
                prompt=prompt,
                schema=obj(price=STR, review=STR, contact=STR, founded_year=STR),
                schema_name="company_facts",
                purpose="company_facts",
                max_tokens=800,
                expected_tokens=150,
            )
        except LLMServiceError:
            return
        raw = result.text
        data = self._parse_json_loose(raw)
        if not data:
            return

        def _clean(value) -> str | None:
            if value is None:
                return None
            s = str(value).strip()
            if not s or s.lower() in {"unknown", "n/a", "none", "null", "—"}:
                return None
            return s

        if not hit.price:
            hit.price = _clean(data.get("price"))
        if not hit.review:
            hit.review = _clean(data.get("review"))
        if not hit.contact:
            hit.contact = _clean(data.get("contact"))
        if not hit.founded_year:
            year_raw = _clean(data.get("founded_year"))
            if year_raw:
                m = re.search(r"\b(\d{4})\b", year_raw)
                if m:
                    try:
                        year = int(m.group(1))
                        if 1700 < year <= datetime.now().year:
                            hit.founded_year = year
                    except ValueError:
                        pass

    @staticmethod
    def _parse_json_loose(raw: str) -> dict | None:
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        return obj if isinstance(obj, dict) else None

    # ── Public entrypoint ─────────────────────────────────────────────────
    def research(
        self,
        offerings: list[str],
        requirement_summary: str = "",
        industry: str | None = None,
        max_companies: int = 8,
    ) -> list[CompanyHit]:
        if not offerings:
            return []

        industry_hint = f" {industry}" if industry else ""
        queries: list[tuple[str, list[str]]] = []

        if len(offerings) >= 2:
            joined = " and ".join(offerings[:3])
            queries.append((f"companies offering {joined}{industry_hint} enterprise", offerings[:3]))
            for off in offerings[:3]:
                queries.append((f"vendors {off}{industry_hint} platform", [off]))
        else:
            off = offerings[0]
            queries.append((f"top {off}{industry_hint} vendors enterprise", [off]))
            queries.append((f"best {off} providers{industry_hint}", [off]))

        if requirement_summary:
            short = requirement_summary[:80]
            queries.append((f"{short} solution providers{industry_hint}", offerings[:2]))

        hits_by_company: dict[str, CompanyHit] = {}
        for query, tagged_offerings in queries:
            for r in self._search(query):
                title = (r.get("title") or "").strip()
                href = (r.get("href") or "").strip()
                body = (r.get("body") or "").strip()
                if _CONTENT_PAGE.search(title):
                    continue
                company = _company_from_result(title, href)
                if not company:
                    continue
                key = company.lower()
                hit = hits_by_company.get(key)
                if hit is None:
                    hit = CompanyHit(name=company, domain=_domain_of(href))
                    hits_by_company[key] = hit
                for off in tagged_offerings:
                    if off not in hit.matched_solutions:
                        hit.matched_solutions.append(off)
                if not hit.snippet and body:
                    hit.snippet = body
                if href and href not in hit.sources:
                    hit.sources.append(href)
                hit.price = hit.price or _extract_price(f"{title} {body}")
                hit.review = hit.review or _extract_rating(f"{title} {body}")
                hit.founded_year = hit.founded_year or _extract_founded(f"{title} {body}")
            if len(hits_by_company) >= max_companies * 2:
                break

        candidates = sorted(
            hits_by_company.values(),
            key=lambda h: (-len(h.matched_solutions), -len(h.sources), h.name.lower()),
        )[: max_companies * 2]
        ranked = self._vendor_check(candidates, offerings)[:max_companies]

        # Search-based enrichment hits the search engine, so it stays sequential (rate limits);
        # page fetches and model extraction run in parallel per company.
        for hit in ranked:
            self._enrich_via_search(hit)

        def finish(hit: CompanyHit) -> None:
            hit.scraped_text = self._scrape_company(hit)
            if hit.scraped_text:
                hit.price = hit.price or _extract_price(hit.scraped_text)
                hit.review = hit.review or _extract_rating(hit.scraped_text)
                hit.founded_year = hit.founded_year or _extract_founded(hit.scraped_text)
            self._llm_extract(hit)

        if ranked:
            with ThreadPoolExecutor(max_workers=min(6, len(ranked)), thread_name_prefix="vendor") as pool:
                list(pool.map(lambda h: contextvars.copy_context().run(finish, h), ranked))
        return ranked

    def _vendor_check(self, candidates: list[CompanyHit], offerings: list[str]) -> list[CompanyHit]:
        """Keep companies that sell the offerings (fast model). Without a model, keep the heuristic order."""
        if not candidates or not self.use_llm_extraction or not self.llm_service:
            return candidates
        listing = "\n".join(
            f"- {h.domain}: {h.name}. Search snippet: {(h.snippet or '')[:220]}" for h in candidates
        )
        try:
            result = self.llm_service.complete_json(
                agent="market_research",
                system=(
                    "You screen web search results for a sales team. A vendor is a company that sells a product or "
                    "service matching the offerings. Publishers, blogs, consultancies writing about the topic, job "
                    "sites, and generic tools that only mention it are not vendors. Return JSON only."
                ),
                prompt=f"Offerings: {', '.join(offerings)}\n\nCandidates:\n{listing}",
                schema=obj(vendors=arr(obj(domain=STR, is_vendor=BOOL, description=STR))),
                schema_name="vendor_screen",
                purpose="vendor_screen",
                max_tokens=2500,
                expected_tokens=600,
            )
        except LLMServiceError as exc:
            logger.info("Vendor screening skipped: %s", exc)
            return candidates
        verdicts = {
            str(v.get("domain", "")).lower().removeprefix("www."): v
            for v in (result.parsed or {}).get("vendors", [])
            if isinstance(v, dict)
        }
        kept = []
        for hit in candidates:
            verdict = verdicts.get(hit.domain)
            if verdict is None or verdict.get("is_vendor"):
                if verdict and verdict.get("description"):
                    hit.description = str(verdict["description"]).strip()[:240]
                kept.append(hit)
        return kept

    def _enrich_via_search(self, hit: CompanyHit) -> None:
        missing_any = not (hit.price and hit.review and hit.founded_year)
        if not missing_any:
            return
        for r in self._search(f"{hit.name} pricing reviews founded year", max_results=3):
            blob = f"{r.get('title','')} {r.get('body','')}"
            hit.price = hit.price or _extract_price(blob)
            hit.review = hit.review or _extract_rating(blob)
            hit.founded_year = hit.founded_year or _extract_founded(blob)
            href = (r.get("href") or "").strip()
            if href and href not in hit.sources:
                hit.sources.append(href)


def get_market_research_service(llm_service: LLMService | None = None) -> MarketResearchService:
    return MarketResearchService(llm_service=llm_service)
