from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import PlatformAgent
from app.agents.utils import extract_requirements, infer_solution_type
from app.schemas.domain import AgentContext, AgentResult


class RequestStructuringAgent(PlatformAgent):
    name = "request_structuring"

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Structure proposal requests into normalized AIOps-friendly metadata."),
                ("human", "{request_text}"),
            ]
        )
        prompt.invoke({"request_text": payload["request_text"]})
        request_text = payload["request_text"]
        requirements = extract_requirements(request_text)
        vendors = [vendor for vendor in ["Nokia", "Huawei", "Ericsson"] if vendor.lower() in request_text.lower()]
        output = {
            "request_summary": request_text[:500],
            "requirements": requirements,
            "vendors": vendors,
            "solution_type": payload.get("solution_type") or infer_solution_type(request_text),
            "industry": payload.get("industry") or "Telecommunications",
            "ambiguity_flags": [] if requirements else ["missing_requirements"],
        }
        return AgentResult(self.name, output, "Structured request into normalized fields.", 0.82)
