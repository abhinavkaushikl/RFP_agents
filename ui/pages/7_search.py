"""Retrieval Explorer page."""
import streamlit as st

from utils.theme import apply_theme, render_header, render_sidebar

st.set_page_config(page_title="Retrieval Explorer", page_icon="🔍", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Retrieval Explorer")
st.title("Retrieval Explorer")
st.markdown("Search historical proposal chunks to find relevant content.")

# ── Search form ────────────────────────────────────────────────────────
with st.form("search_form"):
    query = st.text_input(
        "Search Query",
        placeholder="e.g. event correlation and noise reduction for telecom",
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        section_type = st.selectbox(
            "Section Type",
            options=["", "executive_summary", "solution_overview", "implementation_plan", "pricing_notes"],
        )
    with col2:
        solution_type = st.selectbox(
            "Solution Type",
            options=["", "aiops_operations", "aiops_observability", "aiops_general"],
        )
    with col3:
        industry = st.selectbox(
            "Industry",
            options=["", "Telecom", "Healthcare", "Financial Services", "Retail", "Manufacturing"],
        )
    with col4:
        top_k = st.number_input("Results", min_value=1, max_value=20, value=5)

    submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

# ── Results ────────────────────────────────────────────────────────────
if submitted:
    if not query.strip():
        st.error("Please enter a search query.")
        st.stop()

    from utils.api_client import retrieval_search

    with st.spinner("Searching..."):
        try:
            result = retrieval_search(
                query=query,
                section_type=section_type or None,
                solution_type=solution_type or None,
                industry=industry or None,
                top_k=top_k,
            )
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.stop()

    results = result.get("results", [])
    st.subheader(f"Results ({len(results)} found)")

    if not results:
        st.info("No matching chunks found. Try a different query or ingest more data.")
    else:
        for i, chunk in enumerate(results, 1):
            score = chunk.get("score", 0)
            section_key = chunk.get("section_key", "unknown")
            sol_type = chunk.get("solution_type", "")
            content = chunk.get("content", chunk.get("chunk_text", ""))
            proposal_id = chunk.get("proposal_id", "")

            with st.container(border=True):
                header_col, score_col = st.columns([4, 1])
                with header_col:
                    st.markdown(f"**#{i}** | Section: `{section_key}` | Solution: `{sol_type}`")
                    if proposal_id:
                        st.caption(f"Proposal: {proposal_id}")
                with score_col:
                    st.metric("Score", f"{score:.2f}")

                st.markdown(content)
