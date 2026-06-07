"""Document Matching — score an existing proposal against RFP requirements."""
import streamlit as st

from utils.theme import (
    apply_theme,
    render_header,
    render_score_gauge,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Document Match · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Document Match")

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Analysis Mode</div>
        <h1 class="rfp-title">Document Matching</h1>
        <p class="rfp-copy">
            Score an existing proposal document against RFP requirements.
            The agent pipeline structures the requirements, retrieves historical matches,
            compares solutions, and generates a composite quality score.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Input form ──────────────────────────────────────────────────────────
with st.form("match_form"):
    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_section_header("RFP Requirements", icon="description")
        request_text = st.text_area(
            "RFP Text",
            height=280,
            placeholder="Paste the RFP / requirements text...",
        )
    with col2:
        render_section_header("Proposal Document", icon="article")
        document_text = st.text_area(
            "Proposal Text",
            height=280,
            placeholder="Paste the existing proposal document text...",
        )

    solution_type = st.selectbox(
        "Solution Type (optional)",
        options=["", "aiops_operations", "aiops_observability", "aiops_general"],
    )
    submitted = st.form_submit_button("Run Document Match", type="primary", use_container_width=True)

# ── Execute ─────────────────────────────────────────────────────────────
if submitted:
    if not request_text.strip() or not document_text.strip():
        st.error("Both RFP text and proposal text are required.")
        st.stop()

    from utils.api_client import run_document_match

    with st.spinner("Running document match pipeline — structuring, retrieving, comparing, scoring..."):
        try:
            result = run_document_match(
                request_text=request_text,
                document_text=document_text,
                solution_type=solution_type or None,
            )
        except Exception as exc:
            st.error(f"Document match failed: {exc}")
            st.stop()

    st.success("Matching complete!")

    # ── Scores ──────────────────────────────────────────────────────────
    render_section_header("Match Quality Scores", icon="verified_user", badge="scoring agent")
    scoring = result.get("scoring", result)

    composite = scoring.get("composite_score", 0)
    req_coverage = scoring.get("requirement_coverage_score", 0)
    sol_fit = scoring.get("solution_fit_score", 0)

    col1, col2, col3 = st.columns(3)
    with col1:
        render_score_gauge(composite, "Composite Score")
    with col2:
        render_score_gauge(req_coverage, "Requirement Coverage")
    with col3:
        render_score_gauge(sol_fit, "Solution Fit")

    # ── Agent Trace ─────────────────────────────────────────────────────
    from utils.agent_trace import render_agent_trace
    render_agent_trace(result.get("agent_trace"), title="Match Pipeline Timeline")

    # ── Pipeline Steps ──────────────────────────────────────────────────
    summaries = result.get("step_summaries", [])
    if summaries:
        with st.expander("Pipeline Step Summaries"):
            for i, s in enumerate(summaries, 1):
                st.markdown(f"**Step {i}:** {s}")

    with st.expander("Raw Response"):
        st.json(result)
