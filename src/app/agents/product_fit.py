"""Product fit: how well our offerings fit what the buyer described (frontier model).

The fit is judged against the profile's offering catalog when one exists, and
against the solution discussed in the conversation otherwise. Capability areas
and gap types come from the profile.
"""
from __future__ import annotations

import re
from typing import Any

from app.agents.base import PlatformAgent
from app.agents.normalize import as_list, as_text_list, clamp_float, clamp_int, clean_text, normalize_choice
from app.agents.schema import NUM, STR, arr, enum, obj
from app.agents.transcript import transcript_messages
from app.domain.profile import DomainProfile, load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

STRENGTHS = ("Weak", "Moderate", "Strong")
SEVERITIES = ("Low", "Medium", "High", "Critical")
_WORD = re.compile(r"[a-z0-9]+")


def _schema(p: DomainProfile) -> dict[str, Any]:
    pf = p.product_fit
    return obj(
        product_fit_score=NUM,
        fit_stage=enum(*[s.name for s in pf.fit_stages]),
        confidence=NUM,
        fit_summary=STR,
        matched_capabilities=arr(
            obj(
                buyer_need=STR,
                matched_capability=STR,
                capability_area=enum(*pf.capability_areas),
                fit_strength=enum(*STRENGTHS),
                evidence=STR,
            )
        ),
        product_gaps=arr(obj(gap_type=enum(*pf.gap_types), severity=enum(*SEVERITIES), description=STR, recommendation=STR)),
        integration_fit=obj(score=NUM, summary=STR, required_integrations=arr(STR), risks=arr(STR)),
        competitive_positioning=obj(competitors_mentioned=arr(STR), differentiators=arr(STR), positioning_summary=STR),
        risk_flags=arr(STR),
        recommended_positioning=arr(STR),
        recommended_next_actions=arr(STR),
    )


def _task(p: DomainProfile) -> str:
    pf = p.product_fit
    bands = ", ".join(f"{s.name} ≤{s.max_score}" for s in sorted(pf.fit_stages, key=lambda s: s.max_score))
    if p.offerings:
        basis = f"Judge fit against {p.organization.name}'s offering catalog:\n{p.catalog_text()}\n"
    else:
        basis = "No offering catalog is configured; judge fit against the solution discussed in the conversation.\n"
    competitors = ", ".join(p.lexicons.competitors)
    return (
        "Assess product fit for the sales team.\n"
        + basis
        + "Evaluate buyer needs and use cases, requested capabilities, integration needs, security and "
        "compliance expectations, delivery and support expectations, competitive context, and proof points needed.\n"
        f"- product_fit_score: 0-100. Stage bands: {bands}. fit_stage must match the score.\n"
        "- Never claim a capability, integration, certification, or customer that is not in the catalog or conversation.\n"
        + (f"- Known competitors to watch for: {competitors}.\n" if competitors else "")
        + "- integration_fit.score: 0-100. confidence: 0-1. Lists: max 6 short items.\n"
        "Return JSON only."
    )


def empty_output(p: DomainProfile) -> dict[str, Any]:
    stages = sorted(p.product_fit.fit_stages, key=lambda s: s.max_score)
    return {
        "product_fit_score": 0,
        "fit_stage": stages[0].name if stages else "",
        "confidence": 0.0,
        "fit_summary": "",
        "matched_capabilities": [],
        "product_gaps": [],
        "integration_fit": {"score": 0, "summary": "", "required_integrations": [], "risks": []},
        "competitive_positioning": {"competitors_mentioned": [], "differentiators": [], "positioning_summary": ""},
        "risk_flags": [],
        "recommended_positioning": [],
        "recommended_next_actions": [],
        "notes": "",
    }


def normalize_output(parsed: dict[str, Any] | None, p: DomainProfile) -> dict[str, Any]:
    pf = p.product_fit
    out = empty_output(p)
    if not parsed:
        return out
    score = clamp_int(parsed.get("product_fit_score"))
    out["product_fit_score"] = score
    out["fit_stage"] = p.stage_for_score(pf.fit_stages, score)
    out["confidence"] = clamp_float(parsed.get("confidence"))
    out["fit_summary"] = clean_text(parsed.get("fit_summary"))
    area_default = pf.capability_areas[0] if pf.capability_areas else ""
    matches = []
    for m in as_list(parsed.get("matched_capabilities"))[:10]:
        if not isinstance(m, dict):
            continue
        need, cap = clean_text(m.get("buyer_need")), clean_text(m.get("matched_capability"))
        if not need and not cap:
            continue
        matches.append(
            {
                "buyer_need": need or "Need requires clarification",
                "matched_capability": cap or "Potential fit to validate",
                "capability_area": normalize_choice(m.get("capability_area"), pf.capability_areas, area_default),
                "fit_strength": normalize_choice(m.get("fit_strength"), STRENGTHS, "Moderate"),
                "evidence": clean_text(m.get("evidence")),
            }
        )
    out["matched_capabilities"] = matches
    gaps = []
    for g in as_list(parsed.get("product_gaps"))[:8]:
        if not isinstance(g, dict):
            continue
        desc, rec = clean_text(g.get("description")), clean_text(g.get("recommendation"))
        if not desc and not rec:
            continue
        gaps.append(
            {
                "gap_type": normalize_choice(g.get("gap_type"), pf.gap_types, pf.gap_types[0] if pf.gap_types else "Gap"),
                "severity": normalize_choice(g.get("severity"), SEVERITIES, "Medium"),
                "description": desc or "Potential fit risk requires validation.",
                "recommendation": rec or "Validate this area with the buyer and solution team.",
            }
        )
    out["product_gaps"] = gaps
    integ = parsed.get("integration_fit") if isinstance(parsed.get("integration_fit"), dict) else {}
    out["integration_fit"] = {
        "score": clamp_int(integ.get("score")),
        "summary": clean_text(integ.get("summary")),
        "required_integrations": as_text_list(integ.get("required_integrations"), 10),
        "risks": as_text_list(integ.get("risks")),
    }
    comp = parsed.get("competitive_positioning") if isinstance(parsed.get("competitive_positioning"), dict) else {}
    out["competitive_positioning"] = {
        "competitors_mentioned": as_text_list(comp.get("competitors_mentioned")),
        "differentiators": as_text_list(comp.get("differentiators")),
        "positioning_summary": clean_text(comp.get("positioning_summary")),
    }
    out["risk_flags"] = as_text_list(parsed.get("risk_flags"))
    out["recommended_positioning"] = as_text_list(parsed.get("recommended_positioning"))
    out["recommended_next_actions"] = as_text_list(parsed.get("recommended_next_actions"))
    out["notes"] = out["fit_summary"]
    return out


def heuristic_output(transcript: str, p: DomainProfile) -> dict[str, Any]:
    """Keyword overlap with the offering catalog; used only in degraded mode."""
    out = empty_output(p)
    words = set(_WORD.findall(transcript.lower()))
    matches = []
    for off in p.offerings:
        vocab = {w for term in [*off.keywords, *off.capabilities] for w in _WORD.findall(term.lower()) if len(w) > 3}
        hits = sorted(words & vocab)
        if hits:
            matches.append(
                {
                    "buyer_need": "Mentioned: " + ", ".join(hits[:5]),
                    "matched_capability": off.name,
                    "capability_area": p.product_fit.capability_areas[0] if p.product_fit.capability_areas else "",
                    "fit_strength": "Strong" if len(hits) >= 3 else "Moderate",
                    "evidence": "Keyword overlap with the offering catalog.",
                }
            )
    score = min(100, 20 * len(matches))
    competitors = [c for c in p.lexicons.competitors if c.lower() in transcript.lower()]
    out.update(
        product_fit_score=score,
        fit_stage=p.stage_for_score(p.product_fit.fit_stages, score),
        confidence=0.3,
        matched_capabilities=matches,
        fit_summary="Estimated from keyword overlap because the model was unavailable.",
    )
    out["competitive_positioning"]["competitors_mentioned"] = competitors
    out["notes"] = out["fit_summary"]
    return out


class ProductFitAgent(PlatformAgent):
    name = "product_fit"

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
                schema_name="product_fit",
                purpose="analyze_product_fit",
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
            f"Fit {output['product_fit_score']} ({output['fit_stage']}), {len(output['matched_capabilities'])} matches, "
            f"{len(output['product_gaps'])} gaps ({mode}).",
            output.get("confidence", 0.0),
        )
