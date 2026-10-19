"""Token Usage — model consumption, cache savings, and cost across workflows."""
import pandas as pd
import streamlit as st

from utils.theme import (
    apply_theme,
    render_empty_state,
    render_header,
    render_section_header,
    render_sidebar,
    render_stat_card,
)

st.set_page_config(page_title="Token Usage · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Token Usage")

from utils.api_client import APIError, get_usage_summary, get_workflow_usage  # noqa: E402
from utils.token_usage import render_token_usage  # noqa: E402

st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Observability</div>
        <h1 class="rfp-title">Token Usage and Cost</h1>
        <p class="rfp-copy">
            Every model call is recorded with prompt, cached, completion, and reasoning tokens. Section cache
            hits show the tokens they saved. Costs use Groq list prices from the API configuration.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

days = st.select_slider("Period", options=[1, 7, 30, 90], value=7, format_func=lambda d: f"Last {d} day{'s' if d > 1 else ''}")
try:
    summary = get_usage_summary(days)
except APIError as exc:
    st.error(f"Could not load usage: {exc}")
    st.stop()
except Exception as exc:  # noqa: BLE001
    st.error(f"API unreachable: {exc}")
    st.stop()

if not summary.get("totals", {}).get("calls"):
    render_empty_state("No usage yet", "Run a workflow to see token consumption here.", icon="data_usage")
else:
    t = summary["totals"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat_card("Workflows", f"{summary.get('workflows', 0):,}", icon="account_tree")
    with c2:
        render_stat_card("Tokens", f"{t['total_tokens']:,}", icon="token", sub=f"{t['model_calls']:,} model calls")
    with c3:
        render_stat_card("Est. cost", f"${t['cost_usd']:.4f}", icon="payments",
                         sub=f"${t['saved_cost_usd']:.4f} saved by the section cache")
    with c4:
        render_stat_card("Prompt cache rate", f"{t['prompt_cache_rate'] * 100:.0f}%", icon="bolt",
                         sub=f"{t['cached_prompt_tokens']:,} cached input tokens")

    by_day = pd.DataFrame(summary.get("by_day", []))
    if not by_day.empty:
        render_section_header("Tokens per day", icon="show_chart")
        st.bar_chart(by_day.set_index("day")[["total_tokens"]], height=220)

    render_token_usage({**summary, "calls": []}, title="Breakdown", expanded=True)
    types = summary.get("by_workflow_type") or []
    if types:
        render_section_header("By workflow type", icon="category")
        st.dataframe(pd.DataFrame(types)[["workflow_type", "calls", "total_tokens", "cost_usd", "cache_hits", "saved_tokens"]],
                     hide_index=True, use_container_width=True)

render_section_header("Look up one workflow", icon="search")
workflow_id = st.text_input("Workflow id", placeholder="Paste a workflow id from any results page")
if workflow_id.strip():
    try:
        render_token_usage(get_workflow_usage(workflow_id.strip()), title="Workflow usage", expanded=True)
    except APIError as exc:
        st.warning(str(exc))
