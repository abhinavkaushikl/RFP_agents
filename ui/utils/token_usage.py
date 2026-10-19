"""Token consumption report: totals, then breakdowns by section, agent, and model."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.theme import render_section_header, render_stat_card

_COLUMNS = {
    "model_calls": "Model calls",
    "cache_hits": "Cache hits",
    "prompt_tokens": "Prompt",
    "cached_prompt_tokens": "Prompt cached",
    "completion_tokens": "Completion",
    "reasoning_tokens": "Reasoning",
    "total_tokens": "Total tokens",
    "saved_tokens": "Tokens saved",
    "cost_usd": "Cost (USD)",
    "latency_ms": "Latency (ms)",
}


def _fmt_int(value) -> str:
    return f"{int(value or 0):,}"


def _table(rows: list[dict], label_key: str, label: str) -> None:
    if not rows:
        st.caption("Nothing recorded.")
        return
    df = pd.DataFrame(rows)
    keep = [label_key] + [c for c in _COLUMNS if c in df.columns]
    if "tier" in df.columns and label_key == "model":
        keep.insert(1, "tier")
    df = df[keep].rename(columns={label_key: label, **_COLUMNS, "tier": "Tier"})
    if "Cost (USD)" in df.columns:
        df["Cost (USD)"] = df["Cost (USD)"].map(lambda v: f"${float(v):.5f}")
    st.dataframe(df, hide_index=True, use_container_width=True)


def render_token_usage(report: dict | None, *, title: str = "Token Usage", expanded: bool = False) -> None:
    if not report or not report.get("totals"):
        return
    totals = report["totals"]
    render_section_header(title, icon="data_usage", badge=f"{totals.get('calls', 0)} calls")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_stat_card("Total tokens", _fmt_int(totals.get("total_tokens")), icon="token",
                         sub=f"{_fmt_int(totals.get('prompt_tokens'))} in · {_fmt_int(totals.get('completion_tokens'))} out")
    with c2:
        render_stat_card("Est. cost", f"${float(totals.get('cost_usd') or 0):.4f}", icon="payments",
                         sub="Groq list prices")
    with c3:
        rate = float(totals.get("prompt_cache_rate") or 0) * 100
        render_stat_card("Prompt cache", f"{rate:.0f}%", icon="bolt",
                         sub=f"{_fmt_int(totals.get('cached_prompt_tokens'))} cached input tokens")
    with c4:
        render_stat_card("Section cache", _fmt_int(totals.get("cache_hits")), icon="cached",
                         sub=f"{_fmt_int(totals.get('saved_tokens'))} tokens saved")
    with c5:
        render_stat_card("Model calls", _fmt_int(totals.get("model_calls")), icon="smart_toy",
                         sub=f"{_fmt_int(totals.get('errors'))} errors")

    with st.expander("Breakdown by section, agent, and model", expanded=expanded):
        tabs = st.tabs(["By section", "By agent", "By model", "By tool", "Every call"])
        with tabs[0]:
            _table(report.get("by_section", []), "section_key", "Section")
        with tabs[1]:
            _table(report.get("by_agent", []), "agent", "Agent")
        with tabs[2]:
            _table(report.get("by_model", []), "model", "Model")
        with tabs[3]:
            _table(report.get("by_tool", []), "tool", "Tool")
        with tabs[4]:
            calls = report.get("calls") or []
            if calls:
                df = pd.DataFrame(calls)
                cols = [c for c in ("agent", "tool", "section_key", "model", "purpose", "status", "cache_hit",
                                    "prompt_tokens", "cached_prompt_tokens", "completion_tokens", "total_tokens",
                                    "cost_usd", "latency_ms") if c in df.columns]
                st.dataframe(df[cols], hide_index=True, use_container_width=True)
            else:
                st.caption("Per-call detail is not included in this report.")


def accumulate_session_usage(report: dict | None) -> None:
    """Keep running totals for the dashboard."""
    if not report or not report.get("totals"):
        return
    totals = st.session_state.setdefault("session_usage", {})
    for key in ("total_tokens", "cost_usd", "cached_prompt_tokens", "prompt_tokens", "cache_hits", "saved_tokens", "model_calls"):
        totals[key] = totals.get(key, 0) + (report["totals"].get(key) or 0)
