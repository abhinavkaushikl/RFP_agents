"""Workflow orchestrator — thin agentic shim.

Every endpoint funnels through `run_agentic()`. The hard-coded pipelines that
used to live here are gone; intent picking, planning, replanning, and
termination are all decided by the supervisor LLM. This file only translates
endpoint payloads into the agentic entry point and reshapes the resulting
state into the response contract each router expects.
"""
from __future__ import annotations

from typing import Any

from app.agentic import build_tool_registry, run_agentic
from app.agentic.state import WorkflowState
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService


class ProposalWorkflowOrchestrator:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
        agent_registry: dict[str, Any] | None = None,
    ) -> None:
        if agent_registry is None:
            from app.agents.registry import build_agent_registry

            agent_registry = build_agent_registry(retrieval_service, llm_service)
        self.agents = agent_registry
        self.llm_service = llm_service
        self.tools = build_tool_registry(self.agents)

    # ── single entry point ─────────────────────────────────────────────────
    def _run(self, payload: dict, intent_hint: str | None) -> WorkflowState:
        return run_agentic(
            payload=payload,
            intent_hint=intent_hint,
            agents=self.agents,
            tools=self.tools,
            llm=self.llm_service,
        )

    # ── per-endpoint response builders ─────────────────────────────────────
    def run_proposal_workflow(self, payload: dict) -> dict:
        state = self._run(payload, intent_hint="proposal_generation")
        structured = state.get_result("structure_request") or {}
        solution = state.get_result("compare_solutions") or {}
        sections = state.get_result("generate_proposal_sections", "sections", []) or []
        if not sections:  # supervisor used the atomic generate_section path
            single = state.get_result("generate_section")
            if single:
                sections = [
                    {
                        "section_key": single.get("section_key", "executive_summary"),
                        "draft_text": single.get("draft_text", ""),
                        "citations": single.get("citations", []),
                        "validation": (state.get_result("validate_section") or {}),
                    }
                ]
        scores = state.get_result("score_proposal") or {}
        return {
            "workflow_id": state.workflow_id,
            "status": "completed" if state.done else "incomplete",
            "request": structured,
            "plan": {"intent": state.intent, "steps_executed": state.steps_taken},
            "solution_comparison": solution,
            "sections": sections,
            "scores": scores,
            "step_summaries": state.tool_summaries(),
            "agent_trace": state.trace,
        }

    def run_revision_workflow(self, payload: dict, base_section: dict) -> dict:
        merged = {**payload, "base_section": base_section}
        state = self._run(merged, intent_hint="revision")
        revision = state.get_result("revise_section") or {}
        validation = state.get_result("validate_section") or {}
        retrieval = state.get_result("retrieve_evidence") or {}
        return {
            "workflow_id": state.workflow_id,
            "status": "completed" if state.done else "incomplete",
            "plan": {"intent": state.intent, "steps_executed": state.steps_taken},
            "retrieval": retrieval,
            "revision": revision,
            "validation": validation,
            "agent_trace": state.trace,
        }

    def run_document_match_workflow(self, payload: dict) -> dict:
        state = self._run(payload, intent_hint="document_match")
        structured = state.get_result("structure_request") or {}
        solution = state.get_result("compare_solutions") or {}
        retrieval = state.get_result("retrieve_evidence") or {}
        scores = state.get_result("score_proposal") or {}
        return {
            "workflow_id": state.workflow_id,
            "status": "completed" if state.done else "incomplete",
            "request": structured,
            "solution_comparison": solution,
            "retrieval": retrieval,
            "scores": scores,
            "agent_trace": state.trace,
        }

    def run_market_research_workflow(self, payload: dict) -> dict:
        state = self._run(payload, intent_hint="market_research")
        result = state.get_result("market_research") or {}
        return {
            "workflow_id": state.workflow_id,
            "status": "completed" if state.done else "incomplete",
            "rows": result.get("rows", []),
            "offerings": result.get("offerings", payload.get("offerings", [])),
            "industry": result.get("industry", payload.get("industry")),
            "summary": state.final_summary or "Market research completed.",
            "agent_trace": state.trace,
        }

    def run_intent_detection_workflow(self, payload: dict) -> dict:
        state = self._run(payload, intent_hint="intent_detection")
        result = state.get_result("detect_intent_fields") or {}
        framing = state.get_result("frame_business_problem") or {}
        buyer_intelligence = state.get_result("analyze_buyer_intelligence") or {}
        product_fit_analysis = state.get_result("analyze_product_fit") or {}
        client_overview = dict(result.get("client_overview", {}))
        for key in (
            "problem_statement",
            "success_definition",
            "stakeholder_impact",
            "urgency_statement",
        ):
            value = framing.get(key)
            if value and value != "Not explicitly stated.":
                client_overview[key] = value
        buyer_readiness = dict(result.get("buyer_readiness", {}))
        if buyer_intelligence:
            buyer_readiness.update(buyer_intelligence)
            score = buyer_intelligence.get("buyer_readiness_score")
            if score is not None:
                try:
                    buyer_readiness["readiness_rating"] = round(float(score) / 10)
                except (TypeError, ValueError):
                    pass
            gaps = buyer_intelligence.get("buyer_gaps") or []
            if gaps:
                buyer_readiness["buying_gaps"] = "\n".join(
                    f"{gap.get('gap_type', 'Gap')}: {gap.get('description', '')}"
                    for gap in gaps
                    if isinstance(gap, dict)
                )
        return {
            "workflow_id": state.workflow_id,
            "status": "completed" if state.done else "incomplete",
            "client_overview": client_overview,
            "buyer_readiness": buyer_readiness,
            "product_fit": {**(result.get("product_fit", {}) or {}), **product_fit_analysis},
            "summary": state.final_summary or "Intent detection completed.",
            "agent_trace": state.trace,
        }
