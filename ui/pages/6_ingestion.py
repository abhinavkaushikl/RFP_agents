"""Document Ingestion — upload historical proposals to populate the retrieval index."""
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

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Knowledge Base</div>
        <h1 class="rfp-title">Document Ingestion</h1>
        <p class="rfp-copy">
            Upload historical proposal records to populate the retrieval index.
            Documents are chunked, embedded with SentenceTransformer, and stored
            in pgvector for semantic search.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Processing pipeline preview ─────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-panel" style="margin-bottom:1.2rem">
        <div class="pipeline-flow">
            <span class="pipeline-step">Upload JSON</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">Parse Records</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">Chunk Sections</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">Embed (MiniLM-L6-v2)</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step done-step">Store in pgvector</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Upload method ───────────────────────────────────────────────────────
render_section_header("Input Method", icon="upload_file")
upload_method = st.radio("Select input method", ["JSON File Upload", "Paste JSON"], horizontal=True)

records: list[dict] | None = None

if upload_method == "JSON File Upload":
    uploaded = st.file_uploader("Upload a JSON file (list of proposal records)", type=["json"])
    if uploaded is not None:
        try:
            data = json.loads(uploaded.read())
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict) and "records" in data:
                records = data["records"]
            else:
                records = [data]
            st.markdown(
                f'<div class="status-chip active" style="margin:0.5rem 0">Parsed {len(records)} record(s)</div>',
                unsafe_allow_html=True,
            )
        except json.JSONDecodeError:
            st.error("Invalid JSON file.")
else:
    json_text = st.text_area(
        "Paste JSON Records",
        height=280,
        placeholder='[\n  {\n    "title": "AIOps Proposal",\n    "industry": "Telecom",\n    "solution_type": "aiops_operations",\n    "sections": {\n      "executive_summary": "Our platform...",\n      "implementation_plan": "Phase 1..."\n    }\n  }\n]',
    )
    if json_text.strip():
        try:
            data = json.loads(json_text)
            if isinstance(data, list):
                records = data
            else:
                records = [data]
            st.markdown(
                f'<div class="status-chip active" style="margin:0.5rem 0">Parsed {len(records)} record(s)</div>',
                unsafe_allow_html=True,
            )
        except json.JSONDecodeError:
            st.error("Invalid JSON.")

# ── Ingest ──────────────────────────────────────────────────────────────
render_section_header("Ingest Configuration", icon="settings")
source_name = st.text_input("Source Name", value="ui_upload")

if st.button("Ingest Records", type="primary", disabled=records is None, use_container_width=True):
    if not records:
        st.error("No records to ingest.")
        st.stop()

    from utils.api_client import ingest_historical_proposals

    with st.spinner("Ingesting records — chunking, embedding, and storing..."):
        try:
            result = ingest_historical_proposals(records=records, source_name=source_name)
        except Exception as exc:
            st.error(f"Ingestion failed: {exc}")
            st.stop()

    st.success("Ingestion complete!")

    render_section_header("Ingestion Results", icon="check_circle")
    col1, col2, col3 = st.columns(3)
    with col1:
        render_stat_card("Records Ingested", str(result.get("ingested_count", 0)), icon="description")
    with col2:
        render_stat_card("Sections Processed", str(result.get("section_count", 0)), icon="segment")
    with col3:
        render_stat_card("Chunks Created", str(result.get("chunk_count", 0)), icon="data_array")

# ── Expected format ─────────────────────────────────────────────────────
with st.expander("Expected Record Format"):
    st.json({
        "title": "Example Proposal",
        "industry": "Telecom",
        "solution_type": "aiops_operations",
        "sections": {
            "executive_summary": "Our platform provides...",
            "solution_overview": "The solution architecture...",
            "implementation_plan": "Phase 1: Discovery...",
        },
    })
