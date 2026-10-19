"""Intent detection: opportunity basics from a conversation (fast model).

Pulls the opportunity name, client, relationship, date opened, and urgency.
Regex extraction remains as the degraded-mode fallback and fills gaps.
"""
from __future__ import annotations

import re
from datetime import date as date_cls

from app.agents.base import PlatformAgent
from app.agents.normalize import clean_text, normalize_choice
from app.agents.schema import STR, enum, obj
from app.agents.transcript import transcript_messages
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

RELATIONSHIPS = ("New logo", "Existing customer", "Lapsed customer", "Partner", "Unknown")

_SCHEMA = obj(
    opportunity_name=STR,
    client_name=STR,
    existing_relationship=enum(*RELATIONSHIPS),
    date_opened=STR,
    urgency_statement=STR,
    primary_contact=STR,
)

_TASK = (
    "Extract the opportunity basics:\n"
    "- opportunity_name: the deal, project, or RFP name as stated; otherwise a short descriptive name.\n"
    "- client_name: the buying organization (not the vendor).\n"
    "- existing_relationship: one of " + ", ".join(RELATIONSHIPS) + ".\n"
    "- date_opened: the conversation or opportunity date as YYYY-MM-DD, or \"\" if absent.\n"
    "- urgency_statement: one sentence on deadlines or time pressure, or \"\" if none.\n"
    "- primary_contact: the buyer's main contact as 'Name, Role', or \"\" if absent.\n"
    "Return JSON only."
)

_DATE_PATTERNS = [
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/20\d{2})\b"),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b", re.I),
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
    "urgent", "asap", "deadline", "by end of", "this quarter", "fiscal year", "renewal", "expiring",
    "go-live", "go live", "due date",
)


def _first_match(patterns: list[re.Pattern], text: str) -> str:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return ""


def _relationship(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in ("existing customer", "current customer", "renewal", "expansion", "expanding the relationship")):
        return "Existing customer"
    if any(k in lowered for k in ("first call", "intro call", "discovery call", "new logo", "prospect")):
        return "New logo"
    if "lapsed" in lowered or "former customer" in lowered:
        return "Lapsed customer"
    return "Unknown"


def _urgency(text: str) -> str:
    lowered = text.lower()
    for keyword in _URGENCY_KEYWORDS:
        idx = lowered.find(keyword)
        if idx >= 0:
            return " ".join(text[max(0, idx - 60): idx + 180].split())[:240]
    return ""


def regex_overview(text: str) -> dict:
    return {
        "opportunity_name": _first_match(_OPPORTUNITY_HINTS, text),
        "client_name": _first_match(_CLIENT_HINTS, text),
        "existing_relationship": _relationship(text),
        "date_opened": _first_match(_DATE_PATTERNS, text),
        "urgency_statement": _urgency(text),
        "primary_contact": "",
    }


class IntentDetectionAgent(PlatformAgent):
    name = "intent_detection"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        text = payload.get("transcript_text") or ""
        if not text.strip():
            raise ValueError("transcript_text is empty")
        fallback = regex_overview(text)
        overview = dict(fallback)
        mode = "heuristic"
        if self.llm is not None:
            try:
                parsed = self.llm.complete_json(
                    agent=self.name,
                    messages=transcript_messages(text, _TASK),
                    schema=_SCHEMA,
                    schema_name="opportunity_basics",
                    purpose="detect_intent_fields",
                    max_tokens=1500,
                    expected_tokens=300,
                ).parsed
                for key in ("opportunity_name", "client_name", "date_opened", "urgency_statement", "primary_contact"):
                    value = clean_text(parsed.get(key))
                    if value:
                        overview[key] = value
                overview["existing_relationship"] = normalize_choice(
                    parsed.get("existing_relationship"), RELATIONSHIPS, fallback["existing_relationship"]
                )
                mode = "llm"
            except LLMServiceError:
                if not self.llm.degraded_allowed:
                    raise
        if not overview["date_opened"]:
            overview["date_opened"] = date_cls.today().isoformat()
        client_overview = {
            **overview,
            "problem_statement": "",
            "success_definition": "",
            "stakeholder_impact": "",
        }
        return AgentResult(
            self.name,
            {
                "client_overview": client_overview,
                "buyer_readiness": {"readiness_rating": 0, "buying_gaps": "", "stakeholder_coverage": ""},
                "product_fit": {"notes": ""},
                "mode": mode,
            },
            f"Extracted opportunity basics from a {len(text):,}-character conversation ({mode}).",
            0.8 if mode == "llm" else 0.5,
        )
