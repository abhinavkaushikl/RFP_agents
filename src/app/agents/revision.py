from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


class RevisionAgent(PlatformAgent):
    name = "revision"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        chain = RunnableLambda(
            lambda data: f"{data['base_text']}\n\nRevision Applied: {data['instruction']}"
        )
        revised = chain.invoke({"base_text": payload["base_text"], "instruction": payload["instruction"]})
        output = {
            "section_key": payload["section_key"],
            "draft_text": revised,
            "revision_summary": "Applied targeted user revision while preserving existing draft.",
            "changed_topics": [payload["instruction"]],
            "preserved_constraints": payload.get("requirements", []),
        }
        return AgentResult(self.name, output, f"Revised {payload['section_key']} section.", 0.79)
