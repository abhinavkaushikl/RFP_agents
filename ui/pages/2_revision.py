"""Section Revision — AI-powered section refinement with side-by-side comparison."""
from copy import deepcopy

import streamlit as st

from utils.theme import (
    apply_theme,
    render_empty_state,
    render_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Section Revision · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Section Revision")

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">AI Refinement</div>
        <h1 class="rfp-title">Proposal Revision</h1>
        <p class="rfp-copy">
            Select a previously generated section and provide revision instructions.
            The revision agent retrieves additional evidence and refines the draft
            while maintaining requirement coverage.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Check for available sections ────────────────────────────────────────
results = st.session_state.get("workflow_results", [])
if not results:
    render_empty_state(
        "No proposals available",
        "Generate a proposal first from the New Proposal page to revise its sections.",
        icon="edit_note",
    )
    st.stop()

# ── Select workflow and section ─────────────────────────────────────────
render_section_header("Select Section", icon="checklist")

c1, c2 = st.columns(2)
workflow_options = {r["workflow_id"]: r for r in results}
with c1:
    selected_wf_id = st.selectbox("Workflow Run", options=list(workflow_options.keys()))
with c2:
    selected_wf = workflow_options[selected_wf_id]
    sections = selected_wf.get("sections", [])
    if not sections:
        st.warning("This workflow has no generated sections.")
        st.stop()
    section_keys = [s.get("section_key", f"section_{i}") for i, s in enumerate(sections)]
    selected_key = st.selectbox("Section", options=section_keys)

selected_section = sections[section_keys.index(selected_key)]

# ── Current Draft ───────────────────────────────────────────────────────
render_section_header("Current Draft", icon="article", badge=selected_key)
st.markdown('<div class="result-box">', unsafe_allow_html=True)
st.markdown(selected_section.get("draft_text", "_Empty_"))
st.markdown("</div>", unsafe_allow_html=True)

# ── Revision form ──────────────────────────────────────────────────────
render_section_header("Revision Instructions", icon="auto_fix_high")
with st.form("revision_form"):
    instruction = st.text_area(
        "What should the agent change?",
        placeholder="e.g. Add more detail about implementation timeline and reduce jargon. Include ISO 27001 certification mention.",
        height=100,
    )
    submitted = st.form_submit_button("Revise Section", type="primary", use_container_width=True)

if submitted:
    if not instruction.strip():
        st.error("Please provide a revision instruction.")
        st.stop()

    from utils.api_client import revise_section

    section_id = selected_section.get("section_id", selected_wf_id)

    with st.spinner("Running revision pipeline — retrieving evidence and refining draft..."):
        try:
            revision_result = revise_section(
                section_id=section_id,
                instruction=instruction,
                section_key=selected_key,
                base_text=selected_section.get("draft_text", ""),
            )
        except Exception as exc:
            st.error(f"Revision failed: {exc}")
            st.stop()

    st.success("Revision complete!")

    revised_section = revision_result.get("revision", {})
    revised_text = revised_section.get("draft_text", "_No revised text._")

    # ── Side-by-side comparison ─────────────────────────────────────────
    render_section_header("Comparison", icon="compare_arrows")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="info-card-title">Original</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="result-box">', unsafe_allow_html=True)
        st.markdown(selected_section.get("draft_text", ""))
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            '<div class="info-card-title">Revised <span class="status-chip active" style="margin-left:6px">NEW</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="result-box">', unsafe_allow_html=True)
        st.markdown(revised_text)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── PDF Download ────────────────────────────────────────────────────
    revised_workflow = deepcopy(selected_wf)
    for section in revised_workflow.get("sections", []):
        if section.get("section_key") == selected_key:
            section["draft_text"] = revised_text
            section["validation"] = revision_result.get("validation", section.get("validation", {}))
            section["revision_summary"] = revised_section.get("revision_summary", "")
            break

    revision_steps = [
        revision_result.get("plan", {}).get("workflow_type") and "Planned revision workflow.",
        revision_result.get("retrieval", {}).get("results") is not None
        and f"Retrieved {len(revision_result.get('retrieval', {}).get('results', []))} evidence chunks.",
        revised_section.get("revision_summary"),
        revision_result.get("validation") and "Validated revised section coverage.",
    ]
    revised_workflow["step_summaries"] = selected_wf.get("step_summaries", []) + [
        step for step in revision_steps if step
    ]

    from utils.pdf_export import build_proposal_pdf

    pdf_metadata = selected_wf.get("_pdf_metadata") or st.session_state.get("latest_pdf_metadata", {})
    pdf_title = selected_wf.get("_pdf_title") or st.session_state.get("latest_pdf_title", "Revised RFP Proposal")
    pdf_bytes = build_proposal_pdf(
        workflow_result=revised_workflow, metadata=pdf_metadata, title=f"Revised {pdf_title}",
    )
    st.download_button(
        "Download Revised Proposal PDF",
        data=pdf_bytes,
        file_name=f"revised_{selected_key}_proposal.pdf",
        mime="application/pdf", type="primary", use_container_width=True,
    )

    if st.button("Use Revised Version In This Session", use_container_width=True):
        selected_wf.update(revised_workflow)
        st.session_state["latest_result"] = selected_wf
        st.success("Session copy updated with the revised section.")

    # ── Agent Trace ─────────────────────────────────────────────────────
    from utils.agent_trace import render_agent_trace
    render_agent_trace(revision_result.get("agent_trace"), title="Revision Agent Timeline")

    if revised_workflow.get("step_summaries"):
        with st.expander("Pipeline Step Summaries"):
            for i, s in enumerate(revised_workflow["step_summaries"], 1):
                st.markdown(f"**Step {i}:** {s}")
