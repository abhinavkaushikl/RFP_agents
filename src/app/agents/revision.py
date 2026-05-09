from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.prompts import SYSTEM_PROMPT
from app.schemas.domain import AgentContext, AgentResult
from app.services.llm_service import LLMService, LLMServiceError


REVISION_PROMPT_TEMPLATE = """Revise the **{section_label}** section of an RFP response.

CURRENT DRAFT:
\"\"\"
{base_text}
\"\"\"

USER INSTRUCTION:
{instruction}

REQUIREMENTS TO PRESERVE:
{requirements}

EVIDENCE (use only if it helps):
{evidence}

Apply the instruction while preserving every requirement and the original tone. Keep the same length (±20%). Output ONLY the revised section."""


def _short_evidence(evidence: list[dict], max_items: int = 2, max_chars: int = 220) -> str:
    lines: list[str] = []
    for i, item in enumerate(evidence[:max_items], 1):
        text = " ".join((item.get("content") or "").split())
        if not text:
            continue
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "…"
        lines.append(f"[{i}] {text}")
    return "\n".join(lines) or "(no additional evidence)"


class RevisionAgent(PlatformAgent):
    name = "revision"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        section_key = payload["section_key"]
        base_text = payload["base_text"]
        instruction = payload["instruction"]
        requirements = payload.get("requirements", [])
        evidence = payload.get("evidence", [])

        prompt = REVISION_PROMPT_TEMPLATE.format(
            section_label=section_key.replace("_", " ").title(),
            base_text=base_text,
            instruction=instruction,
            requirements="\n".join(f"- {r[:160]}" for r in requirements[:6]) or "- (none specified)",
            evidence=_short_evidence(evidence),
        )

        revised = ""
        summary = f"Applied user instruction to {section_key} via {self.llm.model}."
        confidence = 0.85
        try:
            revised = self.llm.generate(prompt=prompt, system=SYSTEM_PROMPT)
        except LLMServiceError as exc:
            summary = f"LLM unavailable ({exc}); kept original draft for {section_key}."
            confidence = 0.5

        if not revised.strip():
            revised = base_text
            if confidence == 0.85:
                summary = f"LLM returned empty output; kept original draft for {section_key}."
                confidence = 0.5

        output = {
            "section_key": section_key,
            "draft_text": revised,
            "revision_summary": summary,
            "changed_topics": [instruction],
            "preserved_constraints": requirements,
        }
        return AgentResult(self.name, output, f"Revised {section_key} section.", confidence)
