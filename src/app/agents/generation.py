"""Section generation agent (frontier model, Redis section cache)."""
from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.prompts import SectionPromptContext, build_section_messages
from app.core.config import get_settings
from app.domain.profile import DomainProfile, load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

_CONTEXT_KEYS = (
    "client_name", "industry", "solution_type", "title", "request_summary", "requirements",
    "requirement_details", "evaluation_criteria", "timeline", "budget", "compliance_requirements",
    "vendors", "positioning_notes", "user_instruction",
)


class GenerationAgent(PlatformAgent):
    name = "generation"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        section_key = profile.canonical_section_key(payload["section_key"])
        section = profile.section(section_key)
        evidence = payload.get("evidence") or []
        ctx = SectionPromptContext(**{k: payload.get(k) for k in _CONTEXT_KEYS if payload.get(k) is not None})
        ctx["offerings"] = payload.get("matching_offerings") or []
        citations = [item.get("chunk_id") or item.get("id") or "" for item in evidence[:4]]

        if payload.get("fast_mode"):
            draft = self._template_draft(profile, section_key, ctx, evidence)
            return self._result(section_key, section.title, draft, citations, "template", None, False,
                                ["Template draft (fast mode); no model call."], 0.5)

        settings = get_settings()
        messages = build_section_messages(profile, ctx, section_key, evidence, settings.retrieval_top_k)
        low, high = section.words
        try:
            result = self.llm.complete(
                agent=self.name,
                messages=messages,
                section_key=section_key,
                cache_kind="section",
                purpose="generate_section",
                max_tokens=max(2500, high * 4 + 1500),
                expected_tokens=high * 2 + 600,
            )
        except LLMServiceError as exc:
            if not self.llm.degraded_allowed:
                raise
            draft = self._template_draft(profile, section_key, ctx, evidence)
            return self._result(section_key, section.title, draft, citations, "fallback", None, False,
                                [f"Model call failed ({exc}); template draft used."], 0.4)

        mode = "cache" if result.cache_hit else "llm"
        notes = [
            f"{'Served from section cache' if result.cache_hit else 'Generated'} with {result.model} "
            f"using {len(evidence)} precedent chunks."
        ]
        return self._result(section_key, section.title, result.text, citations, mode, result.model,
                            result.cache_hit, notes, 0.85, usage=result.usage.to_dict())

    def _result(self, section_key, title, draft, citations, mode, model, cache_hit, notes, confidence, usage=None):
        output = {
            "section_key": section_key,
            "title": title,
            "draft_text": draft,
            "citations": citations,
            "generation_mode": mode,
            "model": model,
            "cache_hit": cache_hit,
            "word_count": len(draft.split()),
            "generation_notes": notes,
        }
        if usage:
            output["usage"] = {
                k: usage.get(k)
                for k in ("prompt_tokens", "cached_prompt_tokens", "completion_tokens", "total_tokens",
                          "cost_usd", "saved_tokens", "latency_ms")
            }
        return AgentResult(self.name, output, f"{title}: {output['word_count']} words ({mode}).", confidence)

    def _template_draft(self, profile: DomainProfile, section_key: str, ctx: SectionPromptContext, evidence: list[dict]) -> str:
        """Deterministic outline used only in fast mode or degraded mode."""
        section = profile.section(section_key)
        client = ctx.get("client_name") or "the client"
        requirements = (ctx.get("requirements") or [])[:6]
        offerings = (ctx.get("offerings") or [])[:4]
        lines = [f"**{section.title}**", ""]
        summary = (ctx.get("request_summary") or "").strip()
        if summary:
            lines += [f"**Context.** {summary}", ""]
        if requirements:
            lines.append(f"**Requirements addressed for {client}**")
            lines += [f"- {r}" for r in requirements]
            lines.append("")
        if offerings:
            lines.append("**Relevant capabilities**")
            lines += [f"- {o}" for o in offerings]
            lines.append("")
        points = [" ".join((e.get("content") or "").split())[:240] for e in evidence[:2] if e.get("content")]
        if points:
            lines.append("**Precedent to adapt**")
            lines += [f"- {p}" for p in points]
            lines.append("")
        lines.append("_Draft outline generated without the model. Regenerate with the model before submission._")
        return "\n".join(lines)
