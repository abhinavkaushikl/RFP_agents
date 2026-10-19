"""Prompt builders for proposal sections.

Layout is chosen for Groq's automatic prompt caching (prefix match):

    [system]  writing rules for this profile            ← identical for every call
    [user]    RFP CONTEXT                                ← identical for every section in a run
              SECTION TO WRITE + PRECEDENT + task line   ← differs per section

Everything here is deterministic (no timestamps, stable ordering) so the
cached prefix stays byte-for-byte identical.
"""
from __future__ import annotations

from typing import Any, TypedDict

from app.domain.profile import DomainProfile, SectionDef

PROMPT_VERSION = "2026-10-19.1"

MAX_REQUIREMENTS_IN_PROMPT = 30
MAX_EVIDENCE_CHARS = 700


class SectionPromptContext(TypedDict, total=False):
    client_name: str
    industry: str
    solution_type: str
    title: str
    request_summary: str
    requirements: list[str]
    requirement_details: list[dict[str, Any]]
    evaluation_criteria: list[str]
    timeline: str
    budget: str
    compliance_requirements: list[str]
    vendors: list[str]
    offerings: list[str]
    positioning_notes: list[str]
    user_instruction: str


def system_prompt(profile: DomainProfile) -> str:
    org = profile.organization
    writing = profile.writing
    lines = [
        f"You are a senior proposal writer at {org.name}, drafting one section of a response to a "
        "Request for Proposal (RFP). The reader is the buyer's evaluation committee.",
    ]
    if org.description:
        lines.append(f"About {org.name}: {org.description}")
    if org.differentiators:
        lines.append(f"{org.name} differentiators: " + "; ".join(org.differentiators))
    lines += [
        "",
        "Writing rules:",
        f"- Voice: {writing.tone}. Spelling: {writing.locale}. Currency: {writing.currency}.",
        "- Use only facts from the RFP context, our offerings, and the precedent excerpts. Never invent client "
        "names, statistics, prices, certifications, dates, or references.",
        "- When a needed fact is missing, state it as an explicit assumption (\"Assumption: …\") instead of inventing it.",
        "- Address the buyer's requirements directly, refer to them in the buyer's own terms, and make commitments concrete.",
        "- Treat precedent as style and substance guidance from past proposals for other clients: reuse ideas, never their client names or figures.",
        "- Format in Markdown: bold sub-headings, short paragraphs, bullets where they help scanning. Do not add a document title.",
        "- No meta-commentary, no placeholders such as [Client Name], no citation markers.",
        "- Stay within the word range given for the section.",
    ]
    lines += [f"- {rule}" for rule in writing.style_rules]
    return "\n".join(lines)


def _bullets(items: list[str], empty: str = "(none stated)") -> str:
    clean = [str(i).strip() for i in items if str(i).strip()]
    return "\n".join(f"- {i}" for i in clean) if clean else f"- {empty}"


def rfp_context_block(ctx: SectionPromptContext) -> str:
    details = ctx.get("requirement_details") or []
    if details:
        req_lines = [
            f"- [{d.get('id') or f'R{i}'}] ({d.get('priority', 'should')}) {d.get('text', '')}"
            for i, d in enumerate(details[:MAX_REQUIREMENTS_IN_PROMPT], 1)
        ]
        requirements = "\n".join(req_lines)
    else:
        requirements = _bullets((ctx.get("requirements") or [])[:MAX_REQUIREMENTS_IN_PROMPT])
    parts = [
        "## RFP CONTEXT",
        f"Client: {ctx.get('client_name') or 'the client'}",
        f"Industry: {ctx.get('industry') or 'Unspecified'}",
        f"Solution type: {ctx.get('solution_type') or 'general'}",
        f"RFP title: {ctx.get('title') or '(not stated)'}",
        "",
        "Summary:",
        (ctx.get("request_summary") or "(no summary)").strip(),
        "",
        "Requirements:",
        requirements,
        "",
        "Evaluation criteria:",
        _bullets(ctx.get("evaluation_criteria") or []),
        "",
        f"Timeline: {ctx.get('timeline') or '(not stated)'}",
        f"Budget: {ctx.get('budget') or '(not stated)'}",
        "Compliance and standards:",
        _bullets(ctx.get("compliance_requirements") or []),
        "Systems, products, and vendors mentioned by the buyer:",
        _bullets(ctx.get("vendors") or []),
        "",
        "Our relevant offerings or capabilities:",
        _bullets(ctx.get("offerings") or [], empty="(no catalog match; describe capabilities generically)"),
        "Positioning notes:",
        _bullets(ctx.get("positioning_notes") or []),
    ]
    instruction = (ctx.get("user_instruction") or "").strip()
    if instruction:
        parts += ["", f"Instruction from the bid team (applies to every section): {instruction}"]
    return "\n".join(parts)


def _evidence_block(evidence: list[dict[str, Any]], max_items: int) -> str:
    lines: list[str] = []
    for i, item in enumerate(evidence[:max_items], 1):
        text = " ".join((item.get("content") or "").split())
        if not text:
            continue
        if len(text) > MAX_EVIDENCE_CHARS:
            text = text[:MAX_EVIDENCE_CHARS].rsplit(" ", 1)[0] + "…"
        source = item.get("section_key") or "section"
        lines.append(f"[{i}] (from a past '{source}' section) {text}")
    return "\n".join(lines) or "(no precedent found — write from the RFP context only)"


def section_task_block(section: SectionDef, evidence: list[dict[str, Any]], max_evidence: int = 4) -> str:
    low, high = section.words
    headings = ", ".join(section.headings) if section.headings else "choose 3-4 fitting sub-headings"
    return "\n".join(
        [
            "## SECTION TO WRITE",
            f"Section: {section.title} ({low}-{high} words)",
            f"Guidance: {section.guidance or 'Address the parts of the RFP relevant to this section.'}",
            f"Suggested sub-headings: {headings}",
            "",
            "## PRECEDENT FROM PAST PROPOSALS",
            _evidence_block(evidence, max_evidence),
            "",
            f"Write the {section.title} section now. Start directly with the first bold sub-heading.",
        ]
    )


def build_section_messages(
    profile: DomainProfile,
    ctx: SectionPromptContext,
    section_key: str,
    evidence: list[dict[str, Any]],
    max_evidence: int = 4,
) -> list[dict[str, str]]:
    section = profile.section(section_key)
    return [
        {"role": "system", "content": system_prompt(profile)},
        {
            "role": "user",
            "content": rfp_context_block(ctx) + "\n\n" + section_task_block(section, evidence, max_evidence),
        },
    ]


__all__ = [
    "PROMPT_VERSION",
    "SectionPromptContext",
    "build_section_messages",
    "rfp_context_block",
    "section_task_block",
    "system_prompt",
]
