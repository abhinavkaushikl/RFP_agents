"""Workflow orchestrator — translates endpoint payloads into agentic runs.

Every endpoint calls `run_agentic()`; this class shapes the resulting state into
each response contract, attaches the token-usage report, and persists the run.
"""
from __future__ import annotations

from typing import Any

from app.agentic import build_tool_registry, run_agentic
from app.agentic.state import WorkflowState
from app.core.errors import InvalidRequestError, NotFoundError
from app.domain.profile import ProfileNotFoundError, load_profile
from app.llm.service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.run_store import RunStore

# Large inputs are not copied into the stored payload.
_PAYLOAD_TRUNCATE = 20_000


def _status(state: WorkflowState, partial: bool = False) -> str:
    if not state.done:
        return "incomplete"
    if partial or state.failed_tools():
        return "partial"
    return "completed"


def _slim_payload(payload: dict) -> dict:
    out = {}
    for key, value in payload.items():
        out[key] = value[:_PAYLOAD_TRUNCATE] if isinstance(value, str) else value
    return out


class ProposalWorkflowOrchestrator:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
        agent_registry: dict[str, Any] | None = None,
        *,
        embedding_service: Any = None,
        run_store: RunStore | None = None,
    ) -> None:
        if agent_registry is None:
            from app.agents.registry import build_agent_registry

            agent_registry = build_agent_registry(retrieval_service, llm_service, embedding_service=embedding_service)
        self.agents = agent_registry
        self.llm_service = llm_service
        self.tools = build_tool_registry(self.agents)
        self.run_store = run_store

    # ── single entry point ─────────────────────────────────────────────
    def _run(self, payload: dict, intent_hint: str | None) -> WorkflowState:
        self.llm_service.ensure_configured()
        try:
            profile = load_profile(payload.get("profile"))
        except ProfileNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        payload = {**payload, "profile": profile.name}
        return run_agentic(
            payload=payload,
            intent_hint=intent_hint,
            agents=self.agents,
            tools=self.tools,
            llm=self.llm_service,
        )

    def _common(self, state: WorkflowState, status: str) -> dict:
        usage = state.usage_report()
        totals = usage.get("totals") or {}
        warnings = list(state.warnings)
        if totals.get("errors"):
            if not self.llm_service.configured:
                warnings.append(
                    f"Degraded mode: Groq is not configured, so {totals['errors']} model calls were skipped and the "
                    "agents used heuristic fallbacks. Set RFP_GROQ_API_KEY for real output."
                )
            else:
                warnings.append(f"{totals['errors']} model calls failed; see token_usage.calls for details.")
        return {
            "workflow_id": state.workflow_id,
            "status": status,
            "intent": state.intent,
            "profile": state.profile,
            "summary": state.final_summary,
            "warnings": list(dict.fromkeys(warnings)),
            "token_usage": usage,
            "agent_trace": state.trace,
        }

    def _persist(self, state: WorkflowState, response: dict, sections: list[dict] | None = None) -> dict[str, dict] | None:
        if self.run_store is None:
            response["persisted"] = False
            return None
        stored = {k: v for k, v in response.items() if k not in ("agent_trace",)}
        stored["token_usage"] = state.usage_report(include_calls=False)
        ids = self.run_store.save_workflow(
            workflow_id=state.workflow_id,
            workflow_type=state.intent or "unknown",
            status=response["status"],
            profile=state.profile,
            payload=_slim_payload(state.payload),
            result=stored,
            sections=sections,
            usage_records=[r.to_dict() for r in (state.usage.records if state.usage else [])],
        )
        response["persisted"] = ids is not None
        return ids

    # ── proposal generation ────────────────────────────────────────────
    def run_proposal_workflow(self, payload: dict) -> dict:
        if not (payload.get("request_text") or "").strip():
            raise InvalidRequestError("request_text is required")
        state = self._run(payload, intent_hint="proposal_generation")
        sections = list(state.get_result("generate_proposal_sections", "sections", []) or [])
        if not sections:
            single = state.get_result("generate_section")
            if single:
                sections = [{**single, "validation": state.get_result("validate_section") or {}, "error": None}]
        partial = any(s.get("error") for s in sections) or not sections
        response = {
            **self._common(state, _status(state, partial)),
            "request": state.get_result("structure_request") or {},
            "solution_comparison": state.get_result("compare_solutions") or {},
            "sections": sections,
            "scores": state.get_result("score_proposal") or {},
            "step_summaries": state.tool_summaries(),
        }
        ids = self._persist(state, response, sections)
        if ids:
            for sec in response["sections"]:
                sec.update(ids.get(sec["section_key"], {}))
        return response

    # ── revision ───────────────────────────────────────────────────────
    def run_revision_workflow(self, payload: dict, section_id: str) -> dict:
        stored = self.run_store.load_section(section_id) if self.run_store else None
        base_text = payload.get("base_text") or (stored or {}).get("draft_text") or ""
        if not base_text.strip():
            raise NotFoundError(
                f"Section {section_id} was not found and no base_text was provided to revise."
            )
        section_key = payload.get("section_key") or (stored or {}).get("section_key") or "section"
        base_section = {"section_id": section_id, "section_key": section_key, "draft_text": base_text}
        state = self._run({**payload, "base_section": base_section}, intent_hint="revision")
        revision = dict(state.get_result("revise_section") or {})
        validation = state.get_result("validate_section") or {}
        response = {
            **self._common(state, _status(state, partial=not revision)),
            "section_id": section_id,
            "retrieval": state.get_result("retrieve_evidence") or {},
            "revision": revision,
            "validation": validation,
        }
        if stored and revision and self.run_store:
            saved = self.run_store.save_section_revision(
                section_id=section_id,
                instruction=payload.get("instruction", ""),
                revision=revision,
                validation=validation,
            )
            if saved:
                response["revision"].update(saved)
        if self.run_store:
            response["persisted"] = self.run_store.save_usage(
                state.workflow_id, "revision", [r.to_dict() for r in state.usage.records] if state.usage else []
            )
        return response

    # ── document match ─────────────────────────────────────────────────
    def run_document_match_workflow(self, payload: dict) -> dict:
        if not (payload.get("request_text") or "").strip() or not (payload.get("document_text") or "").strip():
            raise InvalidRequestError("request_text and document_text are required")
        state = self._run(payload, intent_hint="document_match")
        response = {
            **self._common(state, _status(state)),
            "request": state.get_result("structure_request") or {},
            "solution_comparison": state.get_result("compare_solutions") or {},
            "retrieval": state.get_result("retrieve_evidence") or {},
            "scores": state.get_result("score_proposal") or {},
            "step_summaries": state.tool_summaries(),
        }
        self._persist(state, response)
        return response

    # ── market research ────────────────────────────────────────────────
    def run_market_research_workflow(self, payload: dict) -> dict:
        if not [o for o in payload.get("offerings") or [] if str(o).strip()]:
            raise InvalidRequestError("At least one offering is required")
        state = self._run(payload, intent_hint="market_research")
        result = state.get_result("market_research") or {}
        response = {
            **self._common(state, _status(state)),
            "rows": result.get("rows", []),
            "offerings": result.get("offerings", payload.get("offerings", [])),
            "industry": result.get("industry", payload.get("industry")),
        }
        response["summary"] = state.final_summary or "Market research completed."
        self._persist(state, response)
        return response

    # ── intent detection ───────────────────────────────────────────────
    def run_intent_detection_workflow(self, payload: dict) -> dict:
        if not (payload.get("transcript_text") or "").strip():
            raise InvalidRequestError("transcript_text is required")
        state = self._run(payload, intent_hint="intent_detection")
        result = state.get_result("detect_intent_fields") or {}
        framing = state.get_result("frame_business_problem") or {}
        buyer = state.get_result("analyze_buyer_intelligence") or {}
        fit = state.get_result("analyze_product_fit") or {}
        client_overview = dict(result.get("client_overview", {}))
        for key in ("problem_statement", "success_definition", "stakeholder_impact", "urgency_statement"):
            value = framing.get(key)
            if value and value != "Not explicitly stated.":
                client_overview[key] = value
        buyer_readiness = dict(result.get("buyer_readiness", {}))
        if buyer:
            buyer_readiness.update(buyer)
            score = buyer.get("buyer_readiness_score")
            if score is not None:
                buyer_readiness["readiness_rating"] = round(float(score) / 10)
            gaps = buyer.get("buyer_gaps") or []
            if gaps:
                buyer_readiness["buying_gaps"] = "\n".join(
                    f"{g.get('gap_type', 'Gap')}: {g.get('description', '')}" for g in gaps if isinstance(g, dict)
                )
        response = {
            **self._common(state, _status(state)),
            "client_overview": client_overview,
            "buyer_readiness": buyer_readiness,
            "product_fit": {**(result.get("product_fit", {}) or {}), **fit},
        }
        response["summary"] = state.final_summary or "Intent detection completed."
        self._persist(state, response)
        return response
