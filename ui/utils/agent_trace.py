"""Agent trace renderer — enterprise timeline visualization.

Turns the `agent_trace` list from agentic workflow responses into a polished
timeline with status dots, plan chips, confidence pills, and replan banners.
Uses the Modern Enterprise Intelligence design tokens.
"""
from __future__ import annotations

import html
from typing import Iterable, Sequence

import streamlit as st

_DECISION_TYPES = {"pick_intent", "make_plan", "decide_next", "decide_done", "replan"}
_TYPE_LABELS = {
    "pick_intent": "supervisor · intent",
    "make_plan": "supervisor · plan",
    "decide_next": "supervisor · decision",
    "decide_done": "supervisor · done",
    "replan": "supervisor · replan",
    "done": "terminator",
    "tool_call": "tool",
    "tool_error": "tool error",
    "budget_exhausted": "budget",
}
_TYPE_ICONS = {
    "pick_intent": "psychology",
    "make_plan": "account_tree",
    "decide_next": "alt_route",
    "decide_done": "task_alt",
    "replan": "refresh",
    "done": "check_circle",
    "tool_call": "build",
    "tool_error": "error",
    "budget_exhausted": "hourglass_empty",
}


def _status_class(entry: dict) -> str:
    typ = entry.get("type")
    if typ == "tool_call":
        return "tt-bad" if entry.get("ok") is False else "tt-ok"
    if typ == "tool_error":
        return "tt-bad"
    if typ in ("replan", "budget_exhausted"):
        return "tt-warn"
    if typ in _DECISION_TYPES:
        return "tt-info"
    if typ == "done":
        return "tt-ok"
    return "tt-info"


def _entry_title(entry: dict) -> str:
    typ = entry.get("type", "")
    if typ == "tool_call":
        tool = entry.get("tool", "")
        ok = entry.get("ok", True)
        status = '<span class="status-chip active" style="margin-left:6px">OK</span>' if ok else '<span class="status-chip error" style="margin-left:6px">FAIL</span>'
        return f'<span class="tt-monospace">{html.escape(tool)}</span>{status}'
    if typ == "tool_error":
        tool = entry.get("tool", "")
        return f'<span class="tt-monospace">{html.escape(tool)}</span> <span class="status-chip error">ERROR</span>'
    if typ == "pick_intent":
        intent = entry.get("intent", "")
        hint = entry.get("hint")
        suffix = f' <span style="color:var(--text-dim);font-size:0.75rem">(hint: {html.escape(str(hint))})</span>' if hint else ""
        return f'Intent detected: <span class="tt-monospace">{html.escape(intent)}</span>{suffix}'
    if typ == "make_plan":
        plan = entry.get("plan") or []
        chain = " → ".join(f'<span class="tt-monospace">{html.escape(p)}</span>' for p in plan)
        return f"Plan: {chain}" if chain else "Plan: (empty)"
    if typ == "replan":
        plan = entry.get("plan") or []
        chain = " → ".join(f'<span class="tt-monospace">{html.escape(p)}</span>' for p in plan)
        return f"Replanned: {chain}" if chain else "Replanned"
    if typ == "decide_next":
        action = entry.get("action", "")
        reason = entry.get("reason", "")
        rest = f' — <span style="color:var(--text-muted)">{html.escape(reason)}</span>' if reason else ""
        return f'Next: <span class="tt-monospace">{html.escape(action)}</span>{rest}'
    if typ == "decide_done":
        return entry.get("summary", "Workflow completed")
    if typ == "done":
        return entry.get("reason", "Workflow finished")
    return _TYPE_LABELS.get(typ, typ or "event")


def _entry_subtitle(entry: dict) -> str:
    typ = entry.get("type", "")
    if typ == "tool_call":
        bits: list[str] = []
        summary = entry.get("summary")
        if summary:
            bits.append(html.escape(str(summary)))
        if entry.get("ok") is False and entry.get("error"):
            bits.append(f'Error: {html.escape(str(entry["error"]))[:240]}')
        return " · ".join(bits)
    if typ == "tool_error":
        return html.escape(str(entry.get("error", "")))[:240]
    return ""


def render_plan_chips(
    plan_steps: Sequence[str],
    executed_tools: Iterable[str] = (),
    failed_tools: Iterable[str] = (),
) -> None:
    if not plan_steps:
        return
    executed = set(executed_tools)
    failed = set(failed_tools)
    chips: list[str] = []
    for i, step in enumerate(plan_steps):
        cls = "pipeline-step"
        if step == "done":
            cls += " done-step"
        elif step in failed:
            cls += " failed"
        elif step in executed:
            cls += " completed"
        chips.append(f'<span class="{cls}">{html.escape(step)}</span>')
        if i < len(plan_steps) - 1:
            chips.append('<span class="pipeline-arrow">→</span>')
    st.markdown(
        '<div class="plan-strip">'
        '<div class="plan-strip-label">Supervisor Execution Plan</div>'
        f'<div class="plan-strip-chips" style="display:flex;align-items:center;flex-wrap:wrap;gap:6px">{"".join(chips)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_confidence_pill(score: float | None, label: str = "Composite score") -> None:
    if score is None:
        return
    try:
        score_f = float(score)
    except (TypeError, ValueError):
        return
    tone = "good" if score_f >= 0.8 else "warn" if score_f >= 0.6 else "bad"
    st.markdown(
        f'<div class="confidence-pill confidence-{tone}">'
        f'<span class="confidence-label">{html.escape(label)}</span>'
        f'<span class="confidence-value">{score_f:.2f}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_replan_banner(replans: int, last_error: str | None = None) -> None:
    if not replans:
        return
    msg = f"Agent replanned {replans} time{'s' if replans != 1 else ''} after a failure."
    if last_error:
        msg += f" Last error: {last_error[:120]}"
    st.markdown(
        f'<div class="replan-banner">'
        f'<span class="replan-banner-icon">↻</span>'
        f'<span>{html.escape(msg)}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_thinking_indicator(label: str = "Agent is thinking...") -> None:
    st.markdown(
        f'<div class="thinking-indicator">'
        f'<div class="thinking-shimmer"></div>'
        f'<div class="thinking-label">{html.escape(label)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_agent_trace(
    trace: Sequence[dict] | None,
    *,
    title: str = "Agent Orchestration Timeline",
    expanded: bool = False,
    in_progress: bool = False,
) -> None:
    """Render the supervisor + tool trace as a vertical timeline."""
    trace = list(trace or [])
    if not trace and not in_progress:
        return

    ok_count = sum(1 for e in trace if e.get("type") == "tool_call" and e.get("ok"))
    bad_count = sum(
        1 for e in trace
        if (e.get("type") == "tool_call" and e.get("ok") is False) or e.get("type") == "tool_error"
    )
    decision_count = sum(1 for e in trace if e.get("type") in _DECISION_TYPES)

    summary_chips = (
        f'<span class="trace-summary-chip">{ok_count} successful</span>'
        f'<span class="trace-summary-chip trace-summary-bad">{bad_count} failed</span>'
        f'<span class="trace-summary-chip trace-summary-info">{decision_count} decisions</span>'
    )

    with st.expander(f"Agent Orchestration Timeline", expanded=expanded):
        st.markdown(
            f'<div class="trace-summary">{summary_chips}</div>',
            unsafe_allow_html=True,
        )
        rows_html: list[str] = []
        for entry in trace:
            typ = entry.get("type", "")
            row_class = "tt-row"
            if typ in _DECISION_TYPES:
                row_class += " tt-row-decision"
            status_cls = _status_class(entry)
            label = _TYPE_LABELS.get(typ, typ)
            title_html = _entry_title(entry)
            sub = _entry_subtitle(entry)
            sub_html = f'<div class="tt-sub">{sub}</div>' if sub else ""
            rows_html.append(
                f'<div class="{row_class}">'
                f'<div class="tt-dot {status_cls}"></div>'
                f'<div class="tt-body">'
                f'<div class="tt-meta">{html.escape(label)}</div>'
                f'<div class="tt-title">{title_html}</div>'
                f'{sub_html}'
                f'</div>'
                f'</div>'
            )
        if in_progress:
            rows_html.append(
                '<div class="tt-row tt-row-pending">'
                '<div class="tt-dot tt-pending"></div>'
                '<div class="tt-body">'
                '<div class="tt-meta">running</div>'
                '<div class="tt-title">Awaiting next supervisor decision...</div>'
                '</div>'
                '</div>'
            )
        st.markdown(
            f'<div class="agent-timeline">{"".join(rows_html)}</div>',
            unsafe_allow_html=True,
        )
