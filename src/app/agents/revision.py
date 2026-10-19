"""Revision agent: apply a user instruction to an existing section (frontier model)."""
from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.normalize import as_text_list, clean_text
from app.agents.prompts import system_prompt
from app.agents.schema import STR, arr, obj
from app.domain.profile import load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

_SCHEMA = obj(revised_text=STR, change_summary=STR, changed_topics=arr(STR))

_REVISION_RULES = (
    "\n\nYou are revising an existing section. Apply the instruction precisely, keep every requirement "
    "the draft already addresses, keep the voice and structure unless told otherwise, and keep the "
    "length within ±20% unless the instruction asks for a different length. Return JSON with the full "
    "revised section in revised_text (Markdown), a one-sentence change_summary, and the topics changed."
)


def _evidence(evidence: list[dict], max_items: int = 3, max_chars: int = 500) -> str:
    lines = []
    for i, item in enumerate(evidence[:max_items], 1):
        text = " ".join((item.get("content") or "").split())
        if text:
            lines.append(f"[{i}] {text[:max_chars]}")
    return "\n".join(lines) or "(no additional precedent)"


class RevisionAgent(PlatformAgent):
    name = "revision"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        section_key = profile.canonical_section_key(payload.get("section_key") or "section")
        section = profile.section(section_key)
        base_text = payload.get("base_text") or ""
        instruction = (payload.get("instruction") or "").strip()
        requirements = payload.get("requirements") or []
        if not base_text.strip():
            raise ValueError("Nothing to revise: base_text is empty")
        if not instruction:
            raise ValueError("A revision instruction is required")

        low, high = section.words
        prompt = (
            f"Section: {section.title} (target {low}-{high} words)\n"
            f"Section guidance: {section.guidance}\n\n"
            f"CURRENT DRAFT:\n<<<\n{base_text}\n>>>\n\n"
            "REQUIREMENTS TO KEEP ADDRESSED:\n"
            + ("\n".join(f"- {r}" for r in requirements[:20]) or "- (none supplied)")
            + f"\n\nPRECEDENT (optional):\n{_evidence(payload.get('evidence') or [])}\n\n"
            f"INSTRUCTION:\n{instruction}"
        )
        try:
            result = self.llm.complete_json(
                agent=self.name,
                system=system_prompt(profile) + _REVISION_RULES,
                prompt=prompt,
                schema=_SCHEMA,
                schema_name="revision",
                purpose="revise_section",
                section_key=section_key,
                cache_kind="section",
                max_tokens=max(3000, high * 5 + 1500),
                expected_tokens=high * 2 + 600,
            )
        except LLMServiceError as exc:
            if not self.llm.degraded_allowed:
                raise
            output = {
                "section_key": section_key,
                "draft_text": base_text,
                "revision_summary": f"Model unavailable ({exc}); original draft kept.",
                "changed_topics": [],
                "preserved_constraints": requirements,
                "model": None,
                "cache_hit": False,
                "generation_mode": "fallback",
            }
            return AgentResult(self.name, output, f"Kept original {section_key} (model unavailable).", 0.3)

        parsed = result.parsed
        revised = (parsed.get("revised_text") or "").strip() or base_text
        output = {
            "section_key": section_key,
            "draft_text": revised,
            "revision_summary": clean_text(parsed.get("change_summary")) or f"Applied: {instruction}",
            "changed_topics": as_text_list(parsed.get("changed_topics"), limit=8) or [instruction],
            "preserved_constraints": requirements,
            "model": result.model,
            "cache_hit": result.cache_hit,
            "generation_mode": "cache" if result.cache_hit else "llm",
        }
        return AgentResult(self.name, output, f"Revised {section.title} ({len(revised.split())} words).", 0.85)
