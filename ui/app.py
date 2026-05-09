"""RFP Proposal Platform - Streamlit UI."""
import streamlit as st

from utils.theme import (
    apply_theme,
    render_header,
    render_sidebar,
)

st.set_page_config(
    page_title="agentQA · RFP Pro",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


def render_login() -> None:
    render_header(title="Sign In")
    st.markdown('<div class="rfp-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="rfp-hero">
            <div class="rfp-kicker">Secure workspace</div>
            <h1 class="rfp-title">RFP Proposal Platform</h1>
            <p class="rfp-copy">
                Sign in to draft proposal sections from short RFP notes, retrieve similar historical responses,
                and hand the heavy lifting to the backend RAG pipeline.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.95, 1.05], gap="large")
    with left:
        st.markdown("### Demo Login")
        with st.form("login_form"):
            email = st.text_input("Email", value="demo@rfp.ai")
            password = st.text_input("Password", value="demo123", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if email.strip() and password.strip():
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip()
                st.rerun()
            st.error("Enter any email and password to continue.")

    with right:
        st.markdown("### What happens after login")
        st.markdown(
            """
            - Capture contact, company, industry, solution, and short RFP notes.
            - Send those fields to the FastAPI workflow endpoint.
            - Let retrieval, generation, validation, and scoring agents create the draft.
            """
        )
    st.markdown("</div>", unsafe_allow_html=True)


if "workflow_results" not in st.session_state:
    st.session_state["workflow_results"] = []

if not st.session_state.get("authenticated"):
    render_login()
    st.stop()

render_sidebar()
render_header(title="Home")
st.markdown('<div class="rfp-shell">', unsafe_allow_html=True)
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Proposal operations</div>
        <h1 class="rfp-title">Generate stronger RFP responses with less typing.</h1>
        <p class="rfp-copy">
            Use the New Proposal page to provide the client, solution, contact details, and a short request.
            The backend then retrieves matching historical material and drafts section-ready content.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Workflows", value=len(st.session_state["workflow_results"]))
with col2:
    sections_generated = sum(len(item.get("sections", [])) for item in st.session_state["workflow_results"])
    st.metric("Sections Generated", value=sections_generated)
with col3:
    latest_score = st.session_state.get("latest_result", {}).get("scores", {}).get("composite_score")
    st.metric("Latest Composite Score", value=f"{latest_score:.2f}" if latest_score is not None else "--")

st.info("Open **New Proposal** from the sidebar to start a guided RFP intake.")
st.markdown("</div>", unsafe_allow_html=True)
