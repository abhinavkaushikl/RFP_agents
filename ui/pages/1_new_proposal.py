"""New Proposal — RFP intake and multi-agent section generation."""
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

if not st.session_state.get("authenticated"):
    st.warning("Please sign in from the Home page to create proposals.")
    st.stop()

from utils.api_client import APIError, create_workflow_run, extract_text  # noqa: E402
from utils.profile import active_profile_name, get_active_profile, section_options, section_title  # noqa: E402
from utils.token_usage import accumulate_session_usage, render_token_usage  # noqa: E402

profile = get_active_profile()
profile_name = active_profile_name()
INFER = "Let the agents infer it"


def clean_phone(value: str) -> str:
    return re.sub(r"[^\d+() -]", "", value).strip()


# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="rfp-hero">
        <div class="rfp-kicker">Guided RFP Intake · profile: {profile.get("display_name", profile_name)}</div>
        <h1 class="rfp-title">Create Proposal</h1>
        <p class="rfp-copy">
            Paste or upload the RFP. The agents extract the requirements, match them to your offerings,
            retrieve precedent from past proposals, draft each section, and score the response.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Optional RFP upload (outside the form so the text box can be filled) ──
with st.expander("Upload the RFP document (PDF, Word, Markdown, or text)", expanded=False):
    upload = st.file_uploader("RFP file", type=["pdf", "docx", "md", "txt"], key="rfp_upload")
    if upload is not None and st.button("Extract text", key="extract_rfp"):
        try:
            extracted = extract_text(upload.name, upload.getvalue(), profile=profile_name)
            st.session_state["rfp_text"] = extracted["text"]
            st.success(f"Extracted {extracted['characters']:,} characters from {upload.name}.")
        except APIError as exc:
            st.error(f"Could not read the file: {exc}")

sections_map = section_options(profile)
default_titles = [section_title(profile, k) for k in profile.get("default_sections", []) if k]
offering_labels = {o["name"]: o["code"] for o in profile.get("offerings", [])}
industries = profile.get("industries") or ["Other"]

with st.form("proposal_form"):
    left, right = st.columns([0.95, 1.05], gap="large")
    with left:
        render_section_header("Client", icon="business", badge="required")
        client_name = st.text_input("Client organization", placeholder="e.g., Contoso Health Network")
        title = st.text_input("Proposal title", placeholder="e.g., Patient Portal Modernization")
        industry = st.selectbox("Industry", ["Not specified", *industries], index=0)
        solution_choice = st.selectbox(
            "Solution / offering",
            [INFER, *offering_labels.keys(), "Other (type below)"],
            help="Offerings come from the active domain profile.",
        )
        solution_custom = st.text_input("Other solution type", placeholder="e.g., Data platform migration")
        render_section_header("Contact (kept out of the requirements)", icon="person")
        contact_name = st.text_input("Contact name", placeholder="Optional")
        contact_email = st.text_input("Contact email", placeholder="Optional")
        contact_phone = st.text_input("Contact phone", placeholder="Optional")

    with right:
        render_section_header("RFP", icon="description", badge="input")
        request_text = st.text_area(
            "RFP text or notes",
            value=st.session_state.get("rfp_text", ""),
            height=260,
            placeholder="Paste the RFP: scope, requirements, evaluation criteria, timeline, budget…",
        )
        target_titles = st.multiselect("Sections to draft", list(sections_map), default=default_titles)
        priorities = st.text_input("Win themes or priorities (comma-separated)", placeholder="e.g., speed to value, data security")
        user_instruction = st.text_input("Special instructions", placeholder="e.g., Executive-friendly, emphasize ROI")
        reuse_cache = st.checkbox(
            "Reuse cached sections when nothing changed",
            value=True,
            help="Identical inputs return the stored section instantly with zero tokens. Untick to regenerate.",
        )

    submitted = st.form_submit_button("Generate Proposal", type="primary", use_container_width=True)

# ── Execute ─────────────────────────────────────────────────────────────
if submitted:
    if not client_name.strip():
        st.error("Enter the client organization.")
        st.stop()
    if len(request_text.strip()) < 40:
        st.error("Paste the RFP text (at least a few sentences) or upload the RFP file.")
        st.stop()

    instruction_bits = [user_instruction.strip()] if user_instruction.strip() else []
    if priorities.strip():
        instruction_bits.append(f"Win themes to emphasize: {priorities.strip()}")
    solution_type = None
    if solution_choice in offering_labels:
        solution_type = offering_labels[solution_choice]
    elif solution_choice.startswith("Other") and solution_custom.strip():
        solution_type = solution_custom.strip()
    proposal_title = title.strip() or f"{client_name.strip()} Proposal"
    metadata = {
        "client_name": client_name.strip(),
        "contact_name": contact_name.strip(),
        "contact_email": contact_email.strip(),
        "phone_number": clean_phone(contact_phone),
    }

    with st.spinner("Agents are structuring the RFP, retrieving precedent, drafting sections, and scoring…"):
        try:
            result = create_workflow_run(
                request_text=request_text.strip(),
                title=proposal_title,
                client_name=client_name.strip(),
                industry=None if industry == "Not specified" else industry,
                solution_type=solution_type,
                user_instruction=". ".join(instruction_bits) or None,
                target_sections=[sections_map[t] for t in target_titles] or None,
                profile=profile_name,
                cache_policy="use" if reuse_cache else "refresh",
                metadata=metadata,
            )
        except APIError as exc:
            hint = f" Retry in {exc.retry_after}s — finished sections are cached." if exc.retry_after else ""
            st.error(f"Workflow failed: {exc}.{hint}")
            st.stop()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Workflow failed: {exc}")
            st.stop()

    result["_pdf_metadata"] = metadata
    result["_pdf_title"] = proposal_title
    st.session_state.setdefault("workflow_results", []).append(result)
    st.session_state["latest_result"] = result
    st.session_state["latest_pdf_metadata"] = metadata
    st.session_state["latest_pdf_title"] = proposal_title
    accumulate_session_usage(result.get("token_usage"))

    status = result.get("status")
    if status == "completed":
        st.success(f"Workflow `{result['workflow_id']}` completed.")
    else:
        st.warning(f"Workflow `{result['workflow_id']}` finished with status **{status}**.")
    for warning in result.get("warnings", []):
        st.info(warning)

    from utils.pdf_export import build_proposal_pdf

    st.download_button(
        "Download Proposal PDF",
        data=build_proposal_pdf(workflow_result=result, metadata=metadata, title=proposal_title),
        file_name=f"{re.sub(r'[^a-z0-9]+', '_', client_name.lower()).strip('_') or 'client'}_proposal.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

    scores = result.get("scores", {})
    if scores:
        render_section_header("Response Quality", icon="speed", badge="scoring agent")
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
        rubric = scores.get("rubric") or {}
        if rubric:
            with st.expander("Evaluator rubric"):
                for item in rubric.get("criteria", []):
                    st.markdown(f"- **{item['criterion']}** — {item['score']:.1f}/10. {item.get('comment', '')}")
                if rubric.get("weaknesses"):
                    st.markdown("**Weaknesses:** " + "; ".join(rubric["weaknesses"]))
                if rubric.get("recommendations"):
                    st.markdown("**Recommendations:** " + "; ".join(rubric["recommendations"]))
        if scores.get("missing_requirements"):
            st.warning("Requirements not clearly addressed: " + "; ".join(scores["missing_requirements"][:10]))

    render_token_usage(result.get("token_usage"))

    request = result.get("request") or {}
    if request:
        with st.expander(f"Extracted brief — {len(request.get('requirements', []))} requirements"):
            for req in request.get("requirement_details", []):
                st.markdown(f"- `{req.get('id')}` **{req.get('priority', '')}** · {req.get('text')} _({req.get('category')})_")
            if request.get("ambiguity_flags"):
                st.markdown("**Clarify with the buyer:** " + "; ".join(request["ambiguity_flags"]))

    from utils.agent_trace import render_agent_trace

    render_agent_trace(result.get("agent_trace"), title="Agent Orchestration Timeline")

    sections = result.get("sections", [])
    render_section_header("Generated Sections", icon="article", badge=f"{len(sections)} sections")
    if not sections:
        st.warning("No sections were generated.")
    else:
        tabs = st.tabs([s.get("title") or s.get("section_key", f"Section {i}") for i, s in enumerate(sections, 1)])
        for tab, section in zip(tabs, sections):
            with tab:
                if section.get("error"):
                    st.error(f"This section failed: {section['error']}")
                    continue
                usage = section.get("usage") or {}
                mode = section.get("generation_mode")
                if section.get("cache_hit"):
                    badge = "served from cache · 0 tokens"
                elif mode in ("fallback", "template"):
                    badge = "outline only (model not used)"
                else:
                    badge = f"{section.get('model')} · {int(usage.get('total_tokens') or 0):,} tokens"
                st.caption(f"{section.get('word_count', 0)} words · {badge}")
                st.markdown(section.get("draft_text") or "_No text generated._")
                validation = section.get("validation") or {}
                details = validation.get("coverage_details") or []
                if details:
                    with st.expander("Requirement coverage"):
                        covered = sum(1 for d in details if d.get("covered"))
                        st.progress(covered / len(details), text=f"{covered}/{len(details)} requirements addressed")
                        for d in details:
                            mark = "**Covered**" if d.get("covered") else "**Missing**"
                            st.markdown(f"- {mark} · {d['requirement']} _({d.get('method')}, {d.get('score', 0):.2f})_")
