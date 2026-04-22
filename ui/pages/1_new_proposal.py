"""New Proposal Generation page."""
import streamlit as st

st.set_page_config(page_title="New Proposal", page_icon="📝", layout="wide")
st.title("Generate New Proposal")
st.markdown("Paste your RFP text below and configure options to generate proposal sections.")

# ── Input form ─────────────────────────────────────────────────────────
with st.form("proposal_form"):
    request_text = st.text_area(
        "RFP Text *",
        height=250,
        placeholder="Paste the full RFP / request text here...",
    )
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Proposal Title", value="AIOps Proposal Request")
        industry = st.selectbox(
            "Industry",
            options=["", "Telecom", "Healthcare", "Financial Services", "Retail", "Manufacturing", "Other"],
        )
    with col2:
        solution_type = st.selectbox(
            "Solution Type",
            options=["", "aiops_operations", "aiops_observability", "aiops_general"],
        )
        target_sections = st.multiselect(
            "Target Sections",
            options=[
                "executive_summary",
                "solution_overview",
                "implementation_plan",
                "pricing_notes",
            ],
            default=["executive_summary", "solution_overview", "implementation_plan"],
        )
    user_instruction = st.text_input(
        "Custom Instruction (optional)",
        placeholder="e.g. Focus on cost savings and ROI metrics",
    )
    submitted = st.form_submit_button("Generate Proposal", type="primary", use_container_width=True)

# ── Execute workflow ───────────────────────────────────────────────────
if submitted:
    if not request_text.strip():
        st.error("Please provide RFP text.")
        st.stop()

    from utils.api_client import create_workflow_run

    with st.spinner("Running multi-agent pipeline... this may take a minute."):
        try:
            result = create_workflow_run(
                request_text=request_text,
                title=title,
                industry=industry or None,
                solution_type=solution_type or None,
                user_instruction=user_instruction or None,
                target_sections=target_sections or None,
            )
        except Exception as exc:
            st.error(f"Workflow failed: {exc}")
            st.stop()

    # Store result for revision page
    if "workflow_results" not in st.session_state:
        st.session_state["workflow_results"] = []
    st.session_state["workflow_results"].append(result)
    st.session_state["latest_result"] = result

    st.success(f"Workflow **{result['workflow_id']}** completed with status: **{result['status']}**")

    # ── Agent step summaries ───────────────────────────────────────────
    with st.expander("Agent Pipeline Steps", expanded=False):
        for i, summary in enumerate(result.get("step_summaries", []), 1):
            st.markdown(f"**Step {i}:** {summary}")

    # ── Generated sections ─────────────────────────────────────────────
    st.subheader("Generated Sections")
    sections = result.get("sections", [])
    if sections:
        tabs = st.tabs([s.get("section_key", f"Section {i}") for i, s in enumerate(sections, 1)])
        for tab, section in zip(tabs, sections):
            with tab:
                st.markdown(section.get("draft_text", "_No text generated._"))

                citations = section.get("citations", [])
                if citations:
                    with st.expander("Citations"):
                        for c in citations:
                            st.markdown(f"- {c}")

                validation = section.get("validation", {})
                if validation:
                    with st.expander("Validation"):
                        coverage = validation.get("requirement_coverage", {})
                        if coverage:
                            covered = sum(1 for v in coverage.values() if v)
                            total = len(coverage)
                            st.progress(covered / total if total else 0, text=f"{covered}/{total} requirements covered")
                        missing = validation.get("missing_items", [])
                        if missing:
                            st.warning("Missing items: " + ", ".join(missing))
    else:
        st.warning("No sections were generated.")

    # ── Scoring ────────────────────────────────────────────────────────
    scoring = result.get("scoring", {})
    if scoring:
        st.subheader("Proposal Score")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Composite", f"{scoring.get('composite_score', 0):.2f}")
        sc2.metric("Requirement Coverage", f"{scoring.get('requirement_coverage_score', 0):.2f}")
        sc3.metric("Solution Fit", f"{scoring.get('solution_fit_score', 0):.2f}")
        sc4.metric("Historical Similarity", f"{scoring.get('historical_similarity_score', 0):.2f}")
