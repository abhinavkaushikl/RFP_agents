"""Tool registry for the agentic runtime.

Each existing agent (in `app.agents.*`) is exposed here as a `Tool` the
supervisor can pick and call. Tool functions:

- read missing args from prior `state.results` so supervisor plans can be
  sparse (just `{"tool": "score_proposal", "args": {}}` is enough)
- always return a dict `{"ok": bool, "output": dict, "summary": str, "error": str | None}`
- never raise; failures land in `error` so the supervisor can decide to replan

The compound tool `generate_proposal_sections` is intentionally not pure
agentic — it loops retrieve→generate→validate inside one call. This keeps
the supervisor's job tractable on local Qwen 2.5 7B (5 steps instead of 20).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agentic.state import WorkflowState
from app.schemas.domain import AgentContext


@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict[str, Any]
    fn: Callable[[dict, WorkflowState, dict], dict]


# ── helpers ────────────────────────────────────────────────────────────────
def _ctx(state: WorkflowState) -> AgentContext:
    return AgentContext(workflow_id=state.workflow_id)


def _safe_run(fn: Callable[[], Any]) -> dict:
    try:
        result = fn()
        return {
            "ok": True,
            "output": result.output if hasattr(result, "output") else result,
            "summary": result.summary if hasattr(result, "summary") else "",
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": {}, "summary": "", "error": str(exc)}


def _payload(state: WorkflowState) -> dict:
    return state.payload or {}


# ── tool implementations ───────────────────────────────────────────────────
def _structure_request(args: dict, state: WorkflowState, agents: dict) -> dict:
    text = args.get("request_text") or _payload(state).get("request_text", "")
    return _safe_run(lambda: agents["request_structuring"].run(
        {
            "request_text": text,
            "solution_type": args.get("solution_type") or _payload(state).get("solution_type"),
            "industry": args.get("industry") or _payload(state).get("industry"),
        },
        _ctx(state),
    ))


def _compare_solutions(args: dict, state: WorkflowState, agents: dict) -> dict:
    structured = state.get_result("structure_request") or {}
    solution_type = args.get("solution_type") or structured.get("solution_type") or "aiops_general"
    requirements = args.get("requirements") or structured.get("requirements") or []
    return _safe_run(lambda: agents["solution_comparison"].run(
        {"solution_type": solution_type, "requirements": requirements},
        _ctx(state),
    ))


def _retrieve_evidence(args: dict, state: WorkflowState, agents: dict) -> dict:
    structured = state.get_result("structure_request") or {}
    payload = _payload(state)
    return _safe_run(lambda: agents["retrieval"].run(
        {
            "query": args.get("query") or payload.get("request_text", ""),
            "section_type": args.get("section_type"),
            "solution_type": args.get("solution_type") or structured.get("solution_type"),
            "industry": args.get("industry") or structured.get("industry"),
            "top_k": args.get("top_k", 5),
        },
        _ctx(state),
    ))


def _generate_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    structured = state.get_result("structure_request") or {}
    solution = state.get_result("compare_solutions") or {}
    retrieval = state.get_result("retrieve_evidence") or {}
    payload = _payload(state)
    return _safe_run(lambda: agents["generation"].run(
        {
            "section_key": args.get("section_key", "executive_summary"),
            "request_summary": args.get("request_summary") or structured.get("request_summary", ""),
            "requirements": args.get("requirements") or structured.get("requirements", []),
            "vendors": args.get("vendors") or structured.get("vendors", []),
            "industry": args.get("industry") or structured.get("industry", ""),
            "solution_type": args.get("solution_type") or structured.get("solution_type", ""),
            "client_name": args.get("client_name")
            or payload.get("metadata", {}).get("client_name")
            or payload.get("title", "the client"),
            "evidence": args.get("evidence") or retrieval.get("results", []),
            "matching_offerings": args.get("matching_offerings") or solution.get("matching_offerings", []),
            "fast_mode": bool(args.get("fast_mode") or payload.get("metadata", {}).get("fast_mode")),
        },
        _ctx(state),
    ))


def _validate_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    structured = state.get_result("structure_request") or {}
    return _safe_run(lambda: agents["validation"].run(
        {
            "draft_text": args.get("draft_text", ""),
            "requirements": args.get("requirements") or structured.get("requirements", []),
        },
        _ctx(state),
    ))


def _generate_proposal_sections(args: dict, state: WorkflowState, agents: dict) -> dict:
    """Compound tool: retrieve+generate+validate per section in one supervisor step.

    Hides per-section complexity from the supervisor. Without this, a 5-section
    proposal would require ~20 supervisor decisions on a slow local LLM.
    """
    payload = _payload(state)
    structured = state.get_result("structure_request") or {}
    solution = state.get_result("compare_solutions") or {}
    sections = (
        args.get("sections")
        or payload.get("target_sections")
        or [
            "executive_summary",
            "solution_overview",
            "implementation_plan",
            "pricing_notes",
        ]
    )
    fast_mode = bool(payload.get("metadata", {}).get("fast_mode"))
    client_name = (
        payload.get("metadata", {}).get("client_name")
        or payload.get("title", "the client")
    )
    rendered: list[dict] = []
    for section_key in sections:
        retrieval = agents["retrieval"].run(
            {
                "query": payload.get("request_text", ""),
                "section_type": section_key,
                "solution_type": structured.get("solution_type"),
                "industry": structured.get("industry"),
                "top_k": 5,
            },
            _ctx(state),
        )
        generation = agents["generation"].run(
            {
                "section_key": section_key,
                "request_summary": structured.get("request_summary", ""),
                "requirements": structured.get("requirements", []),
                "vendors": structured.get("vendors", []),
                "industry": structured.get("industry", ""),
                "solution_type": structured.get("solution_type", ""),
                "client_name": client_name,
                "evidence": retrieval.output["results"],
                "matching_offerings": solution.get("matching_offerings", []),
                "fast_mode": fast_mode,
            },
            _ctx(state),
        )
        validation = agents["validation"].run(
            {
                "draft_text": generation.output["draft_text"],
                "requirements": structured.get("requirements", []),
            },
            _ctx(state),
        )
        rendered.append(
            {
                "section_key": section_key,
                "draft_text": generation.output["draft_text"],
                "citations": generation.output["citations"],
                "validation": validation.output,
            }
        )
    return {
        "ok": True,
        "output": {"sections": rendered},
        "summary": f"Generated {len(rendered)} sections via compound retrieve+generate+validate.",
        "error": None,
    }


def _revise_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    base_section = payload.get("base_section", {})
    return _safe_run(lambda: agents["revision"].run(
        {
            "section_key": args.get("section_key") or base_section.get("section_key", "implementation_plan"),
            "base_text": args.get("base_text") or base_section.get("draft_text", ""),
            "instruction": args.get("instruction") or payload.get("instruction", ""),
            "requirements": args.get("requirements") or payload.get("requirements", []),
            "evidence": args.get("evidence", []),
        },
        _ctx(state),
    ))


def _score_proposal(args: dict, state: WorkflowState, agents: dict) -> dict:
    structured = state.get_result("structure_request") or {}
    payload = _payload(state)
    document_text = args.get("document_text")
    if not document_text:
        sections = state.get_result("generate_proposal_sections", "sections", [])
        document_text = "\n\n".join(s.get("draft_text", "") for s in sections)
    if not document_text:
        document_text = payload.get("document_text", "")
    matched_evidence = args.get("matched_evidence")
    if matched_evidence is None:
        sections = state.get_result("generate_proposal_sections", "sections", [])
        matched_evidence = [s.get("citations", []) for s in sections] or [[]]
    return _safe_run(lambda: agents["scoring"].run(
        {
            "document_text": document_text,
            "requirements": args.get("requirements") or structured.get("requirements", []),
            "solution_type": args.get("solution_type") or structured.get("solution_type", ""),
            "retrieval_score_hint": args.get("retrieval_score_hint", 0.8),
            "matched_evidence": matched_evidence,
        },
        _ctx(state),
    ))


def _market_research(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    structured = state.get_result("structure_request") or {}
    return _safe_run(lambda: agents["market_research"].run(
        {
            "offerings": args.get("offerings") or payload.get("offerings", []),
            "requirement_summary": args.get("requirement_summary")
            or payload.get("requirement_summary")
            or structured.get("request_summary", ""),
            "industry": args.get("industry") or payload.get("industry") or structured.get("industry"),
            "max_companies": int(args.get("max_companies") or payload.get("max_companies", 8)),
        },
        _ctx(state),
    ))


def _detect_intent_fields(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    return _safe_run(lambda: agents["intent_detection"].run(
        {
            "transcript_text": args.get("transcript_text") or payload.get("transcript_text", ""),
            "file_name": args.get("file_name") or payload.get("file_name"),
        },
        _ctx(state),
    ))


def _frame_business_problem(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    return _safe_run(lambda: agents["problem_framing"].run(
        {
            "transcript_text": args.get("transcript_text") or payload.get("transcript_text", ""),
            "file_name": args.get("file_name") or payload.get("file_name"),
        },
        _ctx(state),
    ))


def _analyze_buyer_intelligence(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    return _safe_run(lambda: agents["buyer_intelligence"].run(
        {
            "transcript_text": args.get("transcript_text") or payload.get("transcript_text", ""),
            "file_name": args.get("file_name") or payload.get("file_name"),
        },
        _ctx(state),
    ))


def _analyze_product_fit(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    return _safe_run(lambda: agents["product_fit"].run(
        {
            "transcript_text": args.get("transcript_text") or payload.get("transcript_text", ""),
            "file_name": args.get("file_name") or payload.get("file_name"),
        },
        _ctx(state),
    ))


# ── registry builder ───────────────────────────────────────────────────────
def build_tool_registry(agents: dict) -> dict[str, Tool]:
    """Return a dict of tool_name → Tool, ready to be passed to the runner."""
    return {
        "structure_request": Tool(
            name="structure_request",
            description=(
                "Extract structured fields (requirements, vendors, solution_type, industry, "
                "request_summary) from raw RFP text. Run FIRST for any proposal-related intent."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "request_text": {"type": "string"},
                    "solution_type": {"type": "string"},
                    "industry": {"type": "string"},
                },
            },
            fn=_structure_request,
        ),
        "compare_solutions": Tool(
            name="compare_solutions",
            description=(
                "Match the request against our internal offering catalog. "
                "Returns matching_offerings + gaps. Reads from structure_request output."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "solution_type": {"type": "string"},
                    "requirements": {"type": "array", "items": {"type": "string"}},
                },
            },
            fn=_compare_solutions,
        ),
        "retrieve_evidence": Tool(
            name="retrieve_evidence",
            description=(
                "pgvector RAG lookup over historical proposals. "
                "Use to ground a single section, OR skip in favor of generate_proposal_sections."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "section_type": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
            },
            fn=_retrieve_evidence,
        ),
        "generate_section": Tool(
            name="generate_section",
            description=(
                "Generate ONE proposal section via Qwen. Requires upstream structure_request "
                "and ideally retrieve_evidence for the same section_type."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "section_key": {"type": "string"},
                    "fast_mode": {"type": "boolean"},
                },
                "required": ["section_key"],
            },
            fn=_generate_section,
        ),
        "validate_section": Tool(
            name="validate_section",
            description="Check that a draft covers the listed requirements (no LLM call).",
            args_schema={
                "type": "object",
                "properties": {
                    "draft_text": {"type": "string"},
                },
                "required": ["draft_text"],
            },
            fn=_validate_section,
        ),
        "generate_proposal_sections": Tool(
            name="generate_proposal_sections",
            description=(
                "Compound: retrieve+generate+validate for every section in one call. "
                "Preferred for proposal_generation intent — much faster than calling the "
                "atomic tools per section. Reads sections from payload.target_sections by default."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "sections": {"type": "array", "items": {"type": "string"}},
                },
            },
            fn=_generate_proposal_sections,
        ),
        "revise_section": Tool(
            name="revise_section",
            description="Apply a user instruction to an existing section draft via Qwen.",
            args_schema={
                "type": "object",
                "properties": {
                    "section_key": {"type": "string"},
                    "base_text": {"type": "string"},
                    "instruction": {"type": "string"},
                },
            },
            fn=_revise_section,
        ),
        "score_proposal": Tool(
            name="score_proposal",
            description=(
                "Composite score of the assembled document. Auto-pulls draft text from "
                "generate_proposal_sections output if not provided."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "document_text": {"type": "string"},
                    "retrieval_score_hint": {"type": "number"},
                },
            },
            fn=_score_proposal,
        ),
        "market_research": Tool(
            name="market_research",
            description=(
                "DDG search + page scrape + Qwen extraction to find vendors offering matching solutions."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "offerings": {"type": "array", "items": {"type": "string"}},
                    "industry": {"type": "string"},
                    "max_companies": {"type": "integer"},
                },
            },
            fn=_market_research,
        ),
        "detect_intent_fields": Tool(
            name="detect_intent_fields",
            description="Regex extraction of opportunity / client / urgency from a transcript or email.",
            args_schema={
                "type": "object",
                "properties": {
                    "transcript_text": {"type": "string"},
                },
            },
            fn=_detect_intent_fields,
        ),
        "frame_business_problem": Tool(
            name="frame_business_problem",
            description=(
                "LLM extraction of problem_statement, success_definition, stakeholder_impact, "
                "and urgency_statement from a business document or transcript."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "transcript_text": {"type": "string"},
                },
            },
            fn=_frame_business_problem,
        ),
        "analyze_buyer_intelligence": Tool(
            name="analyze_buyer_intelligence",
            description=(
                "LLM analysis of buyer readiness score, intent classification, buyer gaps, "
                "stakeholder coverage, conversation highlights, and recommended next actions."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "transcript_text": {"type": "string"},
                },
            },
            fn=_analyze_buyer_intelligence,
        ),
        "analyze_product_fit": Tool(
            name="analyze_product_fit",
            description=(
                "LLM analysis of product fit score, matched capabilities, fit gaps, integration fit, "
                "competitive positioning, risks, and recommended next actions."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "transcript_text": {"type": "string"},
                },
            },
            fn=_analyze_product_fit,
        ),
    }


def tool_catalog_for_prompt(tools: dict[str, Tool]) -> str:
    """Compact tool listing for inclusion in the supervisor prompt."""
    return "\n".join(f"- {t.name}: {t.description}" for t in tools.values())
