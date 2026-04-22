"""Document Matching page."""
import streamlit as st

st.set_page_config(page_title="Document Match", page_icon="📊", layout="wide")
st.title("Document Matching")
st.markdown("Score an existing proposal document against RFP requirements.")

# ── Input form ─────────────────────────────────────────────────────────
with st.form("match_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("RFP Requirements")
        request_text = st.text_area(
            "RFP Text",
            height=300,
            placeholder="Paste the RFP / requirements text...",
        )
    with col2:
        st.subheader("Proposal Document")
        document_text = st.text_area(
            "Proposal Text",
            height=300,
            placeholder="Paste the existing proposal document text...",
        )

    solution_type = st.selectbox(
        "Solution Type (optional)",
        options=["", "aiops_operations", "aiops_observability", "aiops_general"],
    )
    submitted = st.form_submit_button("Run Document Match", type="primary", use_container_width=True)

# ── Execute matching ───────────────────────────────────────────────────
if submitted:
    if not request_text.strip() or not document_text.strip():
        st.error("Both RFP text and proposal text are required.")
        st.stop()

    from utils.api_client import run_document_match

    with st.spinner("Running document match pipeline..."):
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

    # ── Scores ─────────────────────────────────────────────────────────
    st.subheader("Match Scores")
    scoring = result.get("scoring", result)

    col1, col2, col3 = st.columns(3)

    composite = scoring.get("composite_score", 0)
    req_coverage = scoring.get("requirement_coverage_score", 0)
    sol_fit = scoring.get("solution_fit_score", 0)

    with col1:
        st.metric("Composite Score", f"{composite:.2f}")
        st.progress(min(composite, 1.0))
    with col2:
        st.metric("Requirement Coverage", f"{req_coverage:.2f}")
        st.progress(min(req_coverage, 1.0))
    with col3:
        st.metric("Solution Fit", f"{sol_fit:.2f}")
        st.progress(min(sol_fit, 1.0))

    # ── Step summaries ─────────────────────────────────────────────────
    summaries = result.get("step_summaries", [])
    if summaries:
        with st.expander("Pipeline Steps"):
            for i, s in enumerate(summaries, 1):
                st.markdown(f"**Step {i}:** {s}")

    # ── Raw result ─────────────────────────────────────────────────────
    with st.expander("Raw Response"):
        st.json(result)
