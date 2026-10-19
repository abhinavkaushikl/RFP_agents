"""Problem framing: the business problem behind a conversation (fast model)."""
from __future__ import annotations

from app.agents.base import PlatformAgent
from app.agents.normalize import clean_text
from app.agents.schema import STR, obj
from app.agents.transcript import transcript_messages
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

FIELD_KEYS = ("problem_statement", "success_definition", "stakeholder_impact", "urgency_statement")
NOT_STATED = "Not explicitly stated."

_SCHEMA = obj(**{key: STR for key in FIELD_KEYS})

_TASK = (
    "Frame the buyer's business problem in concise, executive-level language:\n"
    "- problem_statement: the core problem or pain, rewritten crisply without noise.\n"
    "- success_definition: measurable or observable success criteria.\n"
    "- stakeholder_impact: who is affected and how.\n"
    "- urgency_statement: why it must happen now and the risk of delay.\n"
    f"Use \"{NOT_STATED}\" for any field the conversation does not support. Return JSON only."
)


class ProblemFramingAgent(PlatformAgent):
    name = "problem_framing"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        transcript = payload.get("transcript_text") or ""
        empty = {key: "" for key in FIELD_KEYS}
        if not transcript.strip():
            return AgentResult(self.name, empty, "No transcript provided.", 0.0)
        try:
            parsed = self.llm.complete_json(
                agent=self.name,
                messages=transcript_messages(transcript, _TASK),
                schema=_SCHEMA,
                schema_name="problem_framing",
                purpose="frame_business_problem",
                max_tokens=1500,
                expected_tokens=400,
            ).parsed
        except LLMServiceError as exc:
            if not self.llm.degraded_allowed:
                raise
            return AgentResult(self.name, empty, f"Model unavailable ({exc}); problem framing skipped.", 0.0)
        fields = {key: clean_text(parsed.get(key)) for key in FIELD_KEYS}
        filled = sum(1 for v in fields.values() if v and v != NOT_STATED)
        return AgentResult(self.name, fields, f"Framed {filled}/4 problem fields.", filled / 4)
