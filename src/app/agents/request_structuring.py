"""Request structuring: raw RFP text → structured brief (requirements, criteria, constraints)."""
from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.normalize import as_text_list, clean_text, normalize_choice
from app.agents.schema import STR, arr, enum, obj
from app.agents.utils import extract_requirements, lead_paragraph, summarize_text
from app.domain.profile import DomainProfile, load_profile, slugify
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

MAX_REQUEST_CHARS = 60_000
MAX_REQUIREMENTS = 40

_SCHEMA = obj(
    title=STR,
    client_name=STR,
    industry=STR,
    request_summary=STR,
    requirements=arr(
        obj(
            id=STR,
            text=STR,
            category=STR,
            priority=enum("must", "should", "could"),
        )
    ),
    evaluation_criteria=arr(STR),
    deliverables=arr(STR),
    timeline=STR,
    budget=STR,
    compliance_requirements=arr(STR),
    mentioned_vendors=arr(STR),
    solution_type=STR,
    ambiguity_flags=arr(STR),
)


def _system_prompt(profile: DomainProfile) -> str:
    industries = ", ".join(profile.industry_names) or "any"
    if profile.offerings:
        solution_hint = (
            "Prefer one of these offering codes when it fits, otherwise write a short new label: "
            + ", ".join(o.code for o in profile.offerings)
            + "."
        )
    else:
        solution_hint = "Write a short label for the kind of solution requested."
    frameworks = ", ".join(profile.lexicons.compliance_frameworks)
    return (
        "You are a senior bid manager. Turn raw RFP text into a structured brief.\n\n"
        "Rules:\n"
        "- Extract only what the text supports. Never invent requirements, dates, budgets, or names; use an empty string or empty list when absent.\n"
        "- A requirement is something the buyer needs the vendor to do, deliver, comply with, or demonstrate. Split compound requirements into separate items and keep the buyer's wording.\n"
        "- Ignore contact details (names, phone numbers, emails), form labels, and drafting instructions; they are not requirements.\n"
        "- priority: \"must\" for mandatory language (must, shall, required, mandatory), \"should\" for stated preferences, \"could\" for nice-to-haves.\n"
        "- category: one short lowercase label such as functional, technical, integration, security, compliance, delivery, support, staffing, reporting, commercial.\n"
        "- id: R1, R2, R3 … in order of appearance.\n"
        f"- industry: the closest of [{industries}], or \"Other\".\n"
        f"- solution_type: snake_case. {solution_hint}\n"
        f"- compliance_requirements: regulations, standards, or certifications named (for example {frameworks}).\n"
        "- mentioned_vendors: products, platforms, incumbent suppliers, or vendors named in the text.\n"
        "- request_summary: 2-4 neutral sentences on what the buyer wants and why.\n"
        "- ambiguity_flags: short notes on missing or contradictory information a bid team should clarify.\n"
        "Return JSON only."
    )


class RequestStructuringAgent(PlatformAgent):
    name = "request_structuring"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        request_text = (payload.get("request_text") or "")[:MAX_REQUEST_CHARS]
        if not request_text.strip():
            raise ValueError("request_text is empty")

        hints = {
            "title": clean_text(payload.get("title")),
            "client_name": clean_text(payload.get("client_name")),
            "industry": clean_text(payload.get("industry")),
            "solution_type": clean_text(payload.get("solution_type")),
        }
        parsed: dict | None = None
        mode = "llm"
        if self.llm is not None:
            prompt = (
                "Hints supplied by the user (may be empty; trust them over the text when present):\n"
                f"- title: {hints['title'] or '(none)'}\n"
                f"- client: {hints['client_name'] or '(none)'}\n"
                f"- industry: {hints['industry'] or '(none)'}\n"
                f"- solution type: {hints['solution_type'] or '(none)'}\n\n"
                f"RFP TEXT:\n<<<\n{request_text}\n>>>"
            )
            try:
                result = self.llm.complete_json(
                    agent=self.name,
                    system=_system_prompt(profile),
                    prompt=prompt,
                    schema=_SCHEMA,
                    schema_name="rfp_brief",
                    purpose="structure_request",
                    max_tokens=6000,
                    expected_tokens=1800,
                )
                parsed = result.parsed
            except LLMServiceError:
                if not self.llm.degraded_allowed:
                    raise
                mode = "heuristic"
        else:
            mode = "heuristic"

        output = self._from_llm(parsed, hints, profile) if parsed else self._heuristic(request_text, hints, profile)
        output["extraction_mode"] = mode if parsed else "heuristic"
        count = len(output["requirements"])
        return AgentResult(
            self.name,
            output,
            f"Structured request: {count} requirements ({output['extraction_mode']}).",
            0.85 if parsed else 0.5,
        )

    # ── shaping ───────────────────────────────────────────────────────
    def _finalize(self, out: dict, hints: dict, profile: DomainProfile) -> dict:
        industry = hints["industry"] or out.get("industry") or ""
        out["industry"] = profile.canonical_industry(industry) or "Unspecified"
        solution = hints["solution_type"] or out.get("solution_type") or "general"
        out["solution_type"] = slugify(solution)
        out["title"] = hints["title"] or out.get("title") or "Proposal request"
        out["client_name"] = hints["client_name"] or out.get("client_name") or ""
        if not out["requirements"]:
            out.setdefault("ambiguity_flags", []).append("No explicit requirements found in the request text.")
        return out

    def _from_llm(self, parsed: dict, hints: dict, profile: DomainProfile) -> dict:
        details = []
        for idx, item in enumerate(parsed.get("requirements") or [], 1):
            if not isinstance(item, dict):
                continue
            text = clean_text(item.get("text"))
            if not text:
                continue
            details.append(
                {
                    "id": clean_text(item.get("id")) or f"R{idx}",
                    "text": text,
                    "category": clean_text(item.get("category")).lower() or "general",
                    "priority": normalize_choice(item.get("priority"), ["must", "should", "could"], "should"),
                }
            )
            if len(details) >= MAX_REQUIREMENTS:
                break
        out = {
            "title": clean_text(parsed.get("title")),
            "client_name": clean_text(parsed.get("client_name")),
            "industry": clean_text(parsed.get("industry")),
            "request_summary": clean_text(parsed.get("request_summary")),
            "requirements": [d["text"] for d in details],
            "requirement_details": details,
            "evaluation_criteria": as_text_list(parsed.get("evaluation_criteria"), limit=15),
            "deliverables": as_text_list(parsed.get("deliverables"), limit=20),
            "timeline": clean_text(parsed.get("timeline")),
            "budget": clean_text(parsed.get("budget")),
            "compliance_requirements": as_text_list(parsed.get("compliance_requirements"), limit=15),
            "vendors": as_text_list(parsed.get("mentioned_vendors"), limit=15),
            "solution_type": clean_text(parsed.get("solution_type")),
            "ambiguity_flags": as_text_list(parsed.get("ambiguity_flags"), limit=10),
        }
        return self._finalize(out, hints, profile)

    def _heuristic(self, text: str, hints: dict, profile: DomainProfile) -> dict:
        requirements = extract_requirements(text)
        lowered = text.lower()
        compliance = [f for f in profile.lexicons.compliance_frameworks if f.lower() in lowered]
        vendors = [c for c in profile.lexicons.competitors if c.lower() in lowered]
        out = {
            "title": "",
            "client_name": "",
            "industry": "",
            "request_summary": summarize_text(lead_paragraph(text), 500),
            "requirements": requirements,
            "requirement_details": [
                {"id": f"R{i}", "text": r, "category": "general", "priority": "should"}
                for i, r in enumerate(requirements, 1)
            ],
            "evaluation_criteria": [],
            "deliverables": [],
            "timeline": "",
            "budget": "",
            "compliance_requirements": compliance,
            "vendors": vendors,
            "solution_type": "",
            "ambiguity_flags": ["Extracted without the model; review requirements manually."],
        }
        return self._finalize(out, hints, profile)
