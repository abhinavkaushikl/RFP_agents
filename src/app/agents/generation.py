from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


class GenerationAgent(PlatformAgent):
    name = "generation"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Draft one grounded proposal section using the retrieved evidence."),
                (
                    "human",
                    "Section: {section_key}\nSummary: {request_summary}\nOfferings: {offerings}\nEvidence: {evidence_text}",
                ),
            ]
        )
        section = payload["section_key"]
        summary = payload["request_summary"]
        evidence = payload.get("evidence", [])
        offerings = payload.get("matching_offerings", [])
        evidence_lines = " ".join(item["content"] for item in evidence[:2])
        rendered = prompt.invoke(
            {
                "section_key": section,
                "request_summary": summary,
                "offerings": ", ".join(offerings[:3]),
                "evidence_text": evidence_lines[:400],
            }
        )
        text = f"{section.replace('_', ' ').title()}: {rendered.messages[-1].content}"
        output = {
            "section_key": section,
            "draft_text": text,
            "citations": [item["chunk_id"] for item in evidence[:3]],
            "generation_notes": [f"Generated {section} with grounded evidence."],
        }
        return AgentResult(self.name, output, f"Generated draft for {section}.", 0.74)
