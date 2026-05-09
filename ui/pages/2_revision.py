"""Section Revision page."""
from copy import deepcopy

import streamlit as st

from utils.theme import apply_theme, render_header, render_sidebar

st.set_page_config(page_title="Section Revision", page_icon="✏️", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Section Revision")
st.title("Revise a Generated Section")
st.markdown("Select a previously generated section and provide revision instructions.")

# ── Check for available sections ───────────────────────────────────────
results = st.session_state.get("workflow_results", [])
if not results:
    st.info("No workflow results available. Generate a proposal first on the **New Proposal** page.")
    st.stop()

# ── Select workflow and section ────────────────────────────────────────
workflow_options = {r["workflow_id"]: r for r in results}
selected_wf_id = st.selectbox("Workflow Run", options=list(workflow_options.keys()))
selected_wf = workflow_options[selected_wf_id]

sections = selected_wf.get("sections", [])
if not sections:
    st.warning("This workflow has no generated sections.")
    st.stop()

section_keys = [s.get("section_key", f"section_{i}") for i, s in enumerate(sections)]
selected_key = st.selectbox("Section", options=section_keys)
selected_section = sections[section_keys.index(selected_key)]

# ── Show current draft ─────────────────────────────────────────────────
st.subheader("Current Draft")
st.markdown(selected_section.get("draft_text", "_Empty_"))

# ── Revision form ──────────────────────────────────────────────────────
st.subheader("Revision")
with st.form("revision_form"):
    instruction = st.text_area(
        "Revision Instruction",
        placeholder="e.g. Add more detail about implementation timeline and reduce jargon",
        height=100,
    )
    submitted = st.form_submit_button("Revise Section", type="primary", use_container_width=True)

if submitted:
    if not instruction.strip():
        st.error("Please provide a revision instruction.")
        st.stop()

    from utils.api_client import revise_section

    section_id = selected_section.get("section_id", selected_wf_id)

    with st.spinner("Running revision pipeline..."):
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

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original")
        st.markdown(selected_section.get("draft_text", ""))
    with col2:
        st.subheader("Revised")
        st.markdown(revised_text)

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
    pdf_title = selected_wf.get("_pdf_title") or st.session_state.get(
        "latest_pdf_title", "Revised RFP Proposal"
    )
    pdf_bytes = build_proposal_pdf(
        workflow_result=revised_workflow,
        metadata=pdf_metadata,
        title=f"Revised {pdf_title}",
    )
    st.download_button(
        "Download Revised Proposal PDF",
        data=pdf_bytes,
        file_name=f"revised_{selected_key}_proposal.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

    if st.button("Use Revised Version In This Session", use_container_width=True):
        selected_wf.update(revised_workflow)
        st.session_state["latest_result"] = selected_wf
        st.success("Session copy updated with the revised section.")

    if revised_workflow.get("step_summaries"):
        with st.expander("Revision Steps"):
            for i, s in enumerate(revised_workflow["step_summaries"], 1):
                st.markdown(f"**Step {i}:** {s}")
