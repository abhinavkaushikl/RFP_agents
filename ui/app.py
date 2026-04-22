"""RFP Proposal Platform - Streamlit UI."""
import streamlit as st

st.set_page_config(
    page_title="RFP Proposal Platform",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("RFP Proposal Platform")
st.markdown("Generate, revise, and score RFP proposal sections using a multi-agent AI pipeline.")

# ── Sidebar: backend status ────────────────────────────────────────────
with st.sidebar:
    st.header("Backend Status")
    try:
        from utils.api_client import health_check

        status = health_check()
        st.success(f"API: {status.get('status', 'ok')}")
    except Exception:
        st.error("API unreachable (start backend with `uvicorn src.main:app`)")

    st.divider()
    st.markdown(
        """
**Pages**
- **New Proposal** - Generate proposal from RFP text
- **Section Revision** - Revise generated sections
- **Document Match** - Score proposals against RFPs
- **Ingestion** - Upload historical proposals
- **Search** - Explore retrieval index
"""
    )

# ── Dashboard ──────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Workflows", value="--", help="Total proposal workflows executed")
with col2:
    st.metric("Sections Generated", value="--", help="Total sections generated across all runs")
with col3:
    st.metric("Avg Composite Score", value="--", help="Average scoring agent composite score")

st.info("Select a page from the sidebar to get started. Use **New Proposal** to generate your first RFP response.")

# ── Session state init ─────────────────────────────────────────────────
if "workflow_results" not in st.session_state:
    st.session_state["workflow_results"] = []
