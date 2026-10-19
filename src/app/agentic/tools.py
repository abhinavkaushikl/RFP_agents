"""Tool registry for the agentic runtime.

Each agent is exposed as a `Tool` the supervisor can plan with. Tool functions:

- fill missing args from earlier `state.results`, so plans can be sparse
  (`{"tool": "score_proposal", "args": {}}` is enough)
- tag every model call with the tool (and section) for the token report
- return `{"ok": bool, "output": dict, "summary": str, "error": str | None}`
- never raise for ordinary failures, so the supervisor can replan; configuration,
  authentication, and exhausted rate limits do propagate, because no replan fixes them

`generate_proposal_sections` is a compound tool: retrieval for every section,
then the first section alone (it primes the provider's prompt cache with the
shared RFP context), then the remaining sections in parallel, then validation.
"""
from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

from app.agentic.events import emit
from app.agentic.state import WorkflowState
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.profile import load_profile
from app.llm.errors import LLMAuthError, LLMConfigurationError, LLMRateLimitError
from app.llm.usage import usage_tags
from app.schemas.domain import AgentContext

logger = get_logger(__name__)

_FATAL = (LLMConfigurationError, LLMAuthError, LLMRateLimitError)


@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict[str, Any]
    fn: Callable[[dict, WorkflowState, dict], dict]


# ── helpers ────────────────────────────────────────────────────────────
def _ctx(state: WorkflowState) -> AgentContext:
    return AgentContext(workflow_id=state.workflow_id)


def _safe_run(tool_name: str, fn: Callable[[], Any]) -> dict:
    with usage_tags(tool=tool_name):
        try:
            result = fn()
        except _FATAL:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tool %s failed: %s", tool_name, exc)
            return {"ok": False, "output": {}, "summary": "", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "output": result.output if hasattr(result, "output") else result,
        "summary": result.summary if hasattr(result, "summary") else "",
        "error": None,
    }


def _payload(state: WorkflowState) -> dict:
    return state.payload or {}


def _metadata(state: WorkflowState) -> dict:
    meta = _payload(state).get("metadata")
    return meta if isinstance(meta, dict) else {}


def _structured(state: WorkflowState) -> dict:
    return state.get_result("structure_request") or {}


def _client_name(state: WorkflowState) -> str:
    payload = _payload(state)
    return (
        payload.get("client_name")
        or _metadata(state).get("client_name")
        or _structured(state).get("client_name")
        or ""
    )


def _requirements(state: WorkflowState, args: dict) -> list[str]:
    return args.get("requirements") or _structured(state).get("requirements") or _payload(state).get("requirements") or []


def _section_context(state: WorkflowState) -> dict:
    """Inputs shared by every section of one proposal (kept identical for prompt caching)."""
    s = _structured(state)
    solution = state.get_result("compare_solutions") or {}
    payload = _payload(state)
    return {
        "profile": state.profile,
        "client_name": _client_name(state),
        "industry": s.get("industry") or payload.get("industry") or "",
        "solution_type": s.get("solution_type") or payload.get("solution_type") or "general",
        "title": s.get("title") or payload.get("title") or "",
        "request_summary": s.get("request_summary", ""),
        "requirements": s.get("requirements", []),
        "requirement_details": s.get("requirement_details", []),
        "evaluation_criteria": s.get("evaluation_criteria", []),
        "timeline": s.get("timeline", ""),
        "budget": s.get("budget", ""),
        "compliance_requirements": s.get("compliance_requirements", []),
        "vendors": s.get("vendors", []),
        "matching_offerings": solution.get("matching_offerings", []),
        "positioning_notes": solution.get("positioning_notes", []),
        "user_instruction": payload.get("user_instruction") or "",
        "fast_mode": bool(_metadata(state).get("fast_mode") or payload.get("fast_mode")),
    }


def _retrieval_query(state: WorkflowState, section_key: str | None = None) -> str:
    payload = _payload(state)
    summary = _structured(state).get("request_summary") or payload.get("request_text") or ""
    base = payload.get("base_section") or {}
    if not summary and base:
        summary = f"{payload.get('instruction', '')} {(base.get('draft_text') or '')[:600]}"
    if not summary and payload.get("document_text"):
        summary = payload["document_text"][:800]
    summary = " ".join(summary.split())[:800]
    if section_key:
        title = load_profile(state.profile).section_title(section_key)
        return f"{title}: {summary}" if summary else title
    return summary


def _retrieve(agents: dict, state: WorkflowState, section_key: str | None, top_k: int, query: str | None = None) -> list[dict]:
    s = _structured(state)
    result = agents["retrieval"].run(
        {
            "query": query or _retrieval_query(state, section_key),
            "section_type": section_key,
            "solution_type": s.get("solution_type") or _payload(state).get("solution_type"),
            "industry": s.get("industry") or _payload(state).get("industry"),
            "top_k": top_k,
            "profile": state.profile,
        },
        _ctx(state),
    )
    return result.output.get("results", [])


# ── tool implementations ───────────────────────────────────────────────
def _structure_request(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    return _safe_run("structure_request", lambda: agents["request_structuring"].run(
        {
            "request_text": args.get("request_text") or payload.get("request_text") or payload.get("document_text", ""),
            "title": payload.get("title"),
            "client_name": payload.get("client_name") or _metadata(state).get("client_name"),
            "industry": args.get("industry") or payload.get("industry"),
            "solution_type": args.get("solution_type") or payload.get("solution_type"),
            "profile": state.profile,
        },
        _ctx(state),
    ))


def _compare_solutions(args: dict, state: WorkflowState, agents: dict) -> dict:
    s = _structured(state)
    return _safe_run("compare_solutions", lambda: agents["solution_comparison"].run(
        {
            "solution_type": args.get("solution_type") or s.get("solution_type") or _payload(state).get("solution_type"),
            "requirements": _requirements(state, args),
            "profile": state.profile,
        },
        _ctx(state),
    ))


def _retrieve_evidence(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    section_type = args.get("section_type") or (payload.get("base_section") or {}).get("section_key")
    s = _structured(state)

    def run():
        return agents["retrieval"].run(
            {
                "query": args.get("query") or _retrieval_query(state, section_type),
                "section_type": section_type,
                "solution_type": args.get("solution_type") or s.get("solution_type") or payload.get("solution_type"),
                "industry": args.get("industry") or s.get("industry") or payload.get("industry"),
                "top_k": int(args.get("top_k") or get_settings().retrieval_top_k),
                "profile": state.profile,
            },
            _ctx(state),
        )

    return _safe_run("retrieve_evidence", run)


def _generate_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    profile = load_profile(state.profile)
    key = profile.canonical_section_key(args.get("section_key") or profile.resolved_default_sections()[0])
    evidence = args.get("evidence") or state.get_result("retrieve_evidence", "results", []) or []

    def run():
        with usage_tags(section_key=key):
            return agents["generation"].run({**_section_context(state), "section_key": key, "evidence": evidence}, _ctx(state))

    return _safe_run("generate_section", run)


def _validate_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    draft = (
        args.get("draft_text")
        or state.get_result("revise_section", "draft_text")
        or state.get_result("generate_section", "draft_text")
        or ""
    )
    return _safe_run("validate_section", lambda: agents["validation"].run(
        {"draft_text": draft, "requirements": _requirements(state, args)},
        _ctx(state),
    ))


def _generate_proposal_sections(args: dict, state: WorkflowState, agents: dict) -> dict:
    settings = get_settings()
    profile = load_profile(state.profile)
    payload = _payload(state)
    requested = args.get("sections") or payload.get("target_sections") or profile.resolved_default_sections()
    sections = list(dict.fromkeys(profile.canonical_section_key(k) for k in requested if str(k).strip()))
    if not sections:
        return {"ok": False, "output": {}, "summary": "", "error": "No sections requested"}
    shared = _section_context(state)
    errors: dict[str, str] = {}
    emit("sections_planned", sections=[{"section_key": k, "title": profile.section_title(k)} for k in sections])

    with usage_tags(tool="generate_proposal_sections"):
        # 1) Retrieval, sequentially: it shares the request's database session.
        evidence: dict[str, list[dict]] = {}
        for key in sections:
            try:
                evidence[key] = _retrieve(agents, state, key, settings.retrieval_top_k)
            except _FATAL:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Retrieval failed for %s: %s", key, exc)
                evidence[key] = []

        # 2) Generation: first section alone, then the rest in parallel.
        def generate(key: str) -> tuple[str, dict | None, str | None]:
            title = profile.section_title(key)
            emit("section_started", section_key=key, title=title, evidence=len(evidence[key]))
            with usage_tags(section_key=key):
                try:
                    result = agents["generation"].run({**shared, "section_key": key, "evidence": evidence[key]}, _ctx(state))
                except (LLMConfigurationError, LLMAuthError):
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Generation failed for %s: %s", key, exc)
                    emit("section_done", section_key=key, title=title, ok=False, error=f"{type(exc).__name__}: {exc}")
                    return key, None, f"{type(exc).__name__}: {exc}"
            out = result.output
            emit(
                "section_done",
                section_key=key,
                title=title,
                ok=True,
                word_count=out.get("word_count"),
                cache_hit=out.get("cache_hit"),
                generation_mode=out.get("generation_mode"),
                tokens=(out.get("usage") or {}).get("total_tokens", 0),
                preview=(out.get("draft_text") or "")[:280],
            )
            return key, out, None

        outputs: dict[str, dict | None] = {}
        first, rest = sections[0], sections[1:]
        _, outputs[first], err = generate(first)
        if err:
            errors[first] = err
        if rest:
            workers = min(settings.section_concurrency, len(rest))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="section") as pool:
                futures = [pool.submit(contextvars.copy_context().run, generate, key) for key in rest]
                for future in futures:
                    key, output, err = future.result()
                    outputs[key] = output
                    if err:
                        errors[key] = err

        # 3) Validation, sequentially (local embedding model).
        rendered: list[dict] = []
        for key in sections:
            out = outputs.get(key)
            item: dict[str, Any] = {
                "section_key": key,
                "title": profile.section_title(key),
                "draft_text": "",
                "citations": [],
                "evidence_scores": [round(float(e.get("score", 0.0)), 3) for e in evidence.get(key, [])],
                "validation": {},
                "generation_mode": "failed",
                "model": None,
                "cache_hit": False,
                "word_count": 0,
                "usage": None,
                "error": errors.get(key),
            }
            if out:
                item.update({k: out.get(k) for k in ("title", "draft_text", "citations", "generation_mode", "model",
                                                       "cache_hit", "word_count", "usage") if k in out})
                validation = agents["validation"].run(
                    {"draft_text": out.get("draft_text", ""), "requirements": shared["requirements"]}, _ctx(state)
                )
                item["validation"] = validation.output
            rendered.append(item)

    ok_count = sum(1 for r in rendered if not r["error"])
    cache_hits = sum(1 for r in rendered if r.get("cache_hit"))
    if errors and any("RateLimit" in e for e in errors.values()):
        state.warnings.append(
            "Some sections hit the Groq rate limit. Retry the request: finished sections are cached and cost nothing."
        )
    return {
        "ok": ok_count > 0,
        "output": {"sections": rendered, "requested": sections, "cache_hits": cache_hits, "failed": sorted(errors)},
        "summary": f"Generated {ok_count}/{len(sections)} sections ({cache_hits} from cache).",
        "error": None if ok_count else "; ".join(f"{k}: {v}" for k, v in errors.items()),
    }


def _revise_section(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    base = payload.get("base_section") or {}
    key = args.get("section_key") or base.get("section_key") or "section"

    def run():
        with usage_tags(section_key=key):
            return agents["revision"].run(
                {
                    "profile": state.profile,
                    "section_key": key,
                    "base_text": args.get("base_text") or base.get("draft_text", ""),
                    "instruction": args.get("instruction") or payload.get("instruction", ""),
                    "requirements": args.get("requirements") or payload.get("requirements") or [],
                    "evidence": args.get("evidence") or state.get_result("retrieve_evidence", "results", []) or [],
                },
                _ctx(state),
            )

    return _safe_run("revise_section", run)


def _sections_for_scoring(state: WorkflowState) -> list[dict]:
    sections = state.get_result("generate_proposal_sections", "sections", []) or []
    if not sections:
        single = state.get_result("generate_section")
        if single:
            sections = [single]
    return [s for s in sections if not s.get("error")]


def _score_proposal(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    s = _structured(state)
    sections = _sections_for_scoring(state)
    document = args.get("document_text") or "\n\n".join(
        f"## {sec.get('title') or sec.get('section_key')}\n{sec.get('draft_text', '')}" for sec in sections
    ) or payload.get("document_text", "")
    scores = [sc for sec in sections for sc in sec.get("evidence_scores") or []]
    scores += [float(r.get("score", 0.0)) for r in state.get_result("retrieve_evidence", "results", []) or []]
    targets = state.get_result("generate_proposal_sections", "requested", []) or [sec.get("section_key") for sec in sections]
    return _safe_run("score_proposal", lambda: agents["scoring"].run(
        {
            "profile": state.profile,
            "document_text": document,
            "requirements": _requirements(state, args),
            "evaluation_criteria": s.get("evaluation_criteria") or [],
            "solution_fit_score": (state.get_result("compare_solutions") or {}).get("solution_fit_score"),
            "retrieval_scores": scores,
            "sections": sections,
            "target_sections": targets if sections else [],
            "matched_evidence": [sec.get("citations", []) for sec in sections],
        },
        _ctx(state),
    ))


def _market_research(args: dict, state: WorkflowState, agents: dict) -> dict:
    payload = _payload(state)
    s = _structured(state)
    return _safe_run("market_research", lambda: agents["market_research"].run(
        {
            "offerings": args.get("offerings") or payload.get("offerings", []),
            "requirement_summary": args.get("requirement_summary") or payload.get("requirement_summary") or s.get("request_summary", ""),
            "industry": args.get("industry") or payload.get("industry") or s.get("industry"),
            "max_companies": int(args.get("max_companies") or payload.get("max_companies", 8)),
        },
        _ctx(state),
    ))


def _transcript_tool(tool_name: str, agent_key: str) -> Callable[[dict, WorkflowState, dict], dict]:
    def fn(args: dict, state: WorkflowState, agents: dict) -> dict:
        payload = _payload(state)
        return _safe_run(tool_name, lambda: agents[agent_key].run(
            {
                "transcript_text": args.get("transcript_text") or payload.get("transcript_text", ""),
                "file_name": args.get("file_name") or payload.get("file_name"),
                "profile": state.profile,
            },
            _ctx(state),
        ))

    return fn


_STR = {"type": "string"}


def build_tool_registry(agents: dict) -> dict[str, Tool]:
    """Return tool_name → Tool, ready for the runner."""
    tools = [
        Tool("structure_request",
             "Extract a structured brief (requirements with priorities, evaluation criteria, timeline, budget, "
             "compliance, mentioned vendors, industry, solution type) from raw RFP text. Run first for proposal work.",
             {"type": "object", "properties": {"request_text": _STR, "solution_type": _STR, "industry": _STR}},
             _structure_request),
        Tool("compare_solutions",
             "Map the structured requirements to our offering catalog (or infer needed capabilities when no catalog "
             "is configured). Returns matching offerings, gaps, and positioning notes.",
             {"type": "object", "properties": {"solution_type": _STR, "requirements": {"type": "array", "items": _STR}}},
             _compare_solutions),
        Tool("retrieve_evidence",
             "Semantic search over past proposals for precedent. Use for revision or document matching; "
             "generate_proposal_sections does its own retrieval.",
             {"type": "object", "properties": {"query": _STR, "section_type": _STR, "top_k": {"type": "integer"}}},
             _retrieve_evidence),
        Tool("generate_section",
             "Write ONE proposal section. Needs structure_request first, ideally retrieve_evidence for that section.",
             {"type": "object", "properties": {"section_key": _STR}, "required": ["section_key"]},
             _generate_section),
        Tool("validate_section",
             "Check which requirements a draft addresses (semantic match, no model call).",
             {"type": "object", "properties": {"draft_text": _STR}},
             _validate_section),
        Tool("generate_proposal_sections",
             "Compound: retrieve + write + validate every requested section (parallel, cached). Preferred for "
             "proposal_generation. Reads sections from payload.target_sections by default.",
             {"type": "object", "properties": {"sections": {"type": "array", "items": _STR}}},
             _generate_proposal_sections),
        Tool("revise_section",
             "Apply the user's instruction to an existing section draft.",
             {"type": "object", "properties": {"section_key": _STR, "base_text": _STR, "instruction": _STR}},
             _revise_section),
        Tool("score_proposal",
             "Composite score of the assembled document: requirement coverage, precedent similarity, solution fit, "
             "completeness, and a rubric against the evaluation criteria.",
             {"type": "object", "properties": {"document_text": _STR}},
             _score_proposal),
        Tool("market_research",
             "Web search plus page scraping to find vendors that offer the given offerings.",
             {"type": "object", "properties": {"offerings": {"type": "array", "items": _STR}, "industry": _STR,
                                               "max_companies": {"type": "integer"}}},
             _market_research),
        Tool("detect_intent_fields",
             "Opportunity basics from a conversation: opportunity name, client, relationship, date, urgency.",
             {"type": "object", "properties": {"transcript_text": _STR}},
             _transcript_tool("detect_intent_fields", "intent_detection")),
        Tool("frame_business_problem",
             "Problem statement, success definition, stakeholder impact, and urgency from a conversation.",
             {"type": "object", "properties": {"transcript_text": _STR}},
             _transcript_tool("frame_business_problem", "problem_framing")),
        Tool("analyze_buyer_intelligence",
             "Buyer readiness score, intent, buying gaps, stakeholder coverage, and next actions.",
             {"type": "object", "properties": {"transcript_text": _STR}},
             _transcript_tool("analyze_buyer_intelligence", "buyer_intelligence")),
        Tool("analyze_product_fit",
             "Product fit score, matched capabilities, fit gaps, integration fit, competition, and positioning.",
             {"type": "object", "properties": {"transcript_text": _STR}},
             _transcript_tool("analyze_product_fit", "product_fit")),
    ]
    return {tool.name: tool for tool in tools}


def tool_catalog_for_prompt(tools: dict[str, Tool]) -> str:
    """Compact, stable tool listing for the supervisor prompt."""
    return "\n".join(f"- {t.name}: {t.description}" for t in tools.values())
