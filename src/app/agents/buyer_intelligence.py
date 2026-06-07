"""Buyer Intelligence Agent — sales-readiness and stakeholder analysis."""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.services.llm_service import LLMService, LLMServiceError


READINESS_STAGES = (
    "Cold",
    "Exploring",
    "Interested",
    "Evaluation Stage",
    "High Intent",
    "Ready to Buy",
)

INTENT_TYPES = (
    "Purchase intent",
    "Information gathering",
    "Vendor comparison",
    "Objection handling",
    "Budget evaluation",
    "Technical validation",
    "Expansion opportunity",
    "Risk concerns",
)

GAP_TYPES = (
    "Budget Gap",
    "Technical Understanding Gap",
    "Stakeholder Alignment Gap",
    "ROI Clarity Gap",
    "Security/Compliance Concerns",
    "Timeline Misalignment",
    "Product Understanding Gap",
    "Integration Concerns",
)

STAKEHOLDER_CATEGORIES = (
    "Decision Maker",
    "Technical Evaluator",
    "Business Champion",
    "Procurement",
    "Security/Compliance",
    "End User",
    "Executive Sponsor",
)


SYSTEM_PROMPT = (
    "You are a Buyer Intelligence Engine for enterprise sales teams. "
    "Analyze customer conversations as an evidence-grounded sales strategist. "
    "Classify buyer intent, score purchase readiness, identify blockers, map "
    "stakeholders, and recommend next actions. Do not invent names, dates, roles, "
    "budget details, or commitments. Use concise reasoning bullets based only on "
    "the transcript. Do not reveal hidden chain-of-thought."
)

EXTRACTION_PROMPT = """Analyze the transcript and produce structured buyer intelligence.

Evaluation dimensions:
- Buying intent signals
- Urgency indicators
- Budget discussions
- Timeline mentions
- Technical validation interest
- Stakeholder engagement
- Competitor comparisons
- Procurement readiness
- Objection severity
- Commitment language

Before returning the JSON, internally verify that every claim is grounded in the transcript.
If evidence is incomplete, infer conservatively and lower confidence.

Allowed readiness stages:
{readiness_stages}

Allowed intent types:
{intent_types}

Allowed gap types:
{gap_types}

Stakeholder categories:
{stakeholder_categories}

Return ONLY valid JSON in exactly this shape:
{{
  "intent_classification": {{
    "primary_intent": "Purchase intent",
    "detected_intents": ["Purchase intent"],
    "summary": "One concise sentence describing buyer intent.",
    "confidence": 0.0
  }},
  "buyer_readiness_score": 0,
  "readiness_stage": "Cold",
  "confidence": 0.0,
  "reasoning": [
    "Short evidence-based reason"
  ],
  "buyer_gaps": [
    {{
      "gap_type": "ROI Clarity Gap",
      "severity": "Medium",
      "description": "Concise description of the blocker or risk.",
      "recommendation": "Actionable next step for the sales team."
    }}
  ],
  "stakeholder_coverage": {{
    "stakeholders": [
      {{
        "name": "Name if stated, otherwise Unknown",
        "role": "Role or title if stated",
        "category": "Decision Maker",
        "influence_level": "High",
        "engagement_quality": "Strong",
        "evidence": "Brief transcript-grounded evidence"
      }}
    ],
    "identified_roles": ["Technical Evaluator"],
    "missing_roles": ["Procurement"],
    "coverage_score": 0,
    "engagement_summary": "Concise summary of coverage quality and risk."
  }},
  "conversation_highlights": [
    "Important transcript signal"
  ],
  "recommended_next_actions": [
    "Specific action for sales team"
  ]
}}

Scoring guidance:
- 0-15 Cold
- 16-35 Exploring
- 36-55 Interested
- 56-70 Evaluation Stage
- 71-88 High Intent
- 89-100 Ready to Buy

TRANSCRIPT:
{transcript_text}
"""


def _empty_output() -> dict[str, Any]:
    return {
        "intent_classification": {
            "primary_intent": "Information gathering",
            "detected_intents": [],
            "summary": "",
            "confidence": 0.0,
        },
        "buyer_readiness_score": 0,
        "readiness_stage": "Cold",
        "confidence": 0.0,
        "reasoning": [],
        "buyer_gaps": [],
        "stakeholder_coverage": {
            "stakeholders": [],
            "identified_roles": [],
            "missing_roles": list(STAKEHOLDER_CATEGORIES),
            "coverage_score": 0,
            "engagement_summary": "",
        },
        "conversation_highlights": [],
        "recommended_next_actions": [],
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    candidate = (raw or "").strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.I).rstrip("`").strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return " ".join(str(value).split())


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _as_text_list(value: Any, limit: int = 8) -> list[str]:
    return [_clean_text(item) for item in _as_list(value)[:limit] if _clean_text(item)]


def _clamp_int(value: Any, minimum: int = 0, maximum: int = 100) -> int:
    try:
        number_float = float(value)
    except (TypeError, ValueError):
        return minimum
    if maximum == 100 and 0 < number_float <= 1:
        number_float *= 100
    number = int(round(number_float))
    return max(minimum, min(maximum, number))


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, round(number, 2)))


def _stage_from_score(score: int) -> str:
    if score <= 15:
        return "Cold"
    if score <= 35:
        return "Exploring"
    if score <= 55:
        return "Interested"
    if score <= 70:
        return "Evaluation Stage"
    if score <= 88:
        return "High Intent"
    return "Ready to Buy"


def _normalize_choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = _clean_text(value)
    lowered = text.lower()
    for option in allowed:
        if lowered == option.lower():
            return option
    return default


def _normalize_gap(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    gap_type = _normalize_choice(value.get("gap_type"), GAP_TYPES, "Stakeholder Alignment Gap")
    severity = _normalize_choice(value.get("severity"), ("Low", "Medium", "High", "Critical"), "Medium")
    description = _clean_text(value.get("description"))
    recommendation = _clean_text(value.get("recommendation"))
    if not description and not recommendation:
        return None
    return {
        "gap_type": gap_type,
        "severity": severity,
        "description": description or "Potential blocker requires follow-up discovery.",
        "recommendation": recommendation or "Clarify this area in the next buyer conversation.",
    }


def _normalize_stakeholder(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    name = _clean_text(value.get("name"), "Unknown") or "Unknown"
    role = _clean_text(value.get("role"), "Not stated") or "Not stated"
    category = _normalize_choice(value.get("category"), STAKEHOLDER_CATEGORIES, "Business Champion")
    influence = _normalize_choice(value.get("influence_level"), ("Low", "Medium", "High"), "Medium")
    engagement = _normalize_choice(
        value.get("engagement_quality"), ("Weak", "Moderate", "Strong"), "Moderate"
    )
    evidence = _clean_text(value.get("evidence"))
    return {
        "name": name,
        "role": role,
        "category": category,
        "influence_level": influence,
        "engagement_quality": engagement,
        "evidence": evidence,
    }


def _normalize_output(parsed: dict[str, Any] | None) -> dict[str, Any]:
    output = _empty_output()
    if not parsed:
        return output

    intent = parsed.get("intent_classification") if isinstance(parsed.get("intent_classification"), dict) else {}
    detected = [
        _normalize_choice(item, INTENT_TYPES, _clean_text(item))
        for item in _as_text_list(intent.get("detected_intents"), limit=8)
    ]
    detected = [item for item in detected if item]
    primary = _normalize_choice(intent.get("primary_intent"), INTENT_TYPES, detected[0] if detected else "Information gathering")
    output["intent_classification"] = {
        "primary_intent": primary,
        "detected_intents": detected,
        "summary": _clean_text(intent.get("summary")),
        "confidence": _clamp_confidence(intent.get("confidence")),
    }

    score = _clamp_int(parsed.get("buyer_readiness_score"))
    stage = _normalize_choice(parsed.get("readiness_stage"), READINESS_STAGES, _stage_from_score(score))
    output["buyer_readiness_score"] = score
    output["readiness_stage"] = stage
    output["confidence"] = _clamp_confidence(parsed.get("confidence"))
    output["reasoning"] = _as_text_list(parsed.get("reasoning"), limit=8)

    gaps = [_normalize_gap(item) for item in _as_list(parsed.get("buyer_gaps"))[:8]]
    output["buyer_gaps"] = [gap for gap in gaps if gap]

    coverage_raw = (
        parsed.get("stakeholder_coverage")
        if isinstance(parsed.get("stakeholder_coverage"), dict)
        else {}
    )
    stakeholders = [
        stakeholder
        for stakeholder in (
            _normalize_stakeholder(item) for item in _as_list(coverage_raw.get("stakeholders"))[:12]
        )
        if stakeholder
    ]
    identified_roles = [
        _normalize_choice(item, STAKEHOLDER_CATEGORIES, _clean_text(item))
        for item in _as_text_list(coverage_raw.get("identified_roles"), limit=12)
    ]
    if not identified_roles:
        identified_roles = sorted({item["category"] for item in stakeholders})
    missing_roles = [
        _normalize_choice(item, STAKEHOLDER_CATEGORIES, _clean_text(item))
        for item in _as_text_list(coverage_raw.get("missing_roles"), limit=12)
    ]
    if not missing_roles and identified_roles:
        missing_roles = [role for role in STAKEHOLDER_CATEGORIES if role not in identified_roles]
    output["stakeholder_coverage"] = {
        "stakeholders": stakeholders,
        "identified_roles": identified_roles,
        "missing_roles": missing_roles,
        "coverage_score": _clamp_int(coverage_raw.get("coverage_score")),
        "engagement_summary": _clean_text(coverage_raw.get("engagement_summary")),
    }
    output["conversation_highlights"] = _as_text_list(parsed.get("conversation_highlights"), limit=8)
    output["recommended_next_actions"] = _as_text_list(parsed.get("recommended_next_actions"), limit=8)
    return output


def _heuristic_output(transcript: str) -> dict[str, Any]:
    """Conservative fallback used only when the local LLM returns invalid JSON."""
    output = _empty_output()
    lowered = transcript.lower()
    score = 0
    reasoning: list[str] = []
    detected: list[str] = []

    if any(term in lowered for term in ("budget approved", "approved a $", "controls the budget", "commercials")):
        score += 20
        reasoning.append("Budget or commercial ownership was discussed.")
        detected.append("Budget evaluation")
    if any(term in lowered for term in ("deadline", "by q", "next quarter", "this quarter", "vendor selected")):
        score += 20
        reasoning.append("Timeline or deadline pressure is present.")
        detected.append("Purchase intent")
    if any(term in lowered for term in ("evaluating vendors", "also talking to", "competitor", "vendor")):
        score += 15
        reasoning.append("Buyer is comparing vendors or running an active evaluation.")
        detected.append("Vendor comparison")
    if any(term in lowered for term in ("technical evaluation", "migration", "deployment", "integrate", "validation")):
        score += 15
        reasoning.append("Technical validation or implementation detail was discussed.")
        detected.append("Technical validation")
    if any(term in lowered for term in ("cto", "cfo", "ciso", "executive sponsor", "procurement")):
        score += 15
        reasoning.append("Multiple buyer-side roles or decision stakeholders were mentioned.")
    if any(term in lowered for term in ("we are buying", "ready to buy", "submitted by", "proposal")):
        score += 15
        reasoning.append("The buyer used commitment language about proposal or purchase progression.")

    score = min(100, score)
    output["buyer_readiness_score"] = score
    output["readiness_stage"] = _stage_from_score(score)
    output["confidence"] = 0.55 if score else 0.25
    output["reasoning"] = reasoning[:6]
    detected = list(dict.fromkeys(detected))
    primary_intent = "Purchase intent" if "Purchase intent" in detected else detected[0] if detected else "Information gathering"
    output["intent_classification"] = {
        "primary_intent": primary_intent,
        "detected_intents": detected,
        "summary": "Buyer signals were inferred from explicit transcript keywords after JSON repair failed.",
        "confidence": 0.55 if detected else 0.25,
    }

    gaps: list[dict[str, str]] = []
    if any(term in lowered for term in ("downtime", "clinical systems", "stateful", "integrate")):
        gaps.append(
            {
                "gap_type": "Integration Concerns",
                "severity": "High",
                "description": "Buyer expressed concern around migration continuity or integration risk.",
                "recommendation": "Provide a technical validation session with migration approach, architecture, and proof points.",
            }
        )
    if "roi" not in lowered and "business impact" not in lowered:
        gaps.append(
            {
                "gap_type": "ROI Clarity Gap",
                "severity": "Medium",
                "description": "Quantified ROI framing is not clearly established in the transcript.",
                "recommendation": "Share quantified outcomes, savings model, and comparable customer results.",
            }
        )
    if "procurement" not in lowered:
        gaps.append(
            {
                "gap_type": "Stakeholder Alignment Gap",
                "severity": "Medium",
                "description": "Procurement involvement is not visible in the conversation.",
                "recommendation": "Confirm procurement process, approval path, and contracting timeline.",
            }
        )
    output["buyer_gaps"] = gaps[:5]

    identified_roles: list[str] = []
    if "cto" in lowered or "executive sponsor" in lowered:
        identified_roles.append("Executive Sponsor")
    if any(term in lowered for term in ("vp of technology", "technical evaluation", "devops")):
        identified_roles.append("Technical Evaluator")
    if "ciso" in lowered or "compliance" in lowered:
        identified_roles.append("Security/Compliance")
    if "cfo" in lowered or "budget" in lowered:
        identified_roles.append("Decision Maker")
    identified_roles = list(dict.fromkeys(identified_roles))
    missing_roles = [role for role in STAKEHOLDER_CATEGORIES if role not in identified_roles]
    output["stakeholder_coverage"] = {
        "stakeholders": [],
        "identified_roles": identified_roles,
        "missing_roles": missing_roles,
        "coverage_score": min(100, len(identified_roles) * 16),
        "engagement_summary": (
            "Stakeholder coverage was inferred from role mentions; validate named participants and missing personas."
            if identified_roles
            else "Stakeholder coverage could not be confidently determined."
        ),
    }
    output["conversation_highlights"] = reasoning[:4]
    output["recommended_next_actions"] = [
        gap["recommendation"] for gap in output["buyer_gaps"][:3]
    ]
    return output


class BuyerIntelligenceAgent(PlatformAgent):
    name = "buyer_intelligence"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        transcript = (payload.get("transcript_text") or "")[:60_000]
        if not transcript.strip():
            return AgentResult(self.name, _empty_output(), "No transcript provided.", 0.0)

        prompt = EXTRACTION_PROMPT.format(
            readiness_stages=", ".join(READINESS_STAGES),
            intent_types=", ".join(INTENT_TYPES),
            gap_types=", ".join(GAP_TYPES),
            stakeholder_categories=", ".join(STAKEHOLDER_CATEGORIES),
            transcript_text=transcript,
        )
        try:
            raw_response = self.llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=1600,
            )
        except LLMServiceError as exc:
            return AgentResult(
                self.name,
                _empty_output(),
                f"LLM unavailable ({exc}); could not analyze buyer intelligence.",
                0.0,
            )

        output = _normalize_output(_parse_json(raw_response))
        if (
            not output.get("reasoning")
            and not output.get("buyer_gaps")
            and not output.get("conversation_highlights")
            and output.get("buyer_readiness_score", 0) == 0
        ):
            output = _heuristic_output(transcript)
        confidence = output.get("confidence", 0.0)
        gap_count = len(output.get("buyer_gaps", []))
        stakeholder_count = len(output.get("stakeholder_coverage", {}).get("stakeholders", []))
        return AgentResult(
            self.name,
            output,
            (
                f"Buyer intelligence generated with score {output['buyer_readiness_score']} "
                f"({output['readiness_stage']}), {gap_count} gaps, and {stakeholder_count} stakeholders."
            ),
            confidence,
        )
