"""Intent Detection — stub agent that runs cheap regex over a transcript.

Placeholder for the eventual three sub-agents (Client Overview, Buyer
Readiness, Product Fit). The shape of the response is final so the UI can
bind to it now; the extraction logic gets replaced in a later pass.
"""
from __future__ import annotations

import re
from datetime import date as date_cls

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


_DATE_PATTERNS = [
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/20\d{2})\b"),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b",
        re.I,
    ),
]
_CLIENT_HINTS = [
    re.compile(r"(?im)^\s*(?:client|company|account|customer)\s*[:\-]\s*(.+)$"),
    re.compile(r"(?im)^\s*(?:from|to)\s*[:\-]\s*[^<\n]*<[^@>]+@([\w\.-]+)>"),
]
_OPPORTUNITY_HINTS = [
    re.compile(r"(?im)^\s*(?:opportunity|opp|deal|project)\s*[:\-]\s*(.+)$"),
    re.compile(r"(?im)^\s*subject\s*[:\-]\s*(.+)$"),
]
_URGENCY_KEYWORDS = (
    "urgent", "asap", "deadline", "by end of", "this quarter",
    "fiscal year", "renewal", "expiring", "rfp deadline",
)


def _first_match(patterns: list[re.Pattern], text: str) -> str | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return None


def _detect_relationship(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in ("existing customer", "current customer", "renewal", "expansion")):
        return "Existing customer"
    if any(k in lowered for k in ("first call", "intro call", "discovery call", "new logo", "prospect")):
        return "New logo"
    if "lapsed" in lowered or "former customer" in lowered:
        return "Lapsed customer"
    return "Unknown"


def _extract_urgency_lines(text: str, max_chars: int = 240) -> str:
    lowered = text.lower()
    for keyword in _URGENCY_KEYWORDS:
        idx = lowered.find(keyword)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(text), idx + 180)
            return text[start:end].strip()[:max_chars]
    return ""


class IntentDetectionAgent(PlatformAgent):
    name = "intent_detection"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        text = (payload.get("transcript_text") or "")[:60_000]

        client_overview = {
            "opportunity_name": _first_match(_OPPORTUNITY_HINTS, text) or "",
            "client_name": _first_match(_CLIENT_HINTS, text) or "",
            "existing_relationship": _detect_relationship(text),
            "date_opened": _first_match(_DATE_PATTERNS, text) or date_cls.today().isoformat(),
            "problem_statement": "",
            "success_definition": "",
            "stakeholder_impact": "",
            "urgency_statement": _extract_urgency_lines(text),
        }
        buyer_readiness = {
            "readiness_rating": 0,
            "buying_gaps": "",
            "stakeholder_coverage": "",
        }
        product_fit = {"notes": ""}

        return AgentResult(
            self.name,
            {
                "client_overview": client_overview,
                "buyer_readiness": buyer_readiness,
                "product_fit": product_fit,
            },
            f"Pre-filled intent fields from {len(text)}-char transcript (stub).",
            0.5,
        )
