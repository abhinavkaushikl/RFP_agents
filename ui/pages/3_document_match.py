"""Document Matching — score an existing proposal against an RFP."""
import streamlit as st

from utils.theme import (
    apply_theme,
    render_header,
    render_score_gauge,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Document Match · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Document Match")

from utils.api_client import APIError, extract_text, run_document_match  # noqa: E402
from utils.profile import active_profile_name, get_active_profile  # noqa: E402
from utils.token_usage import accumulate_session_usage, render_token_usage  # noqa: E402

profile = get_active_profile()
profile_name = active_profile_name()

st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Analysis Mode</div>
        <h1 class="rfp-title">Document Matching</h1>
        <p class="rfp-copy">
            Score an existing proposal against an RFP. The agents extract the RFP's requirements, check which
            ones the proposal addresses, compare against your offerings and past proposals, and grade it
            against the evaluation criteria.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Load either document from a file (PDF, Word, Markdown, or text)"):
    c1, c2 = st.columns(2)
    for col, key, label in ((c1, "match_rfp_text", "RFP file"), (c2, "match_doc_text", "Proposal file")):
        with col:
            f = st.file_uploader(label, type=["pdf", "docx", "md", "txt"], key=f"{key}_file")
            if f is not None and st.button(f"Extract {label.lower()}", key=f"{key}_btn"):
                try:
                    st.session_state[key] = extract_text(f.name, f.getvalue(), profile=profile_name)["text"]
                except APIError as exc:
                    st.error(str(exc))

offering_codes = [""] + [o["code"] for o in profile.get("offerings", [])]
with st.form("match_form"):
    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_section_header("RFP Requirements", icon="description")
        request_text = st.text_area("RFP text", value=st.session_state.get("match_rfp_text", ""), height=280,
                                    placeholder="Paste the RFP or requirements…")
    with col2:
        render_section_header("Proposal Document", icon="article")
        document_text = st.text_area("Proposal text", value=st.session_state.get("match_doc_text", ""), height=280,
                                     placeholder="Paste the proposal to score…")
    c3, c4 = st.columns(2)
    with c3:
        solution_type = st.selectbox("Offering (optional)", offering_codes,
                                     format_func=lambda c: c or "Infer from the RFP")
    with c4:
        industry = st.selectbox("Industry (optional)", ["", *profile.get("industries", [])],
                                format_func=lambda i: i or "Infer from the RFP")
    submitted = st.form_submit_button("Run Document Match", type="primary", use_container_width=True)

if submitted:
    if not request_text.strip() or not document_text.strip():
        st.error("Both the RFP text and the proposal text are required.")
        st.stop()
    with st.spinner("Structuring requirements, retrieving precedent, comparing, and scoring…"):
        try:
            result = run_document_match(
                request_text=request_text,
                document_text=document_text,
                solution_type=solution_type or None,
                industry=industry or None,
                profile=profile_name,
            )
        except APIError as exc:
            st.error(f"Document match failed: {exc}")
            st.stop()
    accumulate_session_usage(result.get("token_usage"))
    st.success("Matching complete.")

    scores = result.get("scores") or {}
    render_section_header("Match Quality Scores", icon="verified_user", badge="scoring agent")
    cols = st.columns(5)
    for col, (key, label) in zip(cols, [
        ("composite_score", "Composite"),
        ("requirement_coverage_score", "Requirement Coverage"),
        ("quality_score", "Rubric Quality"),
        ("solution_fit_score", "Solution Fit"),
        ("historical_similarity_score", "Precedent Similarity"),
    ]):
        with col:
            render_score_gauge(scores.get(key), label)

    missing = scores.get("missing_requirements") or []
    if missing:
        render_section_header("Requirements Not Addressed", icon="warning", badge=str(len(missing)))
        for item in missing:
            st.markdown(f"- {item}")
    rubric = scores.get("rubric") or {}
    if rubric:
        render_section_header("Evaluator Rubric", icon="grading")
        for item in rubric.get("criteria", []):
            st.markdown(f"- **{item['criterion']}** — {item['score']:.1f}/10. {item.get('comment', '')}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Strengths**")
            for s in rubric.get("strengths", []):
                st.markdown(f"- {s}")
        with c2:
            st.markdown("**Recommendations**")
            for s in rubric.get("recommendations", []):
                st.markdown(f"- {s}")

    render_token_usage(result.get("token_usage"))
    from utils.agent_trace import render_agent_trace

    render_agent_trace(result.get("agent_trace"), title="Match Pipeline Timeline")
    with st.expander("Raw response"):
        st.json({k: v for k, v in result.items() if k not in ("agent_trace",)})
