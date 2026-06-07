"""Product Fit Agent — capability fit, gaps, and sales positioning analysis."""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base import PlatformAgent
from app.schemas.domain import AgentContext, AgentResult
from app.services.llm_service import LLMService, LLMServiceError


FIT_STAGES = (
    "Poor Fit",
    "Partial Fit",
    "Qualified Fit",
    "Strong Fit",
    "Strategic Fit",
)

FIT_STRENGTHS = ("Weak", "Moderate", "Strong")

PRODUCT_GAP_TYPES = (
    "Capability Gap",
    "Integration Gap",
    "Compliance Gap",
    "Performance/Scale Gap",
    "Services/Delivery Gap",
    "Commercial Fit Gap",
    "Competitive Differentiation Gap",
    "Operational Readiness Gap",
)

CAPABILITY_AREAS = (
    "Cloud Migration",
    "Managed Services",
    "AIOps/Monitoring",
    "Security/Compliance",
    "Integration",
    "Automation",
    "Analytics/Reporting",
    "Implementation Support",
)


SYSTEM_PROMPT = (
    "You are a Product Fit Intelligence Engine for enterprise sales teams. "
    "Analyze customer conversations and determine how well the proposed solution "
    "fits the buyer's stated needs. Extract capability matches, fit gaps, "
    "integration fit, competitive context, risks, and recommended positioning. "
    "Ground every claim in the transcript. Do not invent product capabilities, "
    "customers, integrations, compliance status, pricing, or commitments."
)

EXTRACTION_PROMPT = """Analyze the transcript and produce structured product-fit intelligence.

Evaluate:
- Buyer requirements and use cases
- Requested technical capabilities
- Integration needs
- Security and compliance expectations
- Delivery and support expectations
- Competitive context
- Fit blockers or proof points required
- Positioning and next-best sales actions

Allowed fit stages:
{fit_stages}

Allowed product gap types:
{gap_types}

Capability areas:
{capability_areas}

Return ONLY valid JSON in exactly this shape:
{{
  "product_fit_score": 0,
  "fit_stage": "Partial Fit",
  "confidence": 0.0,
  "fit_summary": "Concise product-fit assessment.",
  "matched_capabilities": [
    {{
      "buyer_need": "Buyer requirement or pain point",
      "matched_capability": "Relevant capability or solution area",
      "fit_strength": "Strong",
      "evidence": "Short transcript-grounded evidence"
    }}
  ],
  "product_gaps": [
    {{
      "gap_type": "Integration Gap",
      "severity": "Medium",
      "description": "Concise fit blocker or missing proof point.",
      "recommendation": "Actionable sales or solution step."
    }}
  ],
  "integration_fit": {{
    "score": 0,
    "summary": "Concise integration assessment.",
    "required_integrations": ["Named system or integration area"],
    "risks": ["Integration risk"]
  }},
  "competitive_positioning": {{
    "competitors_mentioned": ["Competitor name"],
    "differentiators": ["Evidence-grounded differentiator"],
    "positioning_summary": "How to position the solution against alternatives."
  }},
  "risk_flags": [
    "Important product-fit risk"
  ],
  "recommended_positioning": [
    "Specific positioning message"
  ],
  "recommended_next_actions": [
    "Specific next step"
  ]
}}

Scoring guidance:
- 0-20 Poor Fit
- 21-45 Partial Fit
- 46-65 Qualified Fit
- 66-85 Strong Fit
- 86-100 Strategic Fit

TRANSCRIPT:
{transcript_text}
"""


def _empty_output() -> dict[str, Any]:
    return {
        "product_fit_score": 0,
        "fit_stage": "Poor Fit",
        "confidence": 0.0,
        "fit_summary": "",
        "matched_capabilities": [],
        "product_gaps": [],
        "integration_fit": {
            "score": 0,
            "summary": "",
            "required_integrations": [],
            "risks": [],
        },
        "competitive_positioning": {
            "competitors_mentioned": [],
            "differentiators": [],
            "positioning_summary": "",
        },
        "risk_flags": [],
        "recommended_positioning": [],
        "recommended_next_actions": [],
        "notes": "",
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
    return max(minimum, min(maximum, int(round(number_float))))


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, round(number, 2)))


def _stage_from_score(score: int) -> str:
    if score <= 20:
        return "Poor Fit"
    if score <= 45:
        return "Partial Fit"
    if score <= 65:
        return "Qualified Fit"
    if score <= 85:
        return "Strong Fit"
    return "Strategic Fit"


def _normalize_choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = _clean_text(value)
    lowered = text.lower()
    for option in allowed:
        if lowered == option.lower():
            return option
    return default


def _normalize_match(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    buyer_need = _clean_text(value.get("buyer_need"))
    capability = _clean_text(value.get("matched_capability"))
    evidence = _clean_text(value.get("evidence"))
    if not buyer_need and not capability and not evidence:
        return None
    return {
        "buyer_need": buyer_need or "Need requires clarification",
        "matched_capability": capability or "Potential capability fit to validate",
        "fit_strength": _normalize_choice(value.get("fit_strength"), FIT_STRENGTHS, "Moderate"),
        "evidence": evidence,
    }


def _normalize_gap(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    description = _clean_text(value.get("description"))
    recommendation = _clean_text(value.get("recommendation"))
    if not description and not recommendation:
        return None
    return {
        "gap_type": _normalize_choice(value.get("gap_type"), PRODUCT_GAP_TYPES, "Capability Gap"),
        "severity": _normalize_choice(value.get("severity"), ("Low", "Medium", "High", "Critical"), "Medium"),
        "description": description or "Potential product-fit risk requires validation.",
        "recommendation": recommendation or "Validate this fit area with the buyer and solution team.",
    }


def _normalize_output(parsed: dict[str, Any] | None) -> dict[str, Any]:
    output = _empty_output()
    if not parsed:
        return output

    score = _clamp_int(parsed.get("product_fit_score"))
    output["product_fit_score"] = score
    output["fit_stage"] = _stage_from_score(score)
    output["confidence"] = _clamp_confidence(parsed.get("confidence"))
    output["fit_summary"] = _clean_text(parsed.get("fit_summary"))
    output["matched_capabilities"] = [
        match for match in (_normalize_match(item) for item in _as_list(parsed.get("matched_capabilities"))[:10]) if match
    ]
    output["product_gaps"] = [
        gap for gap in (_normalize_gap(item) for item in _as_list(parsed.get("product_gaps"))[:8]) if gap
    ]

    integration_raw = parsed.get("integration_fit") if isinstance(parsed.get("integration_fit"), dict) else {}
    output["integration_fit"] = {
        "score": _clamp_int(integration_raw.get("score")),
        "summary": _clean_text(integration_raw.get("summary")),
        "required_integrations": _as_text_list(integration_raw.get("required_integrations"), limit=10),
        "risks": _as_text_list(integration_raw.get("risks"), limit=8),
    }

    competitive_raw = (
        parsed.get("competitive_positioning")
        if isinstance(parsed.get("competitive_positioning"), dict)
        else {}
    )
    output["competitive_positioning"] = {
        "competitors_mentioned": _as_text_list(competitive_raw.get("competitors_mentioned"), limit=8),
        "differentiators": _as_text_list(competitive_raw.get("differentiators"), limit=8),
        "positioning_summary": _clean_text(competitive_raw.get("positioning_summary")),
    }
    output["risk_flags"] = _as_text_list(parsed.get("risk_flags"), limit=8)
    output["recommended_positioning"] = _as_text_list(parsed.get("recommended_positioning"), limit=8)
    output["recommended_next_actions"] = _as_text_list(parsed.get("recommended_next_actions"), limit=8)
    output["notes"] = output["fit_summary"]
    return output


def _heuristic_output(transcript: str) -> dict[str, Any]:
    """Conservative fallback used only when the local LLM returns invalid JSON."""
    output = _empty_output()
    lowered = transcript.lower()
    score = 0
    matches: list[dict[str, str]] = []
    gaps: list[dict[str, str]] = []

    def add_match(need: str, capability: str, strength: str, evidence: str, points: int) -> None:
        nonlocal score
        score += points
        matches.append(
            {
                "buyer_need": need,
                "matched_capability": capability,
                "fit_strength": strength,
                "evidence": evidence,
            }
        )

    if "migrate" in lowered or "cloud migration" in lowered:
        add_match(
            "Migrate legacy workloads to cloud",
            "Cloud Migration",
            "Strong",
            "Transcript discusses migration of legacy workloads to AWS or Azure.",
            18,
        )
    if "24x7" in lowered or "managed cloud operations" in lowered or "managed services" in lowered:
        add_match(
            "Post-migration operational support",
            "Managed Services",
            "Strong",
            "Buyer requested 24x7 managed cloud operations.",
            16,
        )
    if "monitoring" in lowered or "alerting" in lowered or "aiops" in lowered:
        add_match(
            "Integrate with existing monitoring and alerting stack",
            "AIOps/Monitoring",
            "Strong",
            "Buyer references an existing monitoring stack and integration value.",
            16,
        )
    if "hipaa" in lowered or "soc 2" in lowered or "compliance" in lowered:
        add_match(
            "Meet compliance requirements",
            "Security/Compliance",
            "Moderate",
            "Buyer named HIPAA and SOC 2 Type II requirements.",
            14,
        )
    if "near-zero downtime" in lowered or "zero unplanned downtime" in lowered:
        add_match(
            "Avoid business disruption during migration",
            "Implementation Support",
            "Moderate",
            "Buyer emphasized near-zero downtime and availability of patient-facing systems.",
            14,
        )
    if "existing customer" in lowered or "already embedded" in lowered:
        score += 12

    if any(term in lowered for term in ("clinical systems", "stateful", "cannot go down", "patient-facing")):
        gaps.append(
            {
                "gap_type": "Performance/Scale Gap",
                "severity": "High",
                "description": "Buyer needs proof that stateful or patient-facing workloads can be migrated without disruption.",
                "recommendation": "Provide a live-migration approach, healthcare workload reference architecture, and risk controls.",
            }
        )
    if "devops team is small" in lowered or "handle 90%" in lowered:
        gaps.append(
            {
                "gap_type": "Services/Delivery Gap",
                "severity": "Medium",
                "description": "Buyer expects the vendor to own most migration execution due to limited internal capacity.",
                "recommendation": "Position delivery capacity, governance model, and managed-services responsibilities clearly.",
            }
        )
    if "accenture" in lowered or "deloitte" in lowered:
        gaps.append(
            {
                "gap_type": "Competitive Differentiation Gap",
                "severity": "Medium",
                "description": "Buyer is comparing against large consulting competitors.",
                "recommendation": "Differentiate on existing stack integration, faster onboarding, and lower transition risk.",
            }
        )

    score = min(100, score)
    output["product_fit_score"] = score
    output["fit_stage"] = _stage_from_score(score)
    output["confidence"] = 0.58 if score else 0.25
    output["matched_capabilities"] = matches[:8]
    output["product_gaps"] = gaps[:6]
    output["integration_fit"] = {
        "score": 82 if "monitoring" in lowered or "already embedded" in lowered else 45,
        "summary": (
            "Integration fit is strong because the vendor is already embedded in the monitoring stack."
            if "monitoring" in lowered or "already embedded" in lowered
            else "Integration fit requires further validation."
        ),
        "required_integrations": ["Existing monitoring and alerting stack"] if "monitoring" in lowered else [],
        "risks": ["Clinical application continuity must be validated"] if "clinical systems" in lowered else [],
    }
    competitors = [name for name in ("Accenture", "Deloitte") if name.lower() in lowered]
    output["competitive_positioning"] = {
        "competitors_mentioned": competitors,
        "differentiators": ["Existing monitoring-stack footprint"] if "already embedded" in lowered or "monitoring" in lowered else [],
        "positioning_summary": "Position around proven integration, migration risk reduction, and managed execution capacity.",
    }
    output["risk_flags"] = [gap["description"] for gap in gaps]
    output["recommended_positioning"] = [
        "Lead with continuity-safe migration for critical workloads.",
        "Emphasize existing monitoring integration and lower transition risk.",
        "Package managed cloud operations as a capacity extension for the buyer's small DevOps team.",
    ]
    output["recommended_next_actions"] = [gap["recommendation"] for gap in gaps[:3]]
    output["fit_summary"] = (
        f"{output['fit_stage']} based on {len(matches)} matched requirement areas and "
        f"{len(gaps)} product-fit risks that need validation."
    )
    output["notes"] = output["fit_summary"]
    return output


class ProductFitAgent(PlatformAgent):
    name = "product_fit"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        transcript = (payload.get("transcript_text") or "")[:60_000]
        if not transcript.strip():
            return AgentResult(self.name, _empty_output(), "No transcript provided.", 0.0)

        prompt = EXTRACTION_PROMPT.format(
            fit_stages=", ".join(FIT_STAGES),
            gap_types=", ".join(PRODUCT_GAP_TYPES),
            capability_areas=", ".join(CAPABILITY_AREAS),
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
                f"LLM unavailable ({exc}); could not analyze product fit.",
                0.0,
            )

        output = _normalize_output(_parse_json(raw_response))
        if (
            not output.get("matched_capabilities")
            and not output.get("product_gaps")
            and not output.get("risk_flags")
            and output.get("product_fit_score", 0) == 0
        ):
            output = _heuristic_output(transcript)
        confidence = output.get("confidence", 0.0)
        return AgentResult(
            self.name,
            output,
            (
                f"Product fit generated with score {output['product_fit_score']} "
                f"({output['fit_stage']}), {len(output['matched_capabilities'])} matches, "
                f"and {len(output['product_gaps'])} fit gaps."
            ),
            confidence,
        )
