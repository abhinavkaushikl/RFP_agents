"""Plan-Execute runner.

    pick_intent → make_plan → loop { exec step → on failure ask supervisor } → done

Every model call inside the run is captured in `state.usage`; each `tool_call`
trace entry carries the tokens and cost that tool consumed.
"""
from __future__ import annotations

from typing import Any

from app.agentic import supervisor
from app.agentic.state import WorkflowState
from app.agentic.tools import Tool
from app.core.config import get_settings
from app.core.logging import workflow_id_var
from app.llm.service import LLMService
from app.llm.usage import cache_policy, usage_run


def _delta(before: dict, after: dict) -> dict:
    keys = ("total_tokens", "cached_prompt_tokens", "saved_tokens", "model_calls", "cache_hits")
    out = {k: int(after.get(k, 0)) - int(before.get(k, 0)) for k in keys}
    out["cost_usd"] = round(float(after.get("cost_usd", 0.0)) - float(before.get("cost_usd", 0.0)), 6)
    return out


def _handle_failure(state: WorkflowState, llm: LLMService, tools: dict[str, Tool]) -> bool:
    """Ask the supervisor what to do after a failure. Returns False to stop the loop."""
    decision = supervisor.decide_next(state, llm, tools)
    state.add_trace(type="decide_next", **decision)
    if decision["action"] == "replan" and state.replans < state.max_replans:
        state.replans += 1
        state.plan, how = supervisor.make_plan(state, llm, tools)
        state.add_trace(type="replan", plan=[s["tool"] for s in state.plan], how=how)
    elif decision["action"] == "abort":
        return False
    return True


def run_agentic(
    payload: dict[str, Any],
    *,
    intent_hint: str | None,
    agents: dict[str, Any],
    tools: dict[str, Tool],
    llm: LLMService,
    budget: int | None = None,
    workflow_id: str | None = None,
) -> WorkflowState:
    settings = get_settings()
    state = WorkflowState(
        payload=payload,
        intent_hint=intent_hint,
        budget=budget or settings.agent_budget,
        max_replans=settings.agent_max_replans,
    )
    if workflow_id:
        state.workflow_id = workflow_id
    wf_token = workflow_id_var.set(state.workflow_id)
    try:
        with usage_run(state.workflow_id) as usage, cache_policy(payload.get("cache_policy")):
            state.usage = usage
            _execute(state, agents, tools, llm)
    finally:
        workflow_id_var.reset(wf_token)
    return state


def _execute(state: WorkflowState, agents: dict[str, Any], tools: dict[str, Tool], llm: LLMService) -> None:
    usage = state.usage
    state.intent, how = supervisor.pick_intent(state, llm)
    state.add_trace(type="pick_intent", intent=state.intent, hint=state.intent_hint, how=how)

    state.plan, how = supervisor.make_plan(state, llm, tools)
    state.add_trace(type="make_plan", plan=[s["tool"] for s in state.plan], how=how)

    while not state.done and state.steps_taken < state.budget and state.plan:
        step = state.plan.pop(0)
        tool_name = str(step.get("tool", ""))
        args = step.get("args", {}) or {}

        if tool_name == "done":
            state.done = True
            state.final_summary = str(args.get("summary") or "Workflow completed.")
            state.add_trace(type="done", reason=state.final_summary)
            break

        tool = tools.get(tool_name)
        if tool is None:
            state.last_error = f"unknown tool: {tool_name}"
            state.add_trace(type="tool_error", tool=tool_name, error=state.last_error)
            if not _handle_failure(state, llm, tools):
                break
            continue

        before = usage.totals() if usage else {}
        result = tool.fn(args, state, agents)
        after = usage.totals() if usage else {}
        state.results[tool_name] = result
        state.steps_taken += 1
        state.add_trace(
            type="tool_call",
            tool=tool_name,
            ok=bool(result.get("ok")),
            summary=result.get("summary", ""),
            error=result.get("error"),
            usage=_delta(before, after),
        )
        if not result.get("ok"):
            state.last_error = result.get("error")
            if not _handle_failure(state, llm, tools):
                break

    if not state.done:
        if state.steps_taken >= state.budget:
            state.add_trace(type="budget_exhausted")
        decision = supervisor.decide_done(state, llm)
        state.done = decision["done"]
        state.final_summary = decision["summary"]
        state.add_trace(type="decide_done", **decision)
