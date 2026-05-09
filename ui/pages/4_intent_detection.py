"""Intent Detection page.

Upload a transcript or email thread, run the intent detection workflow, then
review/edit three sub-views:

1. Client Overview — opportunity / client identifiers + problem framing
2. Buyer Readiness — readiness rating, gaps, stakeholder coverage
3. Product Fit — TBD (placeholder until the agent is designed)

For now the backend is a thin stub that runs cheap regex extraction. Real
sub-agents will replace it later — the UI shape stays the same.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from utils.api_client import run_intent_detection
from utils.theme import apply_theme, render_header, render_sidebar

st.set_page_config(page_title="Intent Detection", page_icon="🎯", layout="wide")
apply_theme()
render_sidebar()
render_header(title="Intent Detection")


SESSION_KEY = "intent_detection_state"


def _empty_state() -> dict:
    return {
        "raw_text": "",
        "file_name": "",
        "client_overview": {
            "opportunity_name": "",
            "client_name": "",
            "existing_relationship": "Unknown",
            "date_opened": None,
            "problem_statement": "",
            "success_definition": "",
            "stakeholder_impact": "",
            "urgency_statement": "",
        },
        "buyer_readiness": {
            "readiness_rating": 0,
            "buying_gaps": "",
            "stakeholder_coverage": "",
        },
        "product_fit": {
            "notes": "",
        },
    }


if SESSION_KEY not in st.session_state:
    st.session_state[SESSION_KEY] = _empty_state()

state: dict = st.session_state[SESSION_KEY]


# ── Hero ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="rfp-hero">
        <div class="rfp-kicker">Discovery analysis</div>
        <h1 class="rfp-title">Detect intent from sales conversations</h1>
        <p class="rfp-copy">
            Drop in a meeting transcript or email thread. The intent detection workflow
            runs three sub-agents — Client Overview, Buyer Readiness, Product Fit —
            and prefills each view. Anything the agent isn't sure about, you fill in.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Upload + run ────────────────────────────────────────────────────────
st.markdown("### 1. Upload conversation")
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
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read file: {exc}")
        raw_text = ""
    state["raw_text"] = raw_text
    state["file_name"] = uploaded.name
    with st.expander("Preview uploaded text", expanded=False):
        st.code(raw_text[:3000] + ("…" if len(raw_text) > 3000 else ""), language="text")


if run_clicked and state["raw_text"]:
    with st.spinner("Running intent detection sub-agents…"):
        try:
            result = run_intent_detection(
                transcript_text=state["raw_text"],
                file_name=state["file_name"],
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Intent detection failed: {exc}")
            result = None

    if result:
        co = result.get("client_overview") or {}
        br = result.get("buyer_readiness") or {}
        pf = result.get("product_fit") or {}
        # Merge — keep existing edits if backend didn't fill a field
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


# ── Three sub-flows ─────────────────────────────────────────────────────
st.markdown("### 2. Review and edit")
tab_client, tab_readiness, tab_fit = st.tabs(
    ["📋 Client Overview", "📈 Buyer Readiness", "🧩 Product Fit"]
)

co = state["client_overview"]
br = state["buyer_readiness"]
pf = state["product_fit"]


# ── Tab 1: Client Overview ──────────────────────────────────────────────
with tab_client:
    st.caption("Auto-filled from the transcript where possible. Edit any field.")

    st.markdown("#### Opportunity")
    c1, c2 = st.columns(2)
    with c1:
        co["opportunity_name"] = st.text_input(
            "Opportunity name",
            value=co.get("opportunity_name", ""),
            placeholder="e.g., Vodafone AIOps Modernization",
        )
        co["client_name"] = st.text_input(
            "Client name",
            value=co.get("client_name", ""),
            placeholder="e.g., Vodafone India",
        )
    with c2:
        relationship_options = ["Unknown", "New logo", "Existing customer", "Lapsed customer"]
        current_rel = co.get("existing_relationship") or "Unknown"
        if current_rel not in relationship_options:
            current_rel = "Unknown"
        co["existing_relationship"] = st.selectbox(
            "Existing relationship",
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
            "Date opened",
            value=existing_date if existing_date else None,
        )

    st.markdown("---")
    st.markdown("#### Problem framing")
    co["problem_statement"] = st.text_area(
        "Problem statement",
        value=co.get("problem_statement", ""),
        height=100,
        placeholder="What is the client trying to solve?",
    )
    co["success_definition"] = st.text_area(
        "Success definition",
        value=co.get("success_definition", ""),
        height=80,
        placeholder="What does winning look like for the client?",
    )
    c3, c4 = st.columns(2)
    with c3:
        co["stakeholder_impact"] = st.text_area(
            "Stakeholder impact",
            value=co.get("stakeholder_impact", ""),
            height=100,
            placeholder="Who is affected? Roles, teams, business lines.",
        )
    with c4:
        co["urgency_statement"] = st.text_area(
            "Urgency statement",
            value=co.get("urgency_statement", ""),
            height=100,
            placeholder="Why now? Deadlines, contractual triggers, budget cycles.",
        )


# ── Tab 2: Buyer Readiness ──────────────────────────────────────────────
with tab_readiness:
    st.caption("Buyer readiness rating, gaps blocking purchase, and stakeholder coverage.")

    rating_value = int(br.get("readiness_rating") or 0)
    rating_value = max(0, min(10, rating_value))
    br["readiness_rating"] = st.slider(
        "Readiness rating (0 = cold, 10 = ready to sign)",
        min_value=0, max_value=10, value=rating_value,
    )
    br["buying_gaps"] = st.text_area(
        "Buying gaps",
        value=br.get("buying_gaps", ""),
        height=140,
        placeholder="What's missing for the buyer? Budget approval, technical validation, stakeholder buy-in, etc.",
    )
    br["stakeholder_coverage"] = st.text_area(
        "Stakeholder coverage",
        value=br.get("stakeholder_coverage", ""),
        height=140,
        placeholder="Which roles have we engaged? Which key decision-makers are still uncovered?",
    )


# ── Tab 3: Product Fit ──────────────────────────────────────────────────
with tab_fit:
    st.caption("Product fit signals — agent design TBD. Free-form notes for now.")
    pf["notes"] = st.text_area(
        "Notes",
        value=pf.get("notes", ""),
        height=240,
        placeholder=(
            "Capture which capabilities map to the client's needs, where there are gaps, "
            "and which competing products surfaced in the conversation."
        ),
    )


# ── Footer actions ──────────────────────────────────────────────────────
st.markdown("---")
left, right = st.columns([0.5, 0.5])
with left:
    if st.button("Reset", type="secondary"):
        st.session_state[SESSION_KEY] = _empty_state()
        st.rerun()
with right:
    if state["raw_text"]:
        st.caption(
            f"📄 Loaded **{state['file_name']}** · {len(state['raw_text'])} chars"
        )
