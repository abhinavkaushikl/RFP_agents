"""Intent Detection — extract intent from sales conversations using sub-agents."""
from __future__ import annotations

import html
import json
from datetime import date

import streamlit as st

from utils.api_client import run_intent_detection
from utils.theme import (
    apply_theme,
    render_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Intent Detection · RFP.ai", page_icon="", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Intent Detection")

SESSION_KEY = "intent_detection_state"
FRAME_KEYS = (
    "problem_statement",
    "success_definition",
    "stakeholder_impact",
    "urgency_statement",
)
READINESS_STAGES = (
    "Cold",
    "Exploring",
    "Interested",
    "Evaluation Stage",
    "High Intent",
    "Ready to Buy",
)
FIT_STAGES = (
    "Poor Fit",
    "Partial Fit",
    "Qualified Fit",
    "Strong Fit",
    "Strategic Fit",
)


def _default_buyer_readiness() -> dict:
    return {
        "readiness_rating": 0,
        "buyer_readiness_score": 0,
        "readiness_stage": "Cold",
        "confidence": 0.0,
        "reasoning": [],
        "buying_gaps": "",
        "buyer_gaps": [],
        "stakeholder_coverage": {
            "stakeholders": [],
            "identified_roles": [],
            "missing_roles": [],
            "coverage_score": 0,
            "engagement_summary": "",
        },
        "intent_classification": {
            "primary_intent": "",
            "detected_intents": [],
            "summary": "",
            "confidence": 0.0,
        },
        "conversation_highlights": [],
        "recommended_next_actions": [],
    }


def _default_product_fit() -> dict:
    return {
        "notes": "",
        "product_fit_score": 0,
        "fit_stage": "Poor Fit",
        "confidence": 0.0,
        "fit_summary": "",
        "matched_capabilities": [],
        "product_gaps": [],
        "integration_fit": {
            "score": 0,
            "summary": "",
            "required_integrations": [],
            "risks": [],
        },
        "competitive_positioning": {
            "competitors_mentioned": [],
            "differentiators": [],
            "positioning_summary": "",
        },
        "risk_flags": [],
        "recommended_positioning": [],
        "recommended_next_actions": [],
    }


def _empty_state() -> dict:
    return {
        "raw_text": "",
        "file_name": "",
        "client_overview": {
            "opportunity_name": "", "client_name": "",
            "existing_relationship": "Unknown", "date_opened": None,
            "problem_statement": "", "success_definition": "",
            "stakeholder_impact": "", "urgency_statement": "",
        },
        "buyer_readiness": _default_buyer_readiness(),
        "product_fit": _default_product_fit(),
    }


def _ensure_buyer_state(state: dict) -> None:
    existing = state.setdefault("buyer_readiness", {})
    defaults = _default_buyer_readiness()
    for key, value in defaults.items():
        if key not in existing or existing[key] is None:
            existing[key] = value
    if not isinstance(existing.get("stakeholder_coverage"), dict):
        existing["stakeholder_coverage"] = defaults["stakeholder_coverage"]
    if not isinstance(existing.get("intent_classification"), dict):
        existing["intent_classification"] = defaults["intent_classification"]
    for list_key in ("reasoning", "buyer_gaps", "conversation_highlights", "recommended_next_actions"):
        if not isinstance(existing.get(list_key), list):
            existing[list_key] = []


def _ensure_product_fit_state(state: dict) -> None:
    existing = state.setdefault("product_fit", {})
    defaults = _default_product_fit()
    for key, value in defaults.items():
        if key not in existing or existing[key] is None:
            existing[key] = value
    if not isinstance(existing.get("integration_fit"), dict):
        existing["integration_fit"] = defaults["integration_fit"]
    if not isinstance(existing.get("competitive_positioning"), dict):
        existing["competitive_positioning"] = defaults["competitive_positioning"]
    for list_key in (
        "matched_capabilities",
        "product_gaps",
        "risk_flags",
        "recommended_positioning",
        "recommended_next_actions",
    ):
        if not isinstance(existing.get(list_key), list):
            existing[list_key] = []


def _problem_framing_payload(state: dict) -> dict[str, str]:
    client_overview = state.get("client_overview", {})
    return {key: client_overview.get(key, "") or "" for key in FRAME_KEYS}


def _has_problem_framing(state: dict) -> bool:
    return any(_problem_framing_payload(state).values())


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _score_to_stage(score: int) -> str:
    if score <= 15:
        return "Cold"
    if score <= 35:
        return "Exploring"
    if score <= 55:
        return "Interested"
    if score <= 70:
        return "Evaluation Stage"
    if score <= 88:
        return "High Intent"
    return "Ready to Buy"


def _fit_stage_from_score(score: int) -> str:
    if score <= 20:
        return "Poor Fit"
    if score <= 45:
        return "Partial Fit"
    if score <= 65:
        return "Qualified Fit"
    if score <= 85:
        return "Strong Fit"
    return "Strategic Fit"


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _chip(label: str, css_class: str = "queued") -> str:
    return f'<span class="status-chip {css_class}">{html.escape(str(label))}</span>'


if SESSION_KEY not in st.session_state:
    st.session_state[SESSION_KEY] = _empty_state()

state: dict = st.session_state[SESSION_KEY]
_ensure_buyer_state(state)
_ensure_product_fit_state(state)

# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Discovery Analysis</div>
        <h1 class="rfp-title">Detect Intent from Sales Conversations</h1>
        <p class="rfp-copy">
            Upload a meeting transcript or email thread. Sub-agents analyze client context,
            buyer intelligence, product fit, and executive problem framing.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Agent pipeline visualization ────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-panel" style="margin-bottom:1.2rem">
        <div class="pipeline-flow">
            <span class="pipeline-step">Upload Transcript</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">detect_intent_fields</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">frame_business_problem</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">analyze_buyer_intelligence</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">analyze_product_fit</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">Client Overview</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">Buyer Readiness</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step done-step">Product Fit</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Upload + right-side problem framing feature ─────────────────────────
input_col, feature_col = st.columns([0.62, 0.38], gap="large")

with input_col:
    render_section_header("Upload Conversation", icon="upload_file", badge="step 1")
    upload_col, run_col = st.columns([0.7, 0.3])

    with upload_col:
        uploaded = st.file_uploader(
            "Transcript or email thread (.txt, .md, .eml)",
            type=["txt", "md", "eml", "log"],
            accept_multiple_files=False,
            help="Plain text works best. Email .eml files are read as raw text.",
        )

    with run_col:
        st.write("")
        st.write("")
        run_clicked = st.button(
            "Run Intent Detection",
            use_container_width=True,
            disabled=uploaded is None,
        )

if uploaded is not None:
    try:
        raw_bytes = uploaded.read()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        st.error(f"Could not read file: {exc}")
        raw_text = ""
    state["raw_text"] = raw_text
    state["file_name"] = uploaded.name
    with input_col:
        with st.expander("Preview uploaded text", expanded=False):
            st.code(raw_text[:3000] + ("..." if len(raw_text) > 3000 else ""), language="text")

if run_clicked and state["raw_text"]:
    with st.spinner("Running intent detection sub-agents..."):
        try:
            result = run_intent_detection(
                transcript_text=state["raw_text"],
                file_name=state["file_name"],
            )
        except Exception as exc:
            st.error(f"Intent detection failed: {exc}")
            result = None

    if result:
        co = result.get("client_overview") or {}
        br = result.get("buyer_readiness") or {}
        pf = result.get("product_fit") or {}
        for key, value in co.items():
            if value:
                state["client_overview"][key] = value
        for key, value in br.items():
            if value not in (None, ""):
                state["buyer_readiness"][key] = value
        for key, value in pf.items():
            if value:
                state["product_fit"][key] = value
        st.success(result.get("summary", "Intent detection completed."))

        from utils.agent_trace import render_agent_trace
        render_agent_trace(result.get("agent_trace"), title="Intent Detection Timeline")

with feature_col:
    render_section_header("Problem Framing Feature", icon="psychology", badge="right side")
    framing_output = _problem_framing_payload(state)
    if _has_problem_framing(state):
        st.code(
            json.dumps(framing_output, indent=2, ensure_ascii=False),
            language="json",
        )
    else:
        st.markdown(
            """
            <div class="rfp-panel">
                <div class="info-card-title">AI Intent Detection and Problem Framing Agent</div>
                <div style="margin-top:0.75rem;display:grid;gap:0.5rem">
                    <span class="status-chip queued">Problem Statement</span>
                    <span class="status-chip queued">Success Definition</span>
                    <span class="status-chip queued">Stakeholder Impact</span>
                    <span class="status-chip queued">Urgency Statement</span>
                </div>
                <div style="margin-top:0.9rem;font-size:0.82rem;color:var(--text-secondary);line-height:1.55">
                    Upload a business document, email thread, meeting note, ticket, or opportunity
                    statement to generate concise executive problem framing.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Three sub-flows ─────────────────────────────────────────────────────
render_section_header("Review and Edit", icon="edit_note", badge="step 2")
tab_client, tab_readiness, tab_fit = st.tabs(
    ["Client Overview", "Buyer Readiness", "Product Fit"]
)

co = state["client_overview"]
br = state["buyer_readiness"]
pf = state["product_fit"]

with tab_client:
    st.caption("Auto-filled from the transcript where possible. Edit any field.")

    render_section_header("Opportunity", icon="work")
    c1, c2 = st.columns(2)
    with c1:
        co["opportunity_name"] = st.text_input(
            "Opportunity Name", value=co.get("opportunity_name", ""),
            placeholder="e.g., Vodafone AIOps Modernization",
        )
        co["client_name"] = st.text_input(
            "Client Name", value=co.get("client_name", ""),
            placeholder="e.g., Vodafone India",
        )
    with c2:
        relationship_options = ["Unknown", "New logo", "Existing customer", "Lapsed customer"]
        current_rel = co.get("existing_relationship") or "Unknown"
        if current_rel not in relationship_options:
            current_rel = "Unknown"
        co["existing_relationship"] = st.selectbox(
            "Existing Relationship",
            options=relationship_options,
            index=relationship_options.index(current_rel),
        )
        existing_date = co.get("date_opened")
        if isinstance(existing_date, str) and existing_date:
            try:
                existing_date = date.fromisoformat(existing_date)
            except ValueError:
                existing_date = None
        co["date_opened"] = st.date_input(
            "Date Opened", value=existing_date if existing_date else None,
        )

    st.divider()
    render_section_header("Problem Framing", icon="psychology")
    co["problem_statement"] = st.text_area(
        "Problem Statement", value=co.get("problem_statement", ""), height=100,
        placeholder="What is the client trying to solve?",
    )
    co["success_definition"] = st.text_area(
        "Success Definition", value=co.get("success_definition", ""), height=80,
        placeholder="What does winning look like for the client?",
    )
    c3, c4 = st.columns(2)
    with c3:
        co["stakeholder_impact"] = st.text_area(
            "Stakeholder Impact", value=co.get("stakeholder_impact", ""), height=100,
            placeholder="Who is affected? Roles, teams, business lines.",
        )
    with c4:
        co["urgency_statement"] = st.text_area(
            "Urgency Statement", value=co.get("urgency_statement", ""), height=100,
            placeholder="Why now? Deadlines, contractual triggers, budget cycles.",
        )

with tab_readiness:
    st.caption("Buyer readiness, conversion blockers, stakeholder coverage, and recommended next actions.")

    score_value = _safe_int(br.get("buyer_readiness_score"), _safe_int(br.get("readiness_rating")) * 10)
    score_value = max(0, min(100, score_value))
    br["buyer_readiness_score"] = st.slider(
        "Buyer Readiness Score",
        min_value=0,
        max_value=100,
        value=score_value,
    )
    br["readiness_rating"] = round(br["buyer_readiness_score"] / 10)
    br["readiness_stage"] = (
        br.get("readiness_stage")
        if br.get("readiness_stage") in READINESS_STAGES
        else _score_to_stage(br["buyer_readiness_score"])
    )

    confidence = max(0.0, min(1.0, _safe_float(br.get("confidence"))))
    intent = br.get("intent_classification") if isinstance(br.get("intent_classification"), dict) else {}
    intent_confidence = max(0.0, min(1.0, _safe_float(intent.get("confidence"))))

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Readiness Stage</div>
                <div style="margin-top:0.35rem;font-size:1.25rem;font-weight:700;color:var(--text)">
                    {html.escape(br["readiness_stage"])}
                </div>
                <div style="margin-top:0.35rem;font-family:var(--font-mono);font-size:0.85rem;color:var(--text-secondary)">
                    {br["buyer_readiness_score"]}/100
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Analysis Confidence</div>
                <div style="margin-top:0.35rem;font-size:1.25rem;font-weight:700;color:var(--text)">
                    {confidence:.0%}
                </div>
                <div style="margin-top:0.35rem;font-size:0.85rem;color:var(--text-secondary)">
                    Buyer intelligence confidence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        primary_intent = intent.get("primary_intent") or "Not detected"
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Primary Intent</div>
                <div style="margin-top:0.35rem;font-size:1.05rem;font-weight:700;color:var(--text)">
                    {html.escape(primary_intent)}
                </div>
                <div style="margin-top:0.35rem;font-family:var(--font-mono);font-size:0.85rem;color:var(--text-secondary)">
                    {intent_confidence:.0%} confidence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.progress(br["buyer_readiness_score"] / 100)

    render_section_header("Intent Summary", icon="radar")
    detected_intents = _as_list(intent.get("detected_intents"))
    if intent.get("summary") or detected_intents:
        st.write(intent.get("summary") or "")
        if detected_intents:
            st.markdown(
                '<div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-top:0.35rem">'
                + "".join(_chip(item, "active") for item in detected_intents)
                + "</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("Intent summary will appear after analysis.")

    render_section_header("Readiness Reasoning", icon="psychology")
    reasoning = _as_list(br.get("reasoning"))
    if reasoning:
        for item in reasoning:
            st.markdown(f"- {html.escape(str(item))}")
    else:
        st.info("Reasoning signals will appear after analysis.")

    render_section_header("Buyer Gap Analysis", icon="warning")
    gaps = [gap for gap in _as_list(br.get("buyer_gaps")) if isinstance(gap, dict)]
    if gaps:
        for gap in gaps:
            severity = gap.get("severity", "Medium")
            chip_class = "active" if severity == "Low" else "processing" if severity == "Medium" else "queued"
            st.markdown(
                f"""
                <div class="info-card" style="margin-bottom:0.65rem">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:0.75rem;flex-wrap:wrap">
                        <div style="font-weight:700;color:var(--text)">{html.escape(gap.get("gap_type", "Gap"))}</div>
                        {_chip(severity, chip_class)}
                    </div>
                    <div style="margin-top:0.45rem;color:var(--text-secondary);line-height:1.55">
                        {html.escape(gap.get("description", ""))}
                    </div>
                    <div style="margin-top:0.55rem;color:var(--text);line-height:1.55">
                        <strong>Recommendation:</strong> {html.escape(gap.get("recommendation", ""))}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Gap cards will appear after analysis.")

    render_section_header("Stakeholder Coverage", icon="groups")
    coverage = br.get("stakeholder_coverage") if isinstance(br.get("stakeholder_coverage"), dict) else {}
    coverage_score = max(0, min(100, _safe_int(coverage.get("coverage_score"))))
    identified_roles = _as_list(coverage.get("identified_roles"))
    missing_roles = _as_list(coverage.get("missing_roles"))
    st.progress(coverage_score / 100)
    st.markdown(
        f'<div style="font-family:var(--font-mono);font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.6rem">'
        f'Coverage score: {coverage_score}/100</div>',
        unsafe_allow_html=True,
    )
    if coverage.get("engagement_summary"):
        st.write(coverage["engagement_summary"])
    role_cols = st.columns(2)
    with role_cols[0]:
        st.markdown("**Identified Roles**")
        if identified_roles:
            st.markdown(
                '<div style="display:flex;gap:0.4rem;flex-wrap:wrap">'
                + "".join(_chip(item, "active") for item in identified_roles)
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("No roles detected yet.")
    with role_cols[1]:
        st.markdown("**Missing Roles**")
        if missing_roles:
            st.markdown(
                '<div style="display:flex;gap:0.4rem;flex-wrap:wrap">'
                + "".join(_chip(item, "queued") for item in missing_roles)
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("No missing roles detected.")

    stakeholders = [item for item in _as_list(coverage.get("stakeholders")) if isinstance(item, dict)]
    if stakeholders:
        st.dataframe(
            [
                {
                    "Name": item.get("name", "Unknown"),
                    "Role": item.get("role", ""),
                    "Category": item.get("category", ""),
                    "Influence": item.get("influence_level", ""),
                    "Engagement": item.get("engagement_quality", ""),
                    "Evidence": item.get("evidence", ""),
                }
                for item in stakeholders
            ],
            use_container_width=True,
            hide_index=True,
        )

    n1, n2 = st.columns(2)
    with n1:
        render_section_header("Conversation Highlights", icon="format_quote")
        highlights = _as_list(br.get("conversation_highlights"))
        if highlights:
            for item in highlights:
                st.markdown(f"- {html.escape(str(item))}")
        else:
            st.caption("No highlights generated yet.")
    with n2:
        render_section_header("Recommended Next Actions", icon="task_alt")
        actions = _as_list(br.get("recommended_next_actions"))
        if actions:
            for item in actions:
                st.markdown(f"- {html.escape(str(item))}")
        else:
            st.caption("No actions generated yet.")

with tab_fit:
    st.caption("Capability fit, integration fit, competitive context, product gaps, and sales positioning.")

    fit_score = max(0, min(100, _safe_int(pf.get("product_fit_score"))))
    pf["product_fit_score"] = st.slider(
        "Product Fit Score",
        min_value=0,
        max_value=100,
        value=fit_score,
    )
    pf["fit_stage"] = (
        pf.get("fit_stage")
        if pf.get("fit_stage") in FIT_STAGES
        else _fit_stage_from_score(pf["product_fit_score"])
    )
    fit_confidence = max(0.0, min(1.0, _safe_float(pf.get("confidence"))))
    integration = pf.get("integration_fit") if isinstance(pf.get("integration_fit"), dict) else {}
    integration_score = max(0, min(100, _safe_int(integration.get("score"))))
    competitive = (
        pf.get("competitive_positioning")
        if isinstance(pf.get("competitive_positioning"), dict)
        else {}
    )

    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Fit Stage</div>
                <div style="margin-top:0.35rem;font-size:1.25rem;font-weight:700;color:var(--text)">
                    {html.escape(pf["fit_stage"])}
                </div>
                <div style="margin-top:0.35rem;font-family:var(--font-mono);font-size:0.85rem;color:var(--text-secondary)">
                    {pf["product_fit_score"]}/100
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f2:
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Fit Confidence</div>
                <div style="margin-top:0.35rem;font-size:1.25rem;font-weight:700;color:var(--text)">
                    {fit_confidence:.0%}
                </div>
                <div style="margin-top:0.35rem;font-size:0.85rem;color:var(--text-secondary)">
                    Product-fit confidence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f3:
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;font-weight:600">Integration Fit</div>
                <div style="margin-top:0.35rem;font-size:1.25rem;font-weight:700;color:var(--text)">
                    {integration_score}/100
                </div>
                <div style="margin-top:0.35rem;font-size:0.85rem;color:var(--text-secondary)">
                    Stack and implementation fit
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.progress(pf["product_fit_score"] / 100)

    render_section_header("Fit Summary", icon="fact_check")
    fit_summary = pf.get("fit_summary") or pf.get("notes") or ""
    if fit_summary:
        st.write(fit_summary)
    else:
        st.info("Product fit summary will appear after analysis.")

    render_section_header("Matched Capabilities", icon="extension")
    matches = [item for item in _as_list(pf.get("matched_capabilities")) if isinstance(item, dict)]
    if matches:
        st.dataframe(
            [
                {
                    "Buyer Need": item.get("buyer_need", ""),
                    "Matched Capability": item.get("matched_capability", ""),
                    "Strength": item.get("fit_strength", ""),
                    "Evidence": item.get("evidence", ""),
                }
                for item in matches
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Capability matches will appear after analysis.")

    render_section_header("Product Gap Analysis", icon="report_problem")
    product_gaps = [gap for gap in _as_list(pf.get("product_gaps")) if isinstance(gap, dict)]
    if product_gaps:
        for gap in product_gaps:
            severity = gap.get("severity", "Medium")
            chip_class = "active" if severity == "Low" else "processing" if severity == "Medium" else "queued"
            st.markdown(
                f"""
                <div class="info-card" style="margin-bottom:0.65rem">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:0.75rem;flex-wrap:wrap">
                        <div style="font-weight:700;color:var(--text)">{html.escape(gap.get("gap_type", "Gap"))}</div>
                        {_chip(severity, chip_class)}
                    </div>
                    <div style="margin-top:0.45rem;color:var(--text-secondary);line-height:1.55">
                        {html.escape(gap.get("description", ""))}
                    </div>
                    <div style="margin-top:0.55rem;color:var(--text);line-height:1.55">
                        <strong>Recommendation:</strong> {html.escape(gap.get("recommendation", ""))}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Product gap cards will appear after analysis.")

    i1, i2 = st.columns(2)
    with i1:
        render_section_header("Integration Fit", icon="hub")
        if integration.get("summary"):
            st.write(integration["summary"])
        required_integrations = _as_list(integration.get("required_integrations"))
        integration_risks = _as_list(integration.get("risks"))
        if required_integrations:
            st.markdown("**Required Integrations**")
            st.markdown(
                '<div style="display:flex;gap:0.4rem;flex-wrap:wrap">'
                + "".join(_chip(item, "active") for item in required_integrations)
                + "</div>",
                unsafe_allow_html=True,
            )
        if integration_risks:
            st.markdown("**Integration Risks**")
            for item in integration_risks:
                st.markdown(f"- {html.escape(str(item))}")
    with i2:
        render_section_header("Competitive Positioning", icon="target")
        competitors = _as_list(competitive.get("competitors_mentioned"))
        differentiators = _as_list(competitive.get("differentiators"))
        if competitive.get("positioning_summary"):
            st.write(competitive["positioning_summary"])
        if competitors:
            st.markdown("**Competitors Mentioned**")
            st.markdown(
                '<div style="display:flex;gap:0.4rem;flex-wrap:wrap">'
                + "".join(_chip(item, "queued") for item in competitors)
                + "</div>",
                unsafe_allow_html=True,
            )
        if differentiators:
            st.markdown("**Differentiators**")
            for item in differentiators:
                st.markdown(f"- {html.escape(str(item))}")

    p1, p2, p3 = st.columns(3)
    with p1:
        render_section_header("Risk Flags", icon="flag")
        risks = _as_list(pf.get("risk_flags"))
        if risks:
            for item in risks:
                st.markdown(f"- {html.escape(str(item))}")
        else:
            st.caption("No product-fit risks generated yet.")
    with p2:
        render_section_header("Recommended Positioning", icon="campaign")
        positioning = _as_list(pf.get("recommended_positioning"))
        if positioning:
            for item in positioning:
                st.markdown(f"- {html.escape(str(item))}")
        else:
            st.caption("No positioning guidance generated yet.")
    with p3:
        render_section_header("Next Actions", icon="task_alt")
        product_actions = _as_list(pf.get("recommended_next_actions"))
        if product_actions:
            for item in product_actions:
                st.markdown(f"- {html.escape(str(item))}")
        else:
            st.caption("No next actions generated yet.")

    pf["notes"] = st.text_area(
        "Editable Product Fit Notes",
        value=pf.get("notes", ""),
        height=120,
        placeholder="Add manual context, caveats, or product notes for the account team.",
    )

# ── Footer ──────────────────────────────────────────────────────────────
st.divider()
left, right = st.columns([0.5, 0.5])
with left:
    if st.button("Reset All Fields", type="secondary"):
        st.session_state[SESSION_KEY] = _empty_state()
        st.rerun()
with right:
    if state["raw_text"]:
        st.markdown(
            f'<div style="padding:0.5rem 0;font-size:0.8rem;color:var(--text-muted);font-family:var(--font-mono)">'
            f'Loaded: {state["file_name"]} · {len(state["raw_text"]):,} chars</div>',
            unsafe_allow_html=True,
        )
