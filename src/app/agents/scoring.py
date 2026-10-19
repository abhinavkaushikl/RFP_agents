"""Scoring: composite quality of a proposal (generated or uploaded).

Components (each 0-1, or None when it cannot be measured for this run):
- requirement_coverage: share of requirements the document addresses (semantic match)
- historical_similarity: mean similarity of the precedent actually retrieved
- solution_fit: share of requirements our offerings cover (from solution comparison)
- completeness: requested sections present and within their word ranges
- quality: model rubric against the evaluation criteria (frontier model)

The composite is a weighted mean over the components that exist, using the
profile's `scoring.weights`.
"""
from __future__ import annotations

from typing import Any

from app.agents.base import PlatformAgent
from app.agents.normalize import as_text_list, clamp_float, clean_text
from app.agents.schema import NUM, STR, arr, obj
from app.core.config import get_settings
from app.domain.profile import DomainProfile, load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult
from app.services.coverage import CoverageAnalyzer

MAX_DOC_CHARS = 40_000

_RUBRIC_SCHEMA = obj(
    overall_score=NUM,
    criteria=arr(obj(criterion=STR, score=NUM, comment=STR)),
    strengths=arr(STR),
    weaknesses=arr(STR),
    recommendations=arr(STR),
)

_RUBRIC_SYSTEM = (
    "You are a strict RFP evaluator. Score the response against each evaluation criterion from 0 to 10, "
    "where 10 means fully convincing and evidenced, 5 means adequate but generic, and 0 means absent. "
    "Penalize unsupported claims, missing requirements, and vague commitments. overall_score is 0-10. "
    "Keep comments to one sentence. Return JSON only."
)


def _completeness(sections: list[dict], targets: list[str], profile: DomainProfile) -> float | None:
    if not targets:
        return None
    by_key = {s.get("section_key"): s for s in sections}
    total = 0.0
    for key in targets:
        sec = by_key.get(profile.canonical_section_key(key)) or by_key.get(key)
        if not sec or not (sec.get("draft_text") or "").strip() or sec.get("error"):
            continue
        low, high = profile.section(key).words
        words = len((sec.get("draft_text") or "").split())
        total += 1.0 if 0.7 * low <= words <= 1.3 * high else 0.6
    return round(total / len(targets), 3)


def _composite(components: dict[str, float | None], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    used = {k: weights.get(k, 0.0) for k, v in components.items() if v is not None and weights.get(k, 0.0) > 0}
    total_weight = sum(used.values())
    if not total_weight:
        return 0.0, {}
    score = sum(components[k] * w for k, w in used.items()) / total_weight
    return round(score, 3), {k: round(w / total_weight, 3) for k, w in used.items()}


class ScoringAgent(PlatformAgent):
    name = "scoring"

    def __init__(self, llm_service: LLMService | None = None, coverage: CoverageAnalyzer | None = None) -> None:
        self.llm = llm_service
        self.coverage = coverage or CoverageAnalyzer()

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        document = payload.get("document_text") or ""
        requirements = payload.get("requirements") or []
        criteria = payload.get("evaluation_criteria") or profile.scoring.default_evaluation_criteria

        coverage = self.coverage.analyze(requirements, document)
        retrieval_scores = [float(s) for s in payload.get("retrieval_scores") or [] if s is not None]
        similarity = round(sum(retrieval_scores) / len(retrieval_scores), 3) if retrieval_scores else None
        fit = payload.get("solution_fit_score")
        completeness = _completeness(payload.get("sections") or [], payload.get("target_sections") or [], profile)

        rubric: dict[str, Any] | None = None
        if self.llm is not None and get_settings().scoring_llm_rubric and document.strip():
            rubric = self._rubric(document, requirements, criteria)
        quality = round(rubric["overall_score"] / 10, 3) if rubric else None

        components = {
            "requirement_coverage": coverage["coverage_score"],
            "historical_similarity": similarity,
            "solution_fit": clamp_float(fit) if fit is not None else None,
            "completeness": completeness,
            "quality": quality,
        }
        composite, weights_used = _composite(components, profile.scoring.weights)
        output = {
            "requirement_coverage_score": components["requirement_coverage"],
            "historical_similarity_score": components["historical_similarity"],
            "solution_fit_score": components["solution_fit"],
            "completeness_score": components["completeness"],
            "quality_score": components["quality"],
            "composite_score": composite,
            "weights_used": weights_used,
            "coverage_details": coverage["details"],
            "missing_requirements": coverage["missing_items"],
            "rubric": rubric,
            "matched_evidence": payload.get("matched_evidence", []),
        }
        measured = ", ".join(k for k in weights_used) or "nothing measurable"
        return AgentResult(self.name, output, f"Composite {composite:.2f} from {measured}.", 0.8)

    def _rubric(self, document: str, requirements: list[str], criteria: list[str]) -> dict[str, Any] | None:
        prompt = (
            "EVALUATION CRITERIA:\n" + "\n".join(f"- {c}" for c in criteria) + "\n\n"
            "KEY REQUIREMENTS:\n" + ("\n".join(f"- {r}" for r in requirements[:30]) or "- (none extracted)") + "\n\n"
            f"RESPONSE DOCUMENT:\n<<<\n{document[:MAX_DOC_CHARS]}\n>>>"
        )
        try:
            parsed = self.llm.complete_json(
                agent=self.name,
                system=_RUBRIC_SYSTEM,
                prompt=prompt,
                schema=_RUBRIC_SCHEMA,
                schema_name="rubric",
                purpose="rubric",
                max_tokens=3000,
                expected_tokens=900,
            ).parsed
        except LLMServiceError:
            if not self.llm.degraded_allowed:
                raise
            return None
        items = []
        for item in parsed.get("criteria") or []:
            if isinstance(item, dict) and clean_text(item.get("criterion")):
                items.append(
                    {
                        "criterion": clean_text(item.get("criterion")),
                        "score": clamp_float(item.get("score"), 0.0, 10.0),
                        "comment": clean_text(item.get("comment")),
                    }
                )
        return {
            "overall_score": clamp_float(parsed.get("overall_score"), 0.0, 10.0),
            "criteria": items,
            "strengths": as_text_list(parsed.get("strengths"), limit=6),
            "weaknesses": as_text_list(parsed.get("weaknesses"), limit=6),
            "recommendations": as_text_list(parsed.get("recommendations"), limit=6),
        }
