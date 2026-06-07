"""Plan-Execute runner.

    pick_intent → make_plan → loop { exec step → on failure ask supervisor }
    → done

Replanning is bounded by `state.max_replans`; total tool calls by `state.budget`.
Tools never raise (they wrap errors as `{"ok": False, ...}`), so the loop
itself doesn't need broad try/except.
"""
from __future__ import annotations

from typing import Any

from app.agentic import supervisor
from app.agentic.state import WorkflowState
from app.agentic.tools import Tool
from app.services.llm_service import LLMService


def run_agentic(
    payload: dict[str, Any],
    *,
    intent_hint: str | None,
    agents: dict[str, Any],
    tools: dict[str, Tool],
    llm: LLMService,
    budget: int = 12,
) -> WorkflowState:
    """Execute a fully agentic workflow and return the resulting state."""
    state = WorkflowState(payload=payload, intent_hint=intent_hint, budget=budget)

    # Phase 1: pick intent
    state.intent = supervisor.pick_intent(state, llm)
    state.add_trace(type="pick_intent", intent=state.intent, hint=intent_hint)

    # Phase 2: initial plan
    state.plan = supervisor.make_plan(state, llm, tools)
    state.add_trace(type="make_plan", plan=[s["tool"] for s in state.plan])

    # Phase 3: execute
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
            decision = supervisor.decide_next(state, llm, tools)
            state.add_trace(type="decide_next", **decision)
            if decision["action"] == "replan" and state.replans < state.max_replans:
                state.replans += 1
                state.plan = supervisor.make_plan(state, llm, tools)
                state.add_trace(type="replan", plan=[s["tool"] for s in state.plan])
            elif decision["action"] == "abort":
                break
            continue

        result = tool.fn(args, state, agents)
        state.results[tool_name] = result
        state.steps_taken += 1
        state.add_trace(
            type="tool_call",
            tool=tool_name,
            ok=bool(result.get("ok")),
            summary=result.get("summary", ""),
            error=result.get("error"),
        )

        if not result.get("ok"):
            state.last_error = result.get("error")
            decision = supervisor.decide_next(state, llm, tools)
            state.add_trace(type="decide_next", **decision)
            if decision["action"] == "replan" and state.replans < state.max_replans:
                state.replans += 1
                state.plan = supervisor.make_plan(state, llm, tools)
                state.add_trace(type="replan", plan=[s["tool"] for s in state.plan])
            elif decision["action"] == "abort":
                break

    if not state.done:
        if state.steps_taken >= state.budget:
            state.add_trace(type="budget_exhausted")
        decision = supervisor.decide_done(state, llm)
        state.done = decision["done"]
        state.final_summary = decision["summary"]
        state.add_trace(type="decide_done", **decision)

    return state
