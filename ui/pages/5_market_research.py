"""Market Research — find vendors offering matching solutions via web search."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.api_client import APIError, run_market_research
from utils.profile import active_profile_name, get_active_profile
from utils.token_usage import accumulate_session_usage, render_token_usage
from utils.theme import (
    apply_theme,
    render_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Market Research · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Market Research")

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Competitive Intelligence</div>
        <h1 class="rfp-title">Market Research</h1>
        <p class="rfp-copy">
            Enter the offerings you care about. The market research agent searches the public web,
            collapses overlapping hits into one row per company, and enriches each with
            pricing, review, and founding-year signals.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

_PROFILE = get_active_profile()
DEFAULT_OFFERINGS = list(_PROFILE.get("market_research", {}).get("default_offerings") or [])
DEFAULT_OFFERINGS += [o["name"] for o in _PROFILE.get("offerings", []) if o["name"] not in DEFAULT_OFFERINGS]

with st.form("market_research_form"):
    col1, col2 = st.columns([0.55, 0.45], gap="large")
    with col1:
        render_section_header("Offerings", icon="category")
        offerings_picked = st.multiselect(
            "Select Offerings",
            options=DEFAULT_OFFERINGS,
            default=DEFAULT_OFFERINGS[:2],
            help="Suggestions come from the active domain profile. Pick two or more to also find vendors that bundle them.",
        ) if DEFAULT_OFFERINGS else []
        custom_offerings = st.text_input(
            "Custom Offerings (comma-separated)",
            value="",
            placeholder="e.g., e-signature platform, field service management",
        )
        requirement_summary = st.text_area(
            "Requirement Summary (optional)",
            value="", height=100,
            placeholder="Short note on the use case — used to refine queries.",
        )
    with col2:
        render_section_header("Filters", icon="tune")
        industry = st.selectbox(
            "Industry (optional)",
            options=["", *_PROFILE.get("industries", [])],
            index=0,
        )
        max_companies = st.slider("Max Companies", 4, 15, value=8)
        st.markdown(
            '<div style="font-size:0.78rem;color:var(--text-muted);margin-top:0.3rem">'
            'DuckDuckGo rate-limits free search. Larger values take longer.</div>',
            unsafe_allow_html=True,
        )

    submitted = st.form_submit_button("Run Market Research", use_container_width=True)


def _merge_offerings() -> list[str]:
    extra = [o.strip() for o in (custom_offerings or "").split(",") if o.strip()]
    seen: list[str] = []
    for o in [*offerings_picked, *extra]:
        if o and o not in seen:
            seen.append(o)
    return seen


if submitted:
    final_offerings = _merge_offerings()
    if not final_offerings:
        st.warning("Pick or type at least one offering to research.")
        st.stop()

    with st.spinner(f"Searching the web for {len(final_offerings)} offering(s)..."):
        try:
            result = run_market_research(
                offerings=final_offerings,
                requirement_summary=requirement_summary.strip(),
                industry=industry or None,
                max_companies=max_companies,
                profile=active_profile_name(),
            )
        except APIError as exc:
            st.error(f"Research failed: {exc}")
            st.stop()
        except Exception as exc:
            st.error(f"Research failed: {exc}")
            st.stop()

    rows = result.get("rows", [])
    if not rows:
        from utils.theme import render_empty_state
        render_empty_state(
            "No companies found",
            "Try broader offerings or remove the industry filter.",
            icon="search_off",
        )
        st.stop()

    st.success(result.get("summary", f"Found {len(rows)} companies."))

    # ── Results table ───────────────────────────────────────────────────
    render_section_header("Vendor Analysis", icon="business", badge=f"{len(rows)} found")

    df = pd.DataFrame(rows)
    display_cols = ["Company", "Matched solutions", "Price", "Review", "Contact", "Age (years)", "Domain"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[display_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Domain": st.column_config.TextColumn("Domain", width="medium"),
            "Matched solutions": st.column_config.TextColumn("Matched solutions", width="large"),
        },
    )

    accumulate_session_usage(result.get("token_usage"))
    render_token_usage(result.get("token_usage"), title="Market Research Token Usage")

    # ── Agent Trace ─────────────────────────────────────────────────────
    from utils.agent_trace import render_agent_trace
    render_agent_trace(result.get("agent_trace"), title="Market Research Timeline")

    with st.expander("Sources & Raw Data"):
        for r in rows:
            sources = r.get("Sources", "")
            st.markdown(
                f'<div class="info-card" style="margin-bottom:0.5rem">'
                f'<div style="font-weight:600;color:var(--text)">{r.get("Company", "—")}</div>'
                f'<div style="font-size:0.8rem;color:var(--text-muted);font-family:var(--font-mono)">{r.get("Domain", "")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if sources:
                for src in sources.split(" | "):
                    st.markdown(f"- {src}")

    st.session_state["latest_market_research"] = result
