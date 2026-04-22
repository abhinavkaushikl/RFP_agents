from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult


class PlannerAgent(PlatformAgent):
    name = "planner"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Plan the workflow and target sections for a proposal platform."),
                ("human", "{request_text}"),
            ]
        )
        prompt.invoke({"request_text": payload["request_text"]})
        request_text = payload["request_text"].lower()
        if payload.get("user_instruction"):
            workflow_type = "revision"
        elif payload.get("document_text"):
            workflow_type = "document_match"
        else:
            workflow_type = "proposal_generation"

        sections = payload.get("target_sections") or [
            "executive_summary",
            "solution_overview",
            "implementation_plan",
            "pricing_notes",
        ]
        if "executive summary" in request_text:
            sections = ["executive_summary"]
        output = {
            "workflow_type": workflow_type,
            "intent": workflow_type,
            "target_sections": sections,
            "revision_scope": payload.get("section_key"),
            "retrieval_hints": {"prefer_solution_type_filter": True, "section_first": True},
        }
        return AgentResult(self.name, output, f"Planned {workflow_type} workflow.", 0.85)
