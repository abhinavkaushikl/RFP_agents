from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.prompts import SYSTEM_PROMPT, SectionPromptContext, build_section_prompt
from app.schemas.domain import AgentContext, AgentResult
from app.services.llm_service import LLMService, LLMServiceError


class GenerationAgent(PlatformAgent):
    name = "generation"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        section = payload["section_key"]
        evidence = payload.get("evidence", [])
        offerings = payload.get("matching_offerings", [])

        if payload.get("fast_mode"):
            draft_text = self._fast_draft(
                section=section,
                client_name=payload.get("client_name", "the client"),
                industry=payload.get("industry", "Telecommunications"),
                request_summary=payload.get("request_summary", ""),
                requirements=payload.get("requirements", []),
                offerings=offerings,
                evidence=evidence,
            )
            return AgentResult(
                self.name,
                {
                    "section_key": section,
                    "draft_text": draft_text,
                    "citations": [item.get("chunk_id", item.get("id", "")) for item in evidence[:3]],
                    "generation_notes": [
                        f"Generated {section} with fast deterministic draft mode using {len(evidence)} retrieved chunks."
                    ],
                },
                f"Generated {section} fast draft ({len(draft_text)} chars).",
                0.72,
            )

        ctx = SectionPromptContext(
            section_key=section,
            client_name=payload.get("client_name", "the client"),
            industry=payload.get("industry", "Telecommunications"),
            request_summary=payload.get("request_summary", ""),
            requirements=payload.get("requirements", []),
            vendors=payload.get("vendors", []),
            offerings=offerings,
            evidence_chunks=[item.get("content", "") for item in evidence[:2]],
            solution_type=payload.get("solution_type", "aiops_general"),
        )

        prompt = build_section_prompt(section, ctx)

        notes: list[str] = []
        draft_text = ""
        try:
            draft_text = self.llm.generate(prompt=prompt, system=SYSTEM_PROMPT)
        except LLMServiceError as exc:
            notes.append(f"LLM call failed for {section}: {exc}. Falling back to deterministic draft.")

        if not draft_text.strip():
            draft_text = self._fast_draft(
                section=section,
                client_name=payload.get("client_name", "the client"),
                industry=payload.get("industry", "Telecommunications"),
                request_summary=payload.get("request_summary", ""),
                requirements=payload.get("requirements", []),
                offerings=offerings,
                evidence=evidence,
            )
            notes.append(f"Used deterministic fallback for {section}.")
            confidence = 0.6
        else:
            notes.append(
                f"Generated {section} via {self.llm.model} using {len(evidence)} retrieved chunks."
            )
            confidence = 0.85

        output = {
            "section_key": section,
            "draft_text": draft_text,
            "citations": [item.get("chunk_id", item.get("id", "")) for item in evidence[:3]],
            "generation_notes": notes,
        }
        return AgentResult(
            self.name,
            output,
            f"Generated {section} draft ({len(draft_text)} chars).",
            confidence,
        )

    def _fast_draft(
        self,
        *,
        section: str,
        client_name: str,
        industry: str,
        request_summary: str,
        requirements: list[str],
        offerings: list[str],
        evidence: list[dict],
    ) -> str:
        section_title = section.replace("_", " ").title()
        top_requirements = requirements[:5] or [request_summary[:220] or "Address the stated RFP priorities."]
        top_offerings = offerings[:4] or ["platform integration", "analytics", "managed operations"]
        evidence_points = [
            item.get("content", "").strip()
            for item in evidence[:2]
            if item.get("content", "").strip()
        ]

        lines = [
            section_title,
            "",
            "Strategic Context",
            (
                f"{client_name} is evaluating a {industry} proposal that requires a practical, evidence-led "
                "response. The proposed approach focuses on measurable operational improvement, delivery "
                "clarity, and reuse of relevant historical proposal evidence."
            ),
            "",
            "Requirements",
        ]
        lines.extend(f"{index}. {item}" for index, item in enumerate(top_requirements, 1))
        lines.extend(["", "Relevant Offerings"])
        lines.extend(f"- {item}" for item in top_offerings)
        lines.extend(
            [
                "",
                "Recommended Response",
                (
                    f"Our response for {client_name} should position the solution around the selected offerings, "
                    "connect each requirement to an implementation action, and keep the proposal grounded in "
                    "retrieved precedent."
                ),
            ]
        )
        if evidence_points:
            lines.extend(["", "Retrieved Evidence Used"])
            lines.extend(f"- {point[:260]}" for point in evidence_points)
        lines.extend(
            [
                "",
                "Next Steps",
                "1. Confirm scope, stakeholders, and expected timeline.",
                "2. Validate integrations, operational constraints, and success metrics.",
                "3. Finalize the implementation plan and commercial assumptions.",
            ]
        )
        return "\n".join(lines)
