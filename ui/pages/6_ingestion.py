"""Historical Proposals Ingestion page."""
import json

import streamlit as st

from utils.theme import apply_theme, render_header, render_sidebar

st.set_page_config(page_title="Ingestion", page_icon="📥", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Ingestion")
st.title("Historical Proposals Ingestion")
st.markdown("Upload historical proposal records to populate the retrieval index.")

# ── Upload method ──────────────────────────────────────────────────────
upload_method = st.radio("Input method", ["JSON File Upload", "Paste JSON"], horizontal=True)

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
            st.info(f"Parsed **{len(records)}** record(s) from file.")
        except json.JSONDecodeError:
            st.error("Invalid JSON file.")
else:
    json_text = st.text_area(
        "Paste JSON records",
        height=300,
        placeholder='[\n  {\n    "title": "AIOps Proposal",\n    "industry": "Telecom",\n    "solution_type": "aiops_operations",\n    "sections": {\n      "executive_summary": "Our platform...",\n      "implementation_plan": "Phase 1..."\n    }\n  }\n]',
    )
    if json_text.strip():
        try:
            data = json.loads(json_text)
            if isinstance(data, list):
                records = data
            else:
                records = [data]
            st.info(f"Parsed **{len(records)}** record(s).")
        except json.JSONDecodeError:
            st.error("Invalid JSON.")

# ── Ingest ─────────────────────────────────────────────────────────────
source_name = st.text_input("Source Name", value="ui_upload")

if st.button("Ingest Records", type="primary", disabled=records is None, use_container_width=True):
    if not records:
        st.error("No records to ingest.")
        st.stop()

    from utils.api_client import ingest_historical_proposals

    with st.spinner("Ingesting records..."):
        try:
            result = ingest_historical_proposals(records=records, source_name=source_name)
        except Exception as exc:
            st.error(f"Ingestion failed: {exc}")
            st.stop()

    st.success("Ingestion complete!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Records Ingested", result.get("ingested_count", 0))
    col2.metric("Sections Processed", result.get("section_count", 0))
    col3.metric("Chunks Created", result.get("chunk_count", 0))

# ── Expected format ────────────────────────────────────────────────────
with st.expander("Expected Record Format"):
    st.json(
        {
            "title": "Example Proposal",
            "industry": "Telecom",
            "solution_type": "aiops_operations",
            "sections": {
                "executive_summary": "Our platform provides...",
                "solution_overview": "The solution architecture...",
                "implementation_plan": "Phase 1: Discovery...",
            },
        }
    )
