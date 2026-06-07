"""Retrieval Explorer — semantic search through historical proposal chunks."""
import streamlit as st

from utils.theme import (
    apply_theme,
    render_empty_state,
    render_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Retrieval Explorer · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Retrieval Explorer")

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Knowledge Base</div>
        <h1 class="rfp-title">Semantic Search</h1>
        <p class="rfp-copy">
            Search historical proposal chunks using semantic similarity.
            Filter by section type, solution type, and industry to find
            the most relevant content for your proposals.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Search form ─────────────────────────────────────────────────────────
with st.form("search_form"):
    query = st.text_input(
        "Search Query",
        placeholder="e.g. event correlation and noise reduction for telecom",
    )

    render_section_header("Filters", icon="filter_list")
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

# ── Results ─────────────────────────────────────────────────────────────
if submitted:
    if not query.strip():
        st.error("Please enter a search query.")
        st.stop()

    from utils.api_client import retrieval_search

    with st.spinner("Searching knowledge base..."):
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
    render_section_header("Search Results", icon="search", badge=f"{len(results)} found")

    if not results:
        render_empty_state(
            "No matching chunks found",
            "Try a different query or ingest more data from the Ingestion page.",
            icon="search_off",
        )
    else:
        # ── Active filter chips ─────────────────────────────────────────
        filters_html = ""
        if section_type:
            filters_html += f'<span class="status-chip processing">{section_type}</span> '
        if solution_type:
            filters_html += f'<span class="status-chip processing">{solution_type}</span> '
        if industry:
            filters_html += f'<span class="status-chip processing">{industry}</span> '
        if filters_html:
            st.markdown(
                f'<div style="margin-bottom:0.75rem">{filters_html}</div>',
                unsafe_allow_html=True,
            )

        for i, chunk in enumerate(results, 1):
            score = chunk.get("score", 0)
            section_key = chunk.get("section_key", "unknown")
            sol_type = chunk.get("solution_type", "")
            content = chunk.get("content", chunk.get("chunk_text", ""))
            proposal_id = chunk.get("proposal_id", "")

            # Score color
            score_tone = "good" if score >= 0.8 else "warn" if score >= 0.6 else "bad"

            st.markdown(
                f'<div class="info-card" style="margin-bottom:0.75rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem">'
                f'<div>'
                f'<span style="font-weight:700;color:var(--text);font-size:0.9rem">#{i}</span>'
                f' <span class="status-chip queued">{section_key}</span>'
                f' <span class="status-chip queued">{sol_type}</span>'
                f'{f" <span style=&quot;font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono)&quot;>Proposal: {proposal_id}</span>" if proposal_id else ""}'
                f'</div>'
                f'<div>'
                f'<span style="font-family:var(--font-mono);font-weight:700;font-size:1.1rem" class="score-gauge-value {score_tone}">{score:.2f}</span>'
                f'<div style="font-size:0.65rem;text-align:right;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;font-weight:600">similarity</div>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown(content)
            st.divider()

        st.markdown(
            '<div style="text-align:center;font-size:0.82rem;color:var(--text-dim);padding:0.5rem 0">End of results</div>',
            unsafe_allow_html=True,
        )
