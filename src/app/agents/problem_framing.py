"""Problem Framing Agent — LLM-powered extraction of problem context from transcripts.

Extracts:
- problem_statement: what pain or challenge the client is describing
- success_definition: what "done well" looks like for the client
- stakeholder_impact: who is affected and how
- urgency_statement: why this needs to happen now / timeline pressure
"""
from __future__ import annotations

import json
import re

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.services.llm_service import LLMService, LLMServiceError


FIELD_KEYS = (
    "problem_statement",
    "success_definition",
    "stakeholder_impact",
    "urgency_statement",
)

SYSTEM_PROMPT = (
    "You are an intelligent AI Intent Detection and Problem Framing Agent. "
    "Extract the core business intent, hidden objective, operational pain point, "
    "and expected business outcome from business documents, requirements, emails, "
    "meeting notes, ticket descriptions, or opportunity statements. Use concise, "
    "executive-level language. Infer conservatively from evidence when a field is "
    "partial, but do not invent unsupported stakeholders, dates, metrics, or risks."
)

EXTRACTION_PROMPT = """Read the complete input document carefully and extract the four fields below.

Requirements:
- Rewrite the business problem in crisp, professional enterprise language.
- Remove noise, duplication, and irrelevant context.
- Preserve the original business meaning and intent.
- Focus on business intent rather than technical jargon unless explicitly mentioned.
- If a section is partially missing, infer the most probable interpretation from the document evidence.
- Keep every field short, decision-ready, and suitable for executive review.

Return ONLY valid JSON in exactly this shape:
{{
  "problem_statement": "Clearly rewritten business problem statement",
  "success_definition": "Measurable or observable success criteria for solving the problem",
  "stakeholder_impact": "Who is impacted and how the problem affects business/users/operations",
  "urgency_statement": "Why the issue needs immediate attention and the business risk of delay"
}}

If a field cannot be determined or reasonably inferred from the document, use "Not explicitly stated."

DOCUMENT:
{transcript_text}
"""


def _parse_response(text: str) -> dict[str, str]:
    """Parse JSON first, with a lenient section fallback for local models."""
    fields = {key: "" for key in FIELD_KEYS}
    candidate = (text or "").strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.I).rstrip("`").strip()

    for opener, closer in (("{", "}"),):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start >= 0 and end > start:
            try:
                parsed = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                for key in FIELD_KEYS:
                    value = parsed.get(key)
                    if value is None:
                        continue
                    if isinstance(value, str):
                        fields[key] = " ".join(value.split())
                    else:
                        fields[key] = " ".join(json.dumps(value, ensure_ascii=False).split())
                return fields

    current_key = None
    buffer: list[str] = []

    key_map = {
        "PROBLEM STATEMENT:": "problem_statement",
        "PROBLEM_STATEMENT:": "problem_statement",
        "SUCCESS DEFINITION:": "success_definition",
        "SUCCESS_DEFINITION:": "success_definition",
        "STAKEHOLDER IMPACT:": "stakeholder_impact",
        "STAKEHOLDER_IMPACT:": "stakeholder_impact",
        "URGENCY STATEMENT:": "urgency_statement",
        "URGENCY_STATEMENT:": "urgency_statement",
    }

    for line in text.splitlines():
        stripped = line.strip()
        matched = False
        for marker, key in key_map.items():
            if stripped.upper().startswith(marker.rstrip(":")):
                if current_key and buffer:
                    fields[current_key] = " ".join(buffer).strip()
                current_key = key
                after = stripped[len(marker):].strip() if stripped.upper().startswith(marker) else ""
                buffer = [after] if after else []
                matched = True
                break
        if not matched and current_key:
            if stripped:
                buffer.append(stripped)

    if current_key and buffer:
        fields[current_key] = " ".join(buffer).strip()

    return {key: " ".join(value.split()) for key, value in fields.items()}


class ProblemFramingAgent(PlatformAgent):
    name = "problem_framing"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        transcript = (payload.get("transcript_text") or "")[:60_000]

        if not transcript.strip():
            empty = {
                "problem_statement": "",
                "success_definition": "",
                "stakeholder_impact": "",
                "urgency_statement": "",
            }
            return AgentResult(self.name, empty, "No transcript provided.", 0.0)

        prompt = EXTRACTION_PROMPT.format(transcript_text=transcript)

        try:
            raw_response = self.llm.generate(prompt=prompt, system=SYSTEM_PROMPT)
        except LLMServiceError as exc:
            empty = {
                "problem_statement": "",
                "success_definition": "",
                "stakeholder_impact": "",
                "urgency_statement": "",
            }
            return AgentResult(
                self.name, empty, f"LLM unavailable ({exc}); could not extract problem framing.", 0.0
            )

        fields = _parse_response(raw_response)
        filled = sum(1 for v in fields.values() if v and v != "Not explicitly stated.")
        confidence = filled / 4

        return AgentResult(
            self.name,
            fields,
            f"Extracted {filled}/4 problem framing fields from transcript.",
            confidence,
        )
