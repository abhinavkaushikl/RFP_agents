"""Solution comparison: map RFP requirements to the profile's offering catalog."""
from __future__ import annotations

import re

from app.agents.base import PlatformAgent
from app.agents.normalize import as_text_list, clean_text, normalize_choice
from app.agents.schema import STR, arr, enum, obj
from app.domain.profile import DomainProfile, load_profile
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.schemas.domain import AgentContext, AgentResult

_WORD = re.compile(r"[a-z0-9]+")


def _catalog_system(profile: DomainProfile) -> str:
    return (
        f"You map RFP requirements to the offering catalog of {profile.organization.name}.\n"
        "For each requirement pick the single best offering code and rate coverage:\n"
        "- full: the offering clearly delivers it\n"
        "- partial: the offering covers part of it or needs extension or a partner\n"
        "- none: nothing in the catalog covers it (use offering_code \"none\")\n"
        "Judge only from the catalog text. positioning_notes: 2-4 short notes on how to position "
        "the matched offerings. fit_explanation: one or two sentences. Return JSON only.\n\n"
        f"OFFERING CATALOG:\n{profile.catalog_text()}"
    )


_INFER_SYSTEM = (
    "No offering catalog is configured. From the RFP requirements, list the capabilities a vendor "
    "must bring (4-10 short noun phrases), 2-4 positioning notes for the response, and a one or "
    "two sentence fit explanation. Return JSON only."
)


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if len(t) > 3}


class SolutionComparisonAgent(PlatformAgent):
    name = "solution_comparison"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm = llm_service

    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        profile = load_profile(payload.get("profile"))
        requirements = [r for r in payload.get("requirements") or [] if clean_text(r)]
        solution_type = payload.get("solution_type") or "general"
        if not requirements:
            output = self._empty(solution_type, profile, "No requirements to compare.")
            return AgentResult(self.name, output, "No requirements to compare.", 0.3)

        if profile.offerings:
            output = self._with_catalog(profile, requirements, solution_type)
        else:
            output = self._infer(profile, requirements, solution_type)
        summary = (
            f"Matched {len(requirements) - len(output['gaps'])}/{len(requirements)} requirements "
            f"to {len(output['matching_offerings'])} offerings ({output['mode']})."
            if output["catalog_configured"]
            else f"Inferred {len(output['matching_offerings'])} required capabilities (no catalog configured)."
        )
        return AgentResult(self.name, output, summary, 0.8 if output["mode"] == "llm" else 0.5)

    # ── catalog matching ──────────────────────────────────────────────
    def _with_catalog(self, profile: DomainProfile, requirements: list[str], solution_type: str) -> dict:
        codes = [o.code for o in profile.offerings]
        schema = obj(
            matches=arr(
                obj(
                    requirement_id=STR,
                    offering_code=enum(*codes, "none"),
                    coverage=enum("full", "partial", "none"),
                    rationale=STR,
                )
            ),
            positioning_notes=arr(STR),
            fit_explanation=STR,
        )
        numbered = "\n".join(f"R{i}: {r}" for i, r in enumerate(requirements, 1))
        parsed = None
        if self.llm is not None:
            try:
                parsed = self.llm.complete_json(
                    agent=self.name,
                    system=_catalog_system(profile),
                    prompt=f"Requested solution type: {solution_type}\n\nREQUIREMENTS:\n{numbered}",
                    schema=schema,
                    schema_name="catalog_match",
                    purpose="compare_solutions",
                    max_tokens=4000,
                    expected_tokens=1200,
                ).parsed
            except LLMServiceError:
                if not self.llm.degraded_allowed:
                    raise
        if parsed:
            matches = []
            for item in parsed.get("matches") or []:
                if not isinstance(item, dict):
                    continue
                rid = clean_text(item.get("requirement_id")).upper().lstrip("R")
                idx = int(rid) - 1 if rid.isdigit() else -1
                if not 0 <= idx < len(requirements):
                    continue
                matches.append(
                    {
                        "requirement": requirements[idx],
                        "offering_code": normalize_choice(item.get("offering_code"), [*codes, "none"], "none"),
                        "coverage": normalize_choice(item.get("coverage"), ["full", "partial", "none"], "none"),
                        "rationale": clean_text(item.get("rationale")),
                    }
                )
            notes = as_text_list(parsed.get("positioning_notes"), limit=6)
            explanation = clean_text(parsed.get("fit_explanation"))
            mode = "llm"
        else:
            matches = self._keyword_matches(profile, requirements)
            notes = []
            explanation = "Matched by keyword overlap with the offering catalog."
            mode = "heuristic"
        return self._summarize(profile, requirements, solution_type, matches, notes, explanation, mode)

    def _keyword_matches(self, profile: DomainProfile, requirements: list[str]) -> list[dict]:
        matches = []
        for req in requirements:
            req_tokens = _tokens(req)
            best, best_score = None, 0
            for off in profile.offerings:
                vocab = _tokens(" ".join([off.name, off.description, *off.capabilities, *off.keywords]))
                score = len(req_tokens & vocab)
                if score > best_score:
                    best, best_score = off, score
            coverage = "full" if best_score >= 3 else "partial" if best_score >= 1 else "none"
            matches.append(
                {
                    "requirement": req,
                    "offering_code": best.code if best and best_score else "none",
                    "coverage": coverage,
                    "rationale": "keyword overlap",
                }
            )
        return matches

    def _summarize(
        self,
        profile: DomainProfile,
        requirements: list[str],
        solution_type: str,
        matches: list[dict],
        notes: list[str],
        explanation: str,
        mode: str,
    ) -> dict:
        matched_by_req = {m["requirement"]: m for m in matches}
        counts: dict[str, int] = {}
        full = partial = 0
        for m in matches:
            if m["coverage"] == "none" or m["offering_code"] == "none":
                continue
            counts[m["offering_code"]] = counts.get(m["offering_code"], 0) + 1
            if m["coverage"] == "full":
                full += 1
            else:
                partial += 1
        ordered = sorted(counts, key=lambda c: -counts[c])
        names = [(profile.offering(c).name if profile.offering(c) else c) for c in ordered]
        gaps = [
            r for r in requirements
            if r not in matched_by_req
            or matched_by_req[r]["coverage"] == "none"
            or matched_by_req[r]["offering_code"] == "none"
        ]
        if not notes and names:
            notes = [f"Lead with {names[0]} and show how it addresses the highest-priority requirements."]
        return {
            "solution_type": solution_type,
            "catalog_configured": True,
            "matching_offerings": names,
            "matching_offering_codes": ordered,
            "matches": matches,
            "gaps": gaps,
            "positioning_notes": notes,
            "fit_explanation": explanation,
            "solution_fit_score": round((full + 0.5 * partial) / len(requirements), 3),
            "mode": mode,
        }

    # ── no catalog: infer capabilities ────────────────────────────────
    def _infer(self, profile: DomainProfile, requirements: list[str], solution_type: str) -> dict:
        schema = obj(capabilities=arr(STR), positioning_notes=arr(STR), fit_explanation=STR)
        numbered = "\n".join(f"R{i}: {r}" for i, r in enumerate(requirements, 1))
        if self.llm is not None:
            try:
                parsed = self.llm.complete_json(
                    agent=self.name,
                    system=_INFER_SYSTEM,
                    prompt=f"Requested solution type: {solution_type}\n\nREQUIREMENTS:\n{numbered}",
                    schema=schema,
                    schema_name="capability_inference",
                    purpose="infer_capabilities",
                    max_tokens=2500,
                    expected_tokens=600,
                ).parsed
                output = self._empty(solution_type, profile, clean_text(parsed.get("fit_explanation")))
                output["matching_offerings"] = as_text_list(parsed.get("capabilities"), limit=10)
                output["positioning_notes"] = as_text_list(parsed.get("positioning_notes"), limit=6)
                output["mode"] = "llm"
                return output
            except LLMServiceError:
                if not self.llm.degraded_allowed:
                    raise
        return self._empty(
            solution_type,
            profile,
            "No offering catalog is configured in this profile; add `offerings` to compare against your catalog.",
        )

    def _empty(self, solution_type: str, profile: DomainProfile, explanation: str) -> dict:
        return {
            "solution_type": solution_type,
            "catalog_configured": bool(profile.offerings),
            "matching_offerings": [],
            "matching_offering_codes": [],
            "matches": [],
            "gaps": [],
            "positioning_notes": [],
            "fit_explanation": explanation,
            "solution_fit_score": None,
            "mode": "heuristic",
        }
