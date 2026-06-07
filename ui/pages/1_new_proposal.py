"""New Proposal Generation — guided RFP intake with agent orchestration."""
import re

import streamlit as st

from utils.theme import (
    apply_theme,
    render_header,
    render_score_gauge,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="New Proposal · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="New Proposal")

COMPANY_OPTIONS = [
    "Vodafone Idea", "Bharti Airtel", "Reliance Jio", "Tata Communications",
    "Nokia", "Ericsson", "Huawei", "Other",
]
INDUSTRY_OPTIONS = [
    "Telecommunications", "Healthcare", "Financial Services",
    "Retail", "Manufacturing", "Public Sector", "Other",
]
SOLUTION_OPTIONS = {
    "AIOps Operations": "aiops_operations",
    "AIOps Observability": "aiops_observability",
    "General AIOps Platform": "aiops_general",
}
SECTION_OPTIONS = {
    "Executive summary": "executive_summary",
    "Solution overview": "solution_overview",
    "Implementation plan": "implementation_plan",
    "Pricing notes": "pricing_notes",
}
PRIORITY_OPTIONS = [
    "Reduce MTTR", "Improve incident response", "Centralize monitoring",
    "Automate root-cause analysis", "Optimize operations cost",
    "Improve SLA visibility", "Vendor-neutral integration",
]


def clean_phone(value: str) -> str:
    return re.sub(r"[^\d+() -]", "", value).strip()


def build_rfp_request(
    *, company_name: str, contact_name: str, phone_number: str,
    industry: str, solution_label: str, priorities: list[str],
    request_text: str, user_instruction: str,
) -> str:
    priority_text = ", ".join(priorities) if priorities else "Use retrieved historical evidence to infer priorities."
    notes = request_text.strip() or "The user provided minimal notes. Use the selected company, industry, solution, and priorities to draft a complete proposal response."
    instruction = user_instruction.strip() or "Keep the response practical, client-ready, and grounded in retrieved proposal evidence."
    return f"""Client company: {company_name}
Contact name: {contact_name}
Contact phone: {phone_number}
Industry: {industry}
Requested solution: {solution_label}
Business priorities: {priority_text}
User RFP notes: {notes}
Drafting instruction: {instruction}"""


if not st.session_state.get("authenticated"):
    st.warning("Please log in from the Home page to access proposal generation.")
    st.stop()

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Guided RFP Intake</div>
        <h1 class="rfp-title">Create Proposal</h1>
        <p class="rfp-copy">
            Fill in client details and RFP notes. The agent pipeline will structure
            requirements, retrieve evidence, generate sections, and score the response.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Agent pipeline preview ──────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-panel" style="margin-bottom:1.2rem">
        <div style="font-size:0.72rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:var(--text-muted);margin-bottom:0.5rem;font-family:var(--font-mono)">
            Agent Execution Pipeline
        </div>
        <div class="pipeline-flow">
            <span class="pipeline-step">structure_request</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">compare_solutions</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">retrieve + generate + validate</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">score_proposal</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step done-step">done</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Form ────────────────────────────────────────────────────────────────
with st.form("proposal_form"):
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        render_section_header("Client Details", icon="person", badge="required")
        contact_name = st.text_input("Contact Name", placeholder="Aarav Mehta")
        phone_number = st.text_input("Phone Number", placeholder="+91 98765 43210")
        selected_company = st.selectbox("Company", COMPANY_OPTIONS, index=0)
        custom_company = ""
        if selected_company == "Other":
            custom_company = st.text_input("Company Name", placeholder="Enter company name")
        company_name = custom_company.strip() if selected_company == "Other" else selected_company
        industry = st.selectbox("Industry", INDUSTRY_OPTIONS, index=0)
        solution_label = st.selectbox("Solution Type", list(SOLUTION_OPTIONS.keys()), index=0)
        priorities = st.multiselect(
            "Business Priorities",
            PRIORITY_OPTIONS,
            default=["Reduce MTTR", "Improve incident response", "Centralize monitoring"],
        )

    with right:
        render_section_header("RFP Requirements", icon="description", badge="input")
        request_text = st.text_area(
            "RFP Notes",
            height=180,
            placeholder="Example: Need an AIOps proposal for telecom network operations. Focus on incident reduction, alarm correlation, dashboards, and rollout plan.",
        )
        target_section_labels = st.multiselect(
            "Target Sections",
            list(SECTION_OPTIONS.keys()),
            default=["Executive summary"],
        )
        user_instruction = st.text_input(
            "Special Instructions",
            placeholder="Example: Make it executive-friendly and ROI focused",
        )
        fast_mode = st.checkbox(
            "Fast PDF mode",
            value=True,
            help="Skips local Qwen generation and creates a structured RAG-backed draft much faster.",
        )

    submitted = st.form_submit_button("Generate Proposal", type="primary", use_container_width=True)

# ── Execute ─────────────────────────────────────────────────────────────
if submitted:
    phone = clean_phone(phone_number)
    if not contact_name.strip():
        st.error("Please enter the contact name.")
        st.stop()
    if not company_name:
        st.error("Please select or enter the company name.")
        st.stop()
    if not phone:
        st.error("Please enter the phone number.")
        st.stop()

    from utils.api_client import create_workflow_run

    selected_sections = [SECTION_OPTIONS[label] for label in target_section_labels] or [
        "executive_summary", "solution_overview", "implementation_plan",
    ]
    solution_type = SOLUTION_OPTIONS[solution_label]
    enriched_request_text = build_rfp_request(
        company_name=company_name, contact_name=contact_name.strip(),
        phone_number=phone, industry=industry, solution_label=solution_label,
        priorities=priorities, request_text=request_text, user_instruction=user_instruction,
    )
    metadata = {
        "client_name": company_name, "contact_name": contact_name.strip(),
        "phone_number": phone, "selected_company": company_name,
        "solution_label": solution_label, "priorities": priorities, "fast_mode": fast_mode,
    }

    spinner_text = (
        "Running retrieval, fast drafting, validation, scoring, and PDF preparation..."
        if fast_mode else
        "Running retrieval, local Qwen generation, validation, scoring, and PDF preparation..."
    )
    with st.spinner(spinner_text):
        try:
            result = create_workflow_run(
                request_text=enriched_request_text,
                title=f"{company_name} {solution_label} Proposal",
                industry=industry, solution_type=solution_type,
                user_instruction=user_instruction or None,
                target_sections=selected_sections, metadata=metadata,
            )
        except Exception as exc:
            st.error(f"Workflow failed: {exc}")
            st.stop()

    if "workflow_results" not in st.session_state:
        st.session_state["workflow_results"] = []
    result["_pdf_metadata"] = metadata
    result["_pdf_title"] = f"{company_name} {solution_label} Proposal"
    st.session_state["workflow_results"].append(result)
    st.session_state["latest_result"] = result
    st.session_state["latest_pdf_metadata"] = metadata
    st.session_state["latest_pdf_title"] = f"{company_name} {solution_label} Proposal"

    st.success(f"Workflow `{result['workflow_id']}` completed successfully.")

    # ── PDF Download ────────────────────────────────────────────────────
    from utils.pdf_export import build_proposal_pdf

    pdf_bytes = build_proposal_pdf(
        workflow_result=result, metadata=metadata,
        title=f"{company_name} {solution_label} Proposal",
    )
    st.download_button(
        "Download Proposal PDF",
        data=pdf_bytes,
        file_name=f"{company_name.lower().replace(' ', '_')}_proposal.pdf",
        mime="application/pdf", type="primary", use_container_width=True,
    )

    # ── Scores ──────────────────────────────────────────────────────────
    scores = result.get("scores", {})
    if scores:
        render_section_header("Response Quality Metrics", icon="speed", badge="scoring agent")
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            render_score_gauge(scores.get("composite_score", 0), "Composite")
        with sc2:
            render_score_gauge(scores.get("requirement_coverage_score", 0), "Requirement Coverage")
        with sc3:
            render_score_gauge(scores.get("solution_fit_score", 0), "Solution Fit")
        with sc4:
            render_score_gauge(scores.get("historical_similarity_score", 0), "Historical Similarity")

    # ── Agent Trace ─────────────────────────────────────────────────────
    from utils.agent_trace import render_agent_trace
    render_agent_trace(result.get("agent_trace"), title="Agent Orchestration Timeline")

    # ── Pipeline Steps ──────────────────────────────────────────────────
    with st.expander("Pipeline Step Summaries", expanded=False):
        for i, summary in enumerate(result.get("step_summaries", []), 1):
            st.markdown(f"**Step {i}:** {summary}")

    # ── Generated Sections ──────────────────────────────────────────────
    render_section_header("Generated Sections", icon="article", badge=f"{len(result.get('sections', []))} sections")
    sections = result.get("sections", [])
    if not sections:
        st.warning("No sections were generated.")
    else:
        tabs = st.tabs([s.get("section_key", f"Section {i}") for i, s in enumerate(sections, 1)])
        for tab, section in zip(tabs, sections):
            with tab:
                st.markdown(
                    '<div class="result-box">',
                    unsafe_allow_html=True,
                )
                st.markdown(section.get("draft_text", "_No text generated._"))
                st.markdown("</div>", unsafe_allow_html=True)

                citations = section.get("citations", [])
                if citations:
                    with st.expander("Citations"):
                        for citation in citations:
                            st.markdown(f"- `{citation}`")

                validation = section.get("validation", {})
                if validation:
                    with st.expander("Validation Details"):
                        coverage = validation.get("requirement_coverage", {})
                        if coverage:
                            covered = sum(1 for v in coverage.values() if v)
                            total = len(coverage)
                            st.progress(covered / total if total else 0, text=f"{covered}/{total} requirements covered")
                        missing = validation.get("missing_items", [])
                        if missing:
                            st.warning("Missing items: " + ", ".join(missing))
