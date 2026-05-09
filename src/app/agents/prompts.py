"""Section-specific RFP prompt registry.

Designed for local Mistral 7B Instruct (Ollama). We pass a compact summary —
not full retrieved chunks — to keep prompts small and generation fast.
"""
from __future__ import annotations

from typing import TypedDict


class SectionPromptContext(TypedDict):
    section_key: str
    client_name: str
    industry: str
    request_summary: str
    requirements: list[str]
    vendors: list[str]
    offerings: list[str]
    evidence_chunks: list[str]
    solution_type: str


SYSTEM_PROMPT = (
    "You are a senior solution architect drafting an RFP response section. "
    "Write professionally, specifically, and only from the provided context. "
    "Use bold sub-headings and short paragraphs. No marketing fluff, no placeholders, "
    "no meta-commentary. Output the section content only — start with the first heading."
)


_SECTION_BRIEFS: dict[str, str] = {
    "executive_summary": (
        "Section: EXECUTIVE SUMMARY (180–240 words).\n"
        "Sub-headings: Strategic Context, Proposed Approach, Quantified Outcomes (4 bullets), "
        "Why Choose Us."
    ),
    "deal_storytelling": (
        "Section: DEAL NARRATIVE (240–320 words, prose only, 4 short paragraphs).\n"
        "Each paragraph leads with a bold phrase: Where the client stands today, "
        "Cost of standing still, Path we propose, What it unlocks."
    ),
    "solution_overview": (
        "Section: SOLUTION OVERVIEW (200–280 words).\n"
        "Sub-headings: Capabilities, How It Works, Integration Fit, Outcomes."
    ),
    "competitor_positioning": (
        "Section: COMPETITIVE POSITIONING (200–280 words).\n"
        "Sub-headings: Likely Incumbents, Capability Gaps (3–4 bullets), "
        "Where We Win (4 bullets), Lock-in Risk. Frame gaps, do not disparage."
    ),
    "implementation_plan": (
        "Section: IMPLEMENTATION PLAN (260–360 words).\n"
        "Four phases as bold sub-headers: Discovery (Wks 1–4), Foundation (Wks 5–10), "
        "Integration (Wks 11–18), Hypercare (Wks 19–24). Each: 3 bullets. "
        "Then Team (5 roles) and Milestones (3 bullets)."
    ),
    "pricing_notes": (
        "Section: PRICING & COMMERCIALS (200–280 words).\n"
        "Sub-headings: Commercial Summary, License & Subscription (bulleted SKUs as "
        "`SKU-NAME`: $X/year — desc), One-Time Implementation, Payment Milestones (4 bullets), ROI."
    ),
    "financials": (
        "Section: FINANCIAL BUSINESS CASE (180–240 words).\n"
        "Sub-headings: Year-1 Investment, Year-1 Savings, Payback Period, "
        "3-Year TCO (markdown 2-row table), Soft Benefits (3 bullets)."
    ),
    "architecture_diagram": (
        "Section: SOLUTION ARCHITECTURE (220–300 words, text-only).\n"
        "Six layered sub-headings: Ingestion, Streaming & Event Bus, ML / Root-Cause Engine, "
        "Automation, Operator Console, Integration Points."
    ),
    "contract_annexure": (
        "Section: CONTRACTUAL TERMS & SLA (200–280 words).\n"
        "Sub-headings: SLA Targets, Penalty Structure, Escalation Matrix (L1/L2/L3), "
        "Reporting Cadence, Standard Safeguards."
    ),
}

_DEFAULT_BRIEF = (
    "Section: {section_title} (200–260 words).\n"
    "Use 3–4 short sub-sections with bold headings."
)


_PROMPT_TEMPLATE = """{section_brief}

Client: {client_name} ({industry})
Solution family: {solution_type}

REQUEST SUMMARY:
{request_summary}

KEY REQUIREMENTS:
{requirements}

OUR OFFERINGS: {offerings}
VENDORS IN CLIENT ENV: {vendors}

PRECEDENT (use only what is supported; do not invent):
{evidence_summary}

Write the section now. Begin directly with the first bold heading."""


def _summarize_evidence(chunks: list[str], max_chunks: int = 2, max_chars: int = 240) -> str:
    if not chunks:
        return "(no precedent — write from the request and requirements only)"
    lines: list[str] = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        text = " ".join((chunk or "").split())
        if not text:
            continue
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "…"
        lines.append(f"[{i}] {text}")
    return "\n".join(lines) or "(no precedent available)"


def build_section_prompt(section_key: str, ctx: SectionPromptContext) -> str:
    """Render a compact prompt for one RFP section."""
    section_title = section_key.replace("_", " ").title()
    brief = _SECTION_BRIEFS.get(section_key, _DEFAULT_BRIEF.format(section_title=section_title.upper()))

    requirements = ctx["requirements"][:5]
    requirements_block = (
        "\n".join(f"- {r[:160]}" for r in requirements) or "- (none specified)"
    )
    vendors_block = ", ".join(ctx["vendors"][:5]) if ctx["vendors"] else "(none detected)"
    offerings_block = (
        ", ".join(ctx["offerings"][:4])
        if ctx["offerings"]
        else "platform integration, analytics, managed services"
    )
    request_summary = (ctx["request_summary"] or "Address the stated RFP priorities.").strip()
    if len(request_summary) > 480:
        request_summary = request_summary[:480].rsplit(" ", 1)[0] + "…"
    evidence_summary = _summarize_evidence(ctx["evidence_chunks"])

    return _PROMPT_TEMPLATE.format(
        section_brief=brief,
        client_name=ctx["client_name"] or "the client",
        industry=ctx["industry"] or "Telecommunications",
        solution_type=ctx["solution_type"] or "aiops_general",
        request_summary=request_summary,
        requirements=requirements_block,
        offerings=offerings_block,
        vendors=vendors_block,
        evidence_summary=evidence_summary,
    )


__all__ = ["SYSTEM_PROMPT", "SectionPromptContext", "build_section_prompt"]
