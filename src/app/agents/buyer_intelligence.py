"""Buyer intelligence: readiness, intent, gaps, and stakeholder coverage (frontier model).

All categories (readiness stages, intent types, gap types, stakeholder
categories) come from the domain profile, so teams can adapt them to their
own sales methodology.
"""
from __future__ import annotations

from typing import Any

from app.agents.base import PlatformAgent
from app.agents.normalize import as_list, as_text_list, clamp_float, clamp_int, clean_text, normalize_choice
from app.agents.schema import NUM, STR, arr, enum, obj
from app.agents.transcript import transcript_messages
from app.domain.profile import DomainProfile, load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

SEVERITIES = ("Low", "Medium", "High", "Critical")
LEVELS = ("Low", "Medium", "High")
ENGAGEMENT = ("Weak", "Moderate", "Strong")


def _schema(p: DomainProfile) -> dict[str, Any]:
    bi = p.buyer_intelligence
    stages = [s.name for s in bi.readiness_stages]
    return obj(
        intent_classification=obj(
            primary_intent=enum(*bi.intent_types),
            detected_intents=arr(enum(*bi.intent_types)),
            summary=STR,
            confidence=NUM,
        ),
        buyer_readiness_score=NUM,
        readiness_stage=enum(*stages),
        confidence=NUM,
        reasoning=arr(STR),
        buyer_gaps=arr(
            obj(gap_type=enum(*bi.gap_types), severity=enum(*SEVERITIES), description=STR, recommendation=STR)
        ),
        stakeholder_coverage=obj(
            stakeholders=arr(
                obj(
                    name=STR,
                    role=STR,
                    category=enum(*bi.stakeholder_categories),
                    influence_level=enum(*LEVELS),
                    engagement_quality=enum(*ENGAGEMENT),
                    evidence=STR,
                )
            ),
            identified_roles=arr(enum(*bi.stakeholder_categories)),
            missing_roles=arr(enum(*bi.stakeholder_categories)),
            coverage_score=NUM,
            engagement_summary=STR,
        ),
        conversation_highlights=arr(STR),
        recommended_next_actions=arr(STR),
    )


def _task(p: DomainProfile) -> str:
    bi = p.buyer_intelligence
    bands = ", ".join(f"{s.name} ≤{s.max_score}" for s in sorted(bi.readiness_stages, key=lambda s: s.max_score))
    return (
        "Produce buyer intelligence for the sales team.\n"
        "Weigh: buying signals, urgency, budget discussion, timeline, technical validation, stakeholder "
        "engagement, competitor comparison, procurement readiness, objection severity, commitment language.\n"
        f"- buyer_readiness_score: 0-100. Stage bands: {bands}. readiness_stage must match the score.\n"
        "- confidence fields: 0-1.\n"
        "- buyer_gaps: blockers to a decision, each with a concrete recommendation.\n"
        "- stakeholders: only people or roles evidenced in the conversation; name \"Unknown\" when unnamed.\n"
        "- coverage_score: 0-100 for how well buying roles are covered.\n"
        "- reasoning, highlights, next actions: short evidence-based bullets (max 6 each).\n"
        "Return JSON only."
    )


def empty_output(p: DomainProfile) -> dict[str, Any]:
    bi = p.buyer_intelligence
    first_stage = sorted(bi.readiness_stages, key=lambda s: s.max_score)[0].name if bi.readiness_stages else ""
    return {
        "intent_classification": {
            "primary_intent": bi.intent_types[1] if len(bi.intent_types) > 1 else "",
            "detected_intents": [],
            "summary": "",
            "confidence": 0.0,
        },
        "buyer_readiness_score": 0,
        "readiness_stage": first_stage,
        "confidence": 0.0,
        "reasoning": [],
        "buyer_gaps": [],
        "stakeholder_coverage": {
            "stakeholders": [],
            "identified_roles": [],
            "missing_roles": list(bi.stakeholder_categories),
            "coverage_score": 0,
            "engagement_summary": "",
        },
        "conversation_highlights": [],
        "recommended_next_actions": [],
    }


def normalize_output(parsed: dict[str, Any] | None, p: DomainProfile) -> dict[str, Any]:
    bi = p.buyer_intelligence
    out = empty_output(p)
    if not parsed:
        return out
    intent = parsed.get("intent_classification") if isinstance(parsed.get("intent_classification"), dict) else {}
    detected = [normalize_choice(i, bi.intent_types, "") for i in as_text_list(intent.get("detected_intents"))]
    detected = [d for d in dict.fromkeys(detected) if d]
    out["intent_classification"] = {
        "primary_intent": normalize_choice(intent.get("primary_intent"), bi.intent_types,
                                           detected[0] if detected else out["intent_classification"]["primary_intent"]),
        "detected_intents": detected,
        "summary": clean_text(intent.get("summary")),
        "confidence": clamp_float(intent.get("confidence")),
    }
    score = clamp_int(parsed.get("buyer_readiness_score"))
    out["buyer_readiness_score"] = score
    out["readiness_stage"] = p.stage_for_score(bi.readiness_stages, score)
    out["confidence"] = clamp_float(parsed.get("confidence"))
    out["reasoning"] = as_text_list(parsed.get("reasoning"))

    gaps = []
    for g in as_list(parsed.get("buyer_gaps"))[:8]:
        if not isinstance(g, dict):
            continue
        desc, rec = clean_text(g.get("description")), clean_text(g.get("recommendation"))
        if not desc and not rec:
            continue
        gaps.append(
            {
                "gap_type": normalize_choice(g.get("gap_type"), bi.gap_types, bi.gap_types[0] if bi.gap_types else "Gap"),
                "severity": normalize_choice(g.get("severity"), SEVERITIES, "Medium"),
                "description": desc or "Potential blocker requires follow-up discovery.",
                "recommendation": rec or "Clarify this area in the next buyer conversation.",
            }
        )
    out["buyer_gaps"] = gaps

    cov = parsed.get("stakeholder_coverage") if isinstance(parsed.get("stakeholder_coverage"), dict) else {}
    default_category = bi.stakeholder_categories[0] if bi.stakeholder_categories else "Stakeholder"
    stakeholders = []
    for s in as_list(cov.get("stakeholders"))[:12]:
        if not isinstance(s, dict):
            continue
        stakeholders.append(
            {
                "name": clean_text(s.get("name"), "Unknown") or "Unknown",
                "role": clean_text(s.get("role"), "Not stated") or "Not stated",
                "category": normalize_choice(s.get("category"), bi.stakeholder_categories, default_category),
                "influence_level": normalize_choice(s.get("influence_level"), LEVELS, "Medium"),
                "engagement_quality": normalize_choice(s.get("engagement_quality"), ENGAGEMENT, "Moderate"),
                "evidence": clean_text(s.get("evidence")),
            }
        )
    identified = [normalize_choice(r, bi.stakeholder_categories, "") for r in as_text_list(cov.get("identified_roles"), 12)]
    identified = [r for r in dict.fromkeys(identified) if r] or sorted({s["category"] for s in stakeholders})
    missing = [normalize_choice(r, bi.stakeholder_categories, "") for r in as_text_list(cov.get("missing_roles"), 12)]
    missing = [r for r in dict.fromkeys(missing) if r] or [r for r in bi.stakeholder_categories if r not in identified]
    out["stakeholder_coverage"] = {
        "stakeholders": stakeholders,
        "identified_roles": identified,
        "missing_roles": missing,
        "coverage_score": clamp_int(cov.get("coverage_score")),
        "engagement_summary": clean_text(cov.get("engagement_summary")),
    }
    out["conversation_highlights"] = as_text_list(parsed.get("conversation_highlights"))
    out["recommended_next_actions"] = as_text_list(parsed.get("recommended_next_actions"))
    return out


def heuristic_output(transcript: str, p: DomainProfile) -> dict[str, Any]:
    """Keyword-based estimate, used only in degraded mode."""
    out = empty_output(p)
    lowered = transcript.lower()
    signals = [
        (("budget", "approved", "commercials", "pricing"), 20, "Budget or commercials were discussed."),
        (("deadline", "this quarter", "next quarter", "by q", "go-live", "timeline"), 20, "A timeline or deadline was mentioned."),
        (("evaluating", "also talking to", "competitor", "shortlist", "vendors"), 15, "The buyer is comparing options."),
        (("technical", "integration", "integrate", "migration", "proof of concept", "pilot"), 15, "Technical validation was discussed."),
        (("cfo", "cto", "cio", "ciso", "procurement", "executive sponsor", "board"), 15, "Decision-level roles were mentioned."),
        (("proposal", "contract", "ready to", "next steps", "sign"), 15, "Commitment language appeared."),
    ]
    score, reasoning = 0, []
    for terms, points, reason in signals:
        if any(t in lowered for t in terms):
            score += points
            reasoning.append(reason)
    score = min(100, score)
    out["buyer_readiness_score"] = score
    out["readiness_stage"] = p.stage_for_score(p.buyer_intelligence.readiness_stages, score)
    out["confidence"] = 0.3
    out["reasoning"] = reasoning
    out["conversation_highlights"] = reasoning[:4]
    out["intent_classification"]["summary"] = "Estimated from keywords because the model was unavailable."
    return out


class BuyerIntelligenceAgent(PlatformAgent):
    name = "buyer_intelligence"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        transcript = payload.get("transcript_text") or ""
        if not transcript.strip():
            return AgentResult(self.name, empty_output(profile), "No transcript provided.", 0.0)
        try:
            parsed = self.llm.complete_json(
                agent=self.name,
                messages=transcript_messages(transcript, _task(profile)),
                schema=_schema(profile),
                schema_name="buyer_intelligence",
                purpose="analyze_buyer_intelligence",
                max_tokens=5000,
                expected_tokens=1500,
            ).parsed
            output = normalize_output(parsed, profile)
            mode = "llm"
        except LLMServiceError:
            if not self.llm.degraded_allowed:
                raise
            output = heuristic_output(transcript, profile)
            mode = "heuristic"
        output["mode"] = mode
        return AgentResult(
            self.name,
            output,
            f"Readiness {output['buyer_readiness_score']} ({output['readiness_stage']}), "
            f"{len(output['buyer_gaps'])} gaps, {len(output['stakeholder_coverage']['stakeholders'])} stakeholders ({mode}).",
            output.get("confidence", 0.0),
        )
