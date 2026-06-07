"""RFP.ai — Multi-Agent RFP Response Engine · Executive Dashboard."""
import streamlit as st

from utils.theme import (
    apply_theme,
    render_empty_state,
    render_header,
    render_section_header,
    render_sidebar,
    render_stat_card,
)

st.set_page_config(
    page_title="RFP.ai · Multi-Agent RFP Engine",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


# ── Login ───────────────────────────────────────────────────────────────
def render_login() -> None:
    render_header(title="Sign In")
    st.markdown(
        """
        <div class="rfp-hero">
            <div class="rfp-kicker">Multi-Agent Platform</div>
            <h1 class="rfp-title">RFP Response Engine</h1>
            <p class="rfp-copy">
                AI-orchestrated proposal generation powered by autonomous agents.
                Structure requirements, retrieve evidence, draft sections, and score
                responses — all through an intelligent agentic pipeline.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_form, col_info = st.columns([1, 1], gap="large")
    with col_form:
        st.markdown(
            '<div class="rfp-panel">'
            '<div class="info-card-title">Platform Access</div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email = st.text_input("Email", value="demo@rfp.ai")
            password = st.text_input("Password", value="demo123", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            if email.strip() and password.strip():
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip()
                st.rerun()
            st.error("Enter any email and password to continue.")

    with col_info:
        st.markdown(
            """
            <div class="rfp-panel">
                <div class="info-card-title">Agent Pipeline</div>
                <div style="margin-top:0.5rem">
                    <div class="pipeline-flow">
                        <span class="pipeline-step completed">User Input</span>
                        <span class="pipeline-arrow">→</span>
                        <span class="pipeline-step completed">Request Structuring</span>
                        <span class="pipeline-arrow">→</span>
                        <span class="pipeline-step completed">Knowledge Retrieval</span>
                        <span class="pipeline-arrow">→</span>
                        <span class="pipeline-step completed">Section Generation</span>
                        <span class="pipeline-arrow">→</span>
                        <span class="pipeline-step completed">Validation</span>
                        <span class="pipeline-arrow">→</span>
                        <span class="pipeline-step done-step">Final Response</span>
                    </div>
                </div>
                <div style="margin-top:1rem;font-size:0.85rem;color:var(--text-secondary);line-height:1.6">
                    The supervisor LLM orchestrates autonomous agents through a
                    plan-execute loop with replanning on failure, ensuring high-quality
                    proposal responses grounded in historical evidence.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Init ────────────────────────────────────────────────────────────────
if "workflow_results" not in st.session_state:
    st.session_state["workflow_results"] = []

if not st.session_state.get("authenticated"):
    render_login()
    st.stop()

render_sidebar()
render_header(title="Dashboard")

# ── Executive Overview Hero ─────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Executive Overview</div>
        <h1 class="rfp-title">Multi-Agent RFP Response Engine</h1>
        <p class="rfp-copy">
            AI-powered proposal generation with autonomous agent orchestration.
            Create new proposals, revise sections, detect intent from sales conversations,
            research vendors, and search your knowledge base.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Metrics Row ─────────────────────────────────────────────────────────
results = st.session_state["workflow_results"]
sections_generated = sum(len(item.get("sections", [])) for item in results)
latest = st.session_state.get("latest_result", {})
latest_score = latest.get("scores", {}).get("composite_score")

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_stat_card("Total Workflows", str(len(results)), icon="account_tree")
with c2:
    render_stat_card("Sections Generated", str(sections_generated), icon="description")
with c3:
    score_str = f"{latest_score:.2f}" if latest_score is not None else "--"
    render_stat_card("Latest Score", score_str, icon="speed")
with c4:
    render_stat_card("Knowledge Base", "Active", sub="pgvector + RAG", icon="database")

st.write("")

# ── Agent Collaboration Panel ───────────────────────────────────────────
render_section_header("Agent Collaboration Panel", icon="smart_toy", badge="7 agents")

a1, a2, a3, a4 = st.columns(4)
agents = [
    ("Request Structuring", "Parses RFP text into structured requirements, vendors, and solution types", "psychology", "blue"),
    ("Knowledge Retrieval", "Searches pgvector index for relevant historical proposal chunks", "search", "teal"),
    ("Section Generation", "Drafts proposal sections using Qwen 2.5 7B with RAG context", "edit_note", "blue"),
    ("Validation & Scoring", "Checks requirement coverage and computes composite quality scores", "verified_user", "teal"),
]
for col, (name, desc, icon, color) in zip([a1, a2, a3, a4], agents):
    with col:
        st.markdown(
            f'<div class="agent-card">'
            f'<div class="agent-card-header">'
            f'<div class="agent-card-icon {color}"><span class="material-symbols-outlined">{icon}</span></div>'
            f'<div><div class="agent-card-name">{name}</div>'
            f'<div class="agent-card-role">autonomous agent</div></div>'
            f'</div>'
            f'<div class="agent-card-desc">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.write("")

# ── Workflow Pipeline Visualization ─────────────────────────────────────
render_section_header("Workflow Execution Pipeline", icon="route", badge="plan-execute")

st.markdown(
    """
    <div class="rfp-panel">
        <div class="pipeline-flow">
            <span class="pipeline-step">pick_intent</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">make_plan</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">structure_request</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">compare_solutions</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">retrieve_evidence</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">generate_sections</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">validate_section</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">score_proposal</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step done-step">done</span>
        </div>
        <div style="display:flex;gap:1rem;margin-top:0.75rem;flex-wrap:wrap">
            <span class="status-chip active">Budget: 12 tool calls</span>
            <span class="status-chip processing">Max replans: 2</span>
            <span class="status-chip queued">LLM: Qwen 2.5 7B</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ── Recent Proposals / Quick Actions ────────────────────────────────────
left_col, right_col = st.columns([1.2, 0.8], gap="large")

with left_col:
    render_section_header("Recent Proposals", icon="history", badge=f"{len(results)} total")
    if not results:
        render_empty_state(
            "No proposals yet",
            "Create your first proposal from the New Proposal page to see it here.",
            icon="draft",
        )
    else:
        for i, r in enumerate(reversed(results[-5:])):
            wf_id = r.get("workflow_id", "unknown")[:12]
            status = r.get("status", "completed")
            n_sections = len(r.get("sections", []))
            score = r.get("scores", {}).get("composite_score")
            score_str = f"{score:.2f}" if score else "--"
            title = r.get("_pdf_title", f"Workflow {wf_id}")
            chip_cls = "active" if status == "completed" else "processing"
            st.markdown(
                f'<div class="info-card" style="margin-bottom:0.5rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div>'
                f'<div style="font-weight:600;font-size:0.9rem;color:var(--text)">{title}</div>'
                f'<div style="font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);margin-top:2px">ID: {wf_id} · {n_sections} sections</div>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span class="status-chip {chip_cls}">{status}</span>'
                f'<span style="font-family:var(--font-mono);font-weight:600;font-size:0.9rem;color:var(--text)">{score_str}</span>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

with right_col:
    render_section_header("Quick Actions", icon="bolt")
    st.page_link("pages/1_new_proposal.py", label="New Proposal", use_container_width=True)
    st.page_link("pages/2_revision.py", label="Section Revision", use_container_width=True)
    st.page_link("pages/3_document_match.py", label="Document Match", use_container_width=True)
    st.page_link("pages/4_intent_detection.py", label="Intent Detection", use_container_width=True)
    st.page_link("pages/5_market_research.py", label="Market Research", use_container_width=True)
    st.page_link("pages/6_ingestion.py", label="Document Ingestion", use_container_width=True)
    st.page_link("pages/7_search.py", label="Retrieval Explorer", use_container_width=True)
