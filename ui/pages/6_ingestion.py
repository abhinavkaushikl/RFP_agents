"""Knowledge Base Ingestion — add past proposals to the retrieval index."""
import json

import streamlit as st

from utils.theme import (
    apply_theme,
    render_header,
    render_section_header,
    render_sidebar,
    render_stat_card,
)

st.set_page_config(page_title="Ingestion · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Ingestion")

from utils.api_client import APIError, ingest_historical_proposals, upload_historical_documents  # noqa: E402
from utils.profile import active_profile_name, get_active_profile  # noqa: E402

profile = get_active_profile()
profile_name = active_profile_name()

SAMPLE = [
    {
        "id": "proposal-2025-014",
        "title": "Citizen Services Portal",
        "client_name": "City of Riverton",
        "industry": "Government & Public Sector",
        "solution_type": "digital_platforms",
        "proposal_sections": {
            "executive_summary": "We propose a mobile-first citizen portal that consolidates 40 services...",
            "implementation_plan": "Phase 1 (weeks 1-6): discovery and service design...",
            "pricing_notes": "Fixed fee per phase with milestone-based payments...",
        },
    }
]

st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Knowledge Base</div>
        <h1 class="rfp-title">Add Past Proposals</h1>
        <p class="rfp-copy">
            Upload proposals you have submitted before. They are split into sections, embedded, and stored
            in pgvector, so the agents can reuse your best precedent. Section names are matched to the
            active profile, so "Pricing", "Commercials", and "Fees" land in the same section.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_section_header("Input Method", icon="upload_file")
method = st.radio("Select input method", ["Documents (PDF, Word, Markdown, text)", "JSON records"], horizontal=True)
source_name = st.text_input("Source name", value="ui_upload", help="Recorded with each proposal; re-uploading the same id from the same source is skipped.")

result = None
if method.startswith("Documents"):
    files = st.file_uploader("Proposal documents", type=["pdf", "docx", "md", "txt"], accept_multiple_files=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        client_name = st.text_input("Client (optional)")
    with c2:
        industry = st.selectbox("Industry (optional)", ["", *profile.get("industries", [])])
    with c3:
        solution_type = st.selectbox("Offering (optional)", ["", *[o["code"] for o in profile.get("offerings", [])]])
    if st.button("Ingest Documents", type="primary", disabled=not files, use_container_width=True):
        with st.spinner("Extracting text, splitting sections, embedding, and storing…"):
            try:
                result = upload_historical_documents(
                    [(f.name, f.getvalue()) for f in files],
                    source_name=source_name,
                    profile=profile_name,
                    client_name=client_name or None,
                    industry=industry or None,
                    solution_type=solution_type or None,
                )
            except APIError as exc:
                st.error(f"Ingestion failed: {exc}")
else:
    records = None
    uploaded = st.file_uploader("JSON file (a list of records, or {\"records\": [...]})", type=["json"])
    pasted = st.text_area("…or paste JSON", height=220, placeholder=json.dumps(SAMPLE, indent=2))
    raw = uploaded.read().decode("utf-8") if uploaded is not None else pasted
    if raw.strip():
        try:
            data = json.loads(raw)
            records = data["records"] if isinstance(data, dict) and "records" in data else data if isinstance(data, list) else [data]
            st.markdown(f'<div class="status-chip active" style="margin:0.5rem 0">Parsed {len(records)} record(s)</div>',
                        unsafe_allow_html=True)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
    if st.button("Ingest Records", type="primary", disabled=not records, use_container_width=True):
        with st.spinner("Chunking, embedding, and storing…"):
            try:
                result = ingest_historical_proposals(records=records, source_name=source_name, profile=profile_name)
            except APIError as exc:
                st.error(f"Ingestion failed: {exc}")

if result:
    st.success("Ingestion complete.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat_card("Proposals added", str(result.get("ingested_count", 0)), icon="description")
    with c2:
        render_stat_card("Sections", str(result.get("section_count", 0)), icon="segment")
    with c3:
        render_stat_card("Chunks embedded", str(result.get("chunk_count", 0)), icon="data_array")
    with c4:
        render_stat_card("Skipped", str(result.get("skipped_duplicates", 0) + len(result.get("skipped", []))),
                         icon="block", sub="duplicates or no text")
    for f in result.get("files", []):
        if f.get("ok"):
            st.markdown(f"- **{f['file_name']}** → {', '.join(f.get('sections', [])) or 'one section'}")
        else:
            st.markdown(f"- **{f['file_name']}** — {f.get('error')}")
    for skipped in result.get("skipped", []):
        st.caption(f"Skipped record {skipped.get('id') or skipped.get('index')}: {skipped.get('reason')}")

with st.expander("Expected JSON record format"):
    st.markdown(
        "`proposal_sections` (or `sections`) can be an object of section name → text, or a list of "
        "`{\"title\": ..., \"content\": ...}`. Everything else is optional."
    )
    st.json(SAMPLE[0])
