"""Supervisor: the model-driven decision layer (fast tier).

    pick_intent  — which workflow the payload needs (skipped when the endpoint already says)
    make_plan    — the ordered tool calls
    decide_next  — after a tool failure: replan / continue / abort
    decide_done  — final check when the plan runs out without `done`

Each decision is a strict-JSON call with a deterministic fallback. Prompts put
the static part (rules, tool catalog, reference plans) in the system message so
Groq can cache it across runs; per-run facts go in the user message.
"""
from __future__ import annotations

import json
from typing import Any

from app.agentic.state import WorkflowState
from app.agentic.tools import Tool, tool_catalog_for_prompt
from app.agents.schema import BOOL, STR, arr, enum, obj
from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.errors import LLMAuthError, LLMConfigurationError, LLMServiceError
from app.llm.service import LLMService

logger = get_logger(__name__)

VALID_INTENTS = (
    "proposal_generation",
    "revision",
    "document_match",
    "market_research",
    "intent_detection",
)

REFERENCE_PLANS: dict[str, list[str]] = {
    "proposal_generation": ["structure_request", "compare_solutions", "generate_proposal_sections", "score_proposal"],
    "revision": ["retrieve_evidence", "revise_section", "validate_section"],
    "document_match": ["structure_request", "retrieve_evidence", "compare_solutions", "score_proposal"],
    "market_research": ["market_research"],
    "intent_detection": ["detect_intent_fields", "frame_business_problem", "analyze_buyer_intelligence", "analyze_product_fit"],
}

# A plan must contain every tool in `all_of` and at least one tool of each `any_of` group.
_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "proposal_generation": {"all_of": {"structure_request"}, "any_of": [{"generate_proposal_sections", "generate_section"}]},
    "revision": {"all_of": {"revise_section"}, "any_of": []},
    "document_match": {"all_of": {"structure_request", "score_proposal"}, "any_of": []},
    "market_research": {"all_of": {"market_research"}, "any_of": []},
    "intent_detection": {"all_of": set(REFERENCE_PLANS["intent_detection"]), "any_of": []},
}

_DONE_SUMMARIES = {
    "proposal_generation": "Proposal generated.",
    "revision": "Section revised.",
    "document_match": "Document scored against the request.",
    "market_research": "Market research completed.",
    "intent_detection": "Conversation analyzed.",
}

_FATAL = (LLMConfigurationError, LLMAuthError)


def _json_call(llm: LLMService, *, system: str, prompt: str, schema: dict, name: str, purpose: str) -> dict | None:
    try:
        return llm.complete_json(
            agent="supervisor",
            system=system,
            prompt=prompt,
            schema=schema,
            schema_name=name,
            purpose=purpose,
            max_tokens=1500,
            expected_tokens=250,
            reasoning_effort="low",
        ).parsed
    except _FATAL:
        raise
    except LLMServiceError as exc:
        logger.warning("Supervisor %s fell back to the default: %s", purpose, exc)
        return None


# ── pick_intent ────────────────────────────────────────────────────────
def _heuristic_intent(payload: dict, hint: str | None) -> str:
    if hint in VALID_INTENTS:
        return hint
    if payload.get("transcript_text"):
        return "intent_detection"
    if payload.get("offerings") and not payload.get("request_text"):
        return "market_research"
    if payload.get("document_text"):
        return "document_match"
    if payload.get("instruction") and (payload.get("base_section") or payload.get("base_text")):
        return "revision"
    return "proposal_generation"


_INTENT_SYSTEM = (
    "You route requests in a proposal platform. Choose the workflow intent from: "
    + ", ".join(VALID_INTENTS)
    + ". proposal_generation drafts a new response from RFP text; revision edits an existing section; "
    "document_match scores an existing response against an RFP; market_research finds vendors for offerings; "
    "intent_detection analyzes a sales conversation. The endpoint hint is usually right. Return JSON only."
)


def pick_intent(state: WorkflowState, llm: LLMService) -> tuple[str, str]:
    """Return (intent, how) where how is 'endpoint', 'model', or 'fallback'."""
    payload = state.payload or {}
    hint = state.intent_hint
    if hint in VALID_INTENTS and get_settings().supervisor_trust_endpoint_intent:
        return hint, "endpoint"
    prompt = (
        f"Endpoint hint: {hint!r}\n"
        f"Payload keys: {sorted(payload.keys())}\n"
        f"request_text sample: {(payload.get('request_text') or '')[:200]!r}"
    )
    parsed = _json_call(
        llm, system=_INTENT_SYSTEM, prompt=prompt,
        schema=obj(intent=enum(*VALID_INTENTS)), name="intent", purpose="pick_intent",
    )
    if parsed and parsed.get("intent") in VALID_INTENTS:
        return parsed["intent"], "model"
    return _heuristic_intent(payload, hint), "fallback"


# ── make_plan ──────────────────────────────────────────────────────────
def _fallback_plan(intent: str) -> list[dict]:
    steps = [{"tool": name, "args": {}} for name in REFERENCE_PLANS.get(intent, [])]
    return steps + [{"tool": "done", "args": {"summary": _DONE_SUMMARIES.get(intent, "Workflow completed.")}}]


def _validate_plan(steps: list[dict], tools: dict[str, Tool]) -> list[dict]:
    cleaned: list[dict] = []
    for raw in steps[:10]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("tool", "")).strip()
        args = raw.get("args")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        if name == "done":
            cleaned.append({"tool": "done", "args": args})
            break
        if name in tools:
            cleaned.append({"tool": name, "args": args})
    if not cleaned or cleaned[-1]["tool"] != "done":
        cleaned.append({"tool": "done", "args": {"summary": "Workflow completed."}})
    return cleaned


def plan_satisfies(intent: str, tool_names: list[str]) -> bool:
    rule = _REQUIREMENTS.get(intent)
    if not rule:
        return True
    names = set(tool_names)
    return rule["all_of"] <= names and all(names & group for group in rule["any_of"])


def _plan_system(tools: dict[str, Tool]) -> str:
    refs = "\n".join(f"- {intent}: {' → '.join(plan)} → done" for intent, plan in REFERENCE_PLANS.items())
    return (
        "You are the planner of an agentic proposal platform. Produce the ordered list of tool calls for the intent.\n\n"
        "AVAILABLE TOOLS:\n"
        f"{tool_catalog_for_prompt(tools)}\n"
        "- done: terminator; args {\"summary\": \"<short>\"}\n\n"
        "RULES:\n"
        "- Use the fewest tools the intent needs; never chain tools from another intent.\n"
        "- Tools auto-fill arguments from earlier results; pass args only to override (as a JSON object string, or \"{}\").\n"
        "- Skip tools listed as already executed unless they failed.\n"
        "- Always end with done.\n\n"
        "REFERENCE PLANS (copy unless the payload needs something different):\n"
        f"{refs}\n"
        "Return JSON only."
    )


_PLAN_SCHEMA = obj(steps=arr(obj(tool=STR, args=STR)))


def make_plan(state: WorkflowState, llm: LLMService, tools: dict[str, Tool]) -> tuple[list[dict], str]:
    """Return (plan, how) where how is 'model' or 'reference'."""
    intent = state.intent or "proposal_generation"
    if not get_settings().supervisor_llm_planning:
        return _fallback_plan(intent), "reference"
    executed_ok = [name for name, res in state.results.items() if res.get("ok")]
    failed = state.failed_tools()
    prompt = (
        f"Intent: {intent}\n"
        f"Payload keys: {sorted((state.payload or {}).keys())}\n"
        f"Target sections: {(state.payload or {}).get('target_sections') or 'profile defaults'}\n"
        f"Already executed: {executed_ok}\n"
        f"Failed so far: {failed}\n"
        f"Last error: {state.last_error or 'none'}"
    )
    parsed = _json_call(llm, system=_plan_system(tools), prompt=prompt, schema=_PLAN_SCHEMA, name="plan", purpose="make_plan")
    if parsed and isinstance(parsed.get("steps"), list):
        plan = _validate_plan(parsed["steps"], tools)
        names = [s["tool"] for s in plan] + executed_ok
        if plan_satisfies(intent, names):
            return plan, "model"
        logger.info("Model plan for %s missed required tools; using the reference plan", intent)
    plan = _fallback_plan(intent)
    if executed_ok:
        plan = [s for s in plan if s["tool"] not in executed_ok or s["tool"] == "done"]
    return plan, "reference"


# ── decide_next ────────────────────────────────────────────────────────
_NEXT_SYSTEM = (
    "A tool failed in an agentic proposal workflow. Decide: \"replan\" to build a new plan, \"continue\" to skip "
    "the failed step, or \"abort\" to stop. Abort when the failure makes the result meaningless (for example the "
    "request could not be structured); continue when later steps can still produce a useful result. Return JSON only."
)


def decide_next(state: WorkflowState, llm: LLMService, tools: dict[str, Tool]) -> dict:
    if state.replans >= state.max_replans:
        return {"action": "abort", "reason": "max replans exhausted", "how": "rule"}
    last_tool = state.trace[-1].get("tool", "") if state.trace else ""
    prompt = (
        f"Intent: {state.intent}\nFailed tool: {last_tool}\nError: {state.last_error or 'unknown'}\n"
        f"Remaining plan: {[s.get('tool') for s in state.plan]}"
    )
    parsed = _json_call(
        llm, system=_NEXT_SYSTEM, prompt=prompt,
        schema=obj(action=enum("replan", "continue", "abort"), reason=STR), name="next_action", purpose="decide_next",
    )
    if parsed and parsed.get("action") in ("replan", "continue", "abort"):
        return {"action": parsed["action"], "reason": parsed.get("reason", ""), "how": "model"}
    return {"action": "continue", "reason": "fallback: skip failed step", "how": "fallback"}


# ── decide_done ────────────────────────────────────────────────────────
_DONE_SYSTEM = (
    "Decide whether an agentic proposal workflow produced an acceptable result from the steps it ran. "
    "Return JSON with done (boolean) and a one-sentence summary."
)


def decide_done(state: WorkflowState, llm: LLMService) -> dict:
    summaries = state.tool_summaries()[-8:]
    if not state.failed_tools() and summaries:
        return {"done": True, "summary": _DONE_SUMMARIES.get(state.intent or "", "Workflow completed."), "how": "rule"}
    prompt = f"Intent: {state.intent}\nSteps executed:\n" + "\n".join(f"- {s}" for s in summaries)
    parsed = _json_call(
        llm, system=_DONE_SYSTEM, prompt=prompt,
        schema=obj(done=BOOL, summary=STR), name="done_check", purpose="decide_done",
    )
    if parsed and "done" in parsed:
        return {"done": bool(parsed["done"]), "summary": str(parsed.get("summary") or "Workflow completed."), "how": "model"}
    return {"done": bool(summaries), "summary": "Workflow completed (fallback).", "how": "fallback"}
