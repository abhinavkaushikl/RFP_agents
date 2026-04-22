"""Section Revision page."""
import streamlit as st

st.set_page_config(page_title="Section Revision", page_icon="✏️", layout="wide")
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
            )
        except Exception as exc:
            st.error(f"Revision failed: {exc}")
            st.stop()

    st.success("Revision complete!")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original")
        st.markdown(selected_section.get("draft_text", ""))
    with col2:
        st.subheader("Revised")
        revised_sections = revision_result.get("sections", [])
        if revised_sections:
            st.markdown(revised_sections[0].get("draft_text", "_No revised text._"))
        else:
            st.markdown(str(revision_result))

    summaries = revision_result.get("step_summaries", [])
    if summaries:
        with st.expander("Revision Steps"):
            for i, s in enumerate(summaries, 1):
                st.markdown(f"**Step {i}:** {s}")
