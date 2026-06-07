"""Supervisor — the LLM-driven decision layer.

Four decision functions, each backed by a strict-JSON LLM call with one
retry on parse failure and a heuristic fallback if the retry also fails:

    pick_intent  — picks the workflow intent from the payload
    make_plan    — produces the ordered list of tool calls
    decide_next  — invoked after a tool failure (replan / abort / continue)
    decide_done  — final yes/no when the plan is exhausted

Heuristic fallbacks aren't a deterministic flow — they're safety nets that
only fire when the local LLM emits unparseable output. When Qwen works
(the common case), every decision goes through the model.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agentic.state import WorkflowState
from app.agentic.tools import Tool, tool_catalog_for_prompt
from app.services.llm_service import LLMService, LLMServiceError


_VALID_INTENTS = (
    "proposal_generation",
    "revision",
    "document_match",
    "market_research",
    "intent_detection",
)


# ── JSON parsing ───────────────────────────────────────────────────────────
def _parse_json(raw: str) -> Any:
    if not raw:
        return None
    candidate = raw.strip()
    # Drop common ```json fences
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).rstrip("`").strip()
    # Find the outermost { ... } or [ ... ]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _llm_json_call(
    llm: LLMService,
    prompt: str,
    *,
    system: str = "You output strict JSON only. No prose.",
    max_tokens: int = 350,
) -> Any:
    """One LLM call with one retry on JSON parse failure."""
    try:
        raw = llm.generate(prompt=prompt, system=system, temperature=0.0, max_tokens=max_tokens)
    except LLMServiceError:
        return None
    parsed = _parse_json(raw)
    if parsed is not None:
        return parsed
    fix_prompt = (
        "Your previous response was not valid JSON:\n\n"
        f"{raw}\n\nReturn ONLY the JSON object that matches the original schema. JSON:"
    )
    try:
        raw2 = llm.generate(prompt=fix_prompt, system=system, temperature=0.0, max_tokens=max_tokens)
    except LLMServiceError:
        return None
    return _parse_json(raw2)


# ── pick_intent ────────────────────────────────────────────────────────────
def _heuristic_intent(payload: dict, hint: str | None) -> str:
    if hint in _VALID_INTENTS:
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


def pick_intent(state: WorkflowState, llm: LLMService) -> str:
    payload = state.payload or {}
    hint = state.intent_hint
    keys = sorted(payload.keys())
    sample_request = (payload.get("request_text") or "")[:160]
    prompt = (
        f"Pick the workflow intent. Allowed values: {list(_VALID_INTENTS)}.\n"
        f'Endpoint hint (may be wrong): {hint!r}\n'
        f"Payload keys present: {keys}\n"
        f"request_text sample: {sample_request!r}\n"
        f"transcript_text present: {bool(payload.get('transcript_text'))}\n"
        f"document_text present: {bool(payload.get('document_text'))}\n"
        f"offerings present: {bool(payload.get('offerings'))}\n"
        f'instruction present: {bool(payload.get("instruction"))}\n\n'
        'Respond with JSON: {"intent": "<one of the allowed values>"}'
    )
    parsed = _llm_json_call(llm, prompt, max_tokens=80)
    if isinstance(parsed, dict):
        candidate = str(parsed.get("intent", "")).strip().lower()
        if candidate in _VALID_INTENTS:
            return candidate
    return _heuristic_intent(payload, hint)


# ── make_plan ──────────────────────────────────────────────────────────────
def _fallback_plan(intent: str, state: WorkflowState) -> list[dict]:
    """Hard-coded plan templates per intent — only used if LLM plan fails to parse."""
    if intent == "proposal_generation":
        return [
            {"tool": "structure_request", "args": {}},
            {"tool": "compare_solutions", "args": {}},
            {"tool": "generate_proposal_sections", "args": {}},
            {"tool": "score_proposal", "args": {}},
            {"tool": "done", "args": {"summary": "Proposal generated."}},
        ]
    if intent == "revision":
        return [
            {"tool": "retrieve_evidence", "args": {"section_type": "implementation_plan", "top_k": 5}},
            {"tool": "revise_section", "args": {}},
            {"tool": "done", "args": {"summary": "Section revised."}},
        ]
    if intent == "document_match":
        return [
            {"tool": "structure_request", "args": {}},
            {"tool": "retrieve_evidence", "args": {"top_k": 5}},
            {"tool": "compare_solutions", "args": {}},
            {"tool": "score_proposal", "args": {"retrieval_score_hint": 0.75}},
            {"tool": "done", "args": {"summary": "Document scored against request."}},
        ]
    if intent == "market_research":
        return [
            {"tool": "market_research", "args": {}},
            {"tool": "done", "args": {"summary": "Market research completed."}},
        ]
    if intent == "intent_detection":
        return [
            {"tool": "detect_intent_fields", "args": {}},
            {"tool": "frame_business_problem", "args": {}},
            {"tool": "analyze_buyer_intelligence", "args": {}},
            {"tool": "analyze_product_fit", "args": {}},
            {"tool": "done", "args": {"summary": "Intent, problem framing, buyer intelligence, and product fit extracted."}},
        ]
    return [{"tool": "done", "args": {"summary": "No plan available."}}]


def _validate_plan(steps: list[dict], tools: dict[str, Tool]) -> list[dict]:
    """Drop unknown tools, ensure plan ends with done, cap length."""
    cleaned: list[dict] = []
    for raw in steps[:10]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("tool", "")).strip()
        args = raw.get("args", {})
        if not isinstance(args, dict):
            args = {}
        if name == "done" or name in tools:
            cleaned.append({"tool": name, "args": args})
    if not cleaned or cleaned[-1]["tool"] != "done":
        cleaned.append({"tool": "done", "args": {"summary": "Workflow completed."}})
    return cleaned


def make_plan(state: WorkflowState, llm: LLMService, tools: dict[str, Tool]) -> list[dict]:
    intent = state.intent or "proposal_generation"
    catalog = tool_catalog_for_prompt(tools)
    payload = state.payload or {}
    payload_keys = sorted(payload.keys())
    prior_results = sorted(state.results.keys())

    intent_examples = {
        "proposal_generation": (
            '[{"tool":"structure_request","args":{}},'
            '{"tool":"compare_solutions","args":{}},'
            '{"tool":"generate_proposal_sections","args":{}},'
            '{"tool":"score_proposal","args":{}},'
            '{"tool":"done","args":{"summary":"Proposal generated."}}]'
        ),
        "revision": (
            '[{"tool":"retrieve_evidence","args":{}},'
            '{"tool":"revise_section","args":{}},'
            '{"tool":"done","args":{"summary":"Section revised."}}]'
        ),
        "document_match": (
            '[{"tool":"structure_request","args":{}},'
            '{"tool":"retrieve_evidence","args":{}},'
            '{"tool":"compare_solutions","args":{}},'
            '{"tool":"score_proposal","args":{}},'
            '{"tool":"done","args":{"summary":"Document scored."}}]'
        ),
        "market_research": (
            '[{"tool":"market_research","args":{}},'
            '{"tool":"done","args":{"summary":"Market research completed."}}]'
        ),
        "intent_detection": (
            '[{"tool":"detect_intent_fields","args":{}},'
            '{"tool":"frame_business_problem","args":{}},'
            '{"tool":"analyze_buyer_intelligence","args":{}},'
            '{"tool":"analyze_product_fit","args":{}},'
            '{"tool":"done","args":{"summary":"Intent, problem framing, buyer intelligence, and product fit extracted."}}]'
        ),
    }
    example = intent_examples.get(intent, "")
    prompt = (
        f"You are an agentic workflow planner. Intent: {intent}.\n\n"
        "AVAILABLE TOOLS:\n"
        f"{catalog}\n"
        '- done: terminator. args={"summary":"<short>"}\n\n'
        f"Payload keys: {payload_keys}\n"
        f"Tools already executed: {prior_results}\n\n"
        "RULES:\n"
        "- Use the FEWEST tools needed for this intent. Do NOT chain unrelated tools.\n"
        "- Do NOT call generate_proposal_sections unless the intent is proposal_generation.\n"
        "- Args can be {} — tools auto-fill from prior results.\n"
        "- Always end with the done tool.\n\n"
        f"Reference plan for this intent (you may copy or adjust): {example}\n\n"
        'Respond with JSON: {"steps": [{"tool":"<name>","args":{...}}, ...]}'
    )
    parsed = _llm_json_call(llm, prompt, max_tokens=420)
    if isinstance(parsed, dict) and isinstance(parsed.get("steps"), list):
        return _validate_plan(parsed["steps"], tools)
    return _fallback_plan(intent, state)


# ── decide_next (after tool failure) ───────────────────────────────────────
def decide_next(state: WorkflowState, llm: LLMService, tools: dict[str, Tool]) -> dict:
    if state.replans >= state.max_replans:
        return {"action": "abort", "reason": "max replans exhausted"}
    error = state.last_error or "unknown error"
    last_tool = state.trace[-1].get("tool", "") if state.trace else ""
    pending = [s.get("tool") for s in state.plan]
    prompt = (
        f"A tool just failed in an agentic workflow.\n"
        f"Intent: {state.intent}\n"
        f"Last tool: {last_tool}\n"
        f"Error: {error}\n"
        f"Pending plan: {pending}\n\n"
        'Decide: {"action": "replan"} to redo the plan, '
        '{"action": "continue"} to skip the failed step and keep going, '
        '{"action": "abort", "reason": "<short>"} to stop.\n\n'
        "JSON:"
    )
    parsed = _llm_json_call(llm, prompt, max_tokens=120)
    if isinstance(parsed, dict):
        action = str(parsed.get("action", "")).strip().lower()
        if action in ("replan", "continue", "abort"):
            return {"action": action, "reason": parsed.get("reason", "")}
    return {"action": "continue", "reason": "fallback: skip failed step"}


# ── decide_done ────────────────────────────────────────────────────────────
def decide_done(state: WorkflowState, llm: LLMService) -> dict:
    summaries = state.tool_summaries()[-6:]
    prompt = (
        f"Intent: {state.intent}\n"
        f"Steps executed:\n" + "\n".join(f"- {s}" for s in summaries) + "\n\n"
        'Is the workflow complete and acceptable? '
        'Respond with JSON: {"done": true|false, "summary": "<one short sentence>"}'
    )
    parsed = _llm_json_call(llm, prompt, max_tokens=100)
    if isinstance(parsed, dict) and "done" in parsed:
        return {
            "done": bool(parsed["done"]),
            "summary": str(parsed.get("summary", "Workflow completed.")),
        }
    return {"done": True, "summary": "Workflow completed (fallback)."}
