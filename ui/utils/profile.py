"""Active domain profile for the UI (industries, sections, offerings, categories)."""
from __future__ import annotations

import streamlit as st

_FALLBACK = {
    "name": "default",
    "display_name": "Generic (any industry)",
    "industries": ["Other"],
    "offerings": [],
    "sections": [
        {"key": "executive_summary", "title": "Executive Summary", "words": [180, 260], "headings": []},
        {"key": "solution_overview", "title": "Solution Overview", "words": [220, 320], "headings": []},
        {"key": "implementation_plan", "title": "Implementation Plan", "words": [260, 380], "headings": []},
        {"key": "pricing_notes", "title": "Commercial Proposal", "words": [200, 300], "headings": []},
    ],
    "default_sections": ["executive_summary", "solution_overview", "implementation_plan", "pricing_notes"],
    "buyer_intelligence": {"readiness_stages": [], "intent_types": [], "gap_types": [], "stakeholder_categories": []},
    "product_fit": {"fit_stages": [], "gap_types": [], "capability_areas": []},
    "market_research": {"default_offerings": []},
    "llm": {},
}


@st.cache_data(ttl=120, show_spinner=False)
def _profiles() -> dict:
    from utils.api_client import list_profiles

    return list_profiles()


@st.cache_data(ttl=120, show_spinner=False)
def _profile(name: str) -> dict:
    from utils.api_client import get_profile

    return get_profile(name)


def active_profile_name() -> str:
    if st.session_state.get("profile_name"):
        return st.session_state["profile_name"]
    try:
        return _profiles().get("default", "default")
    except Exception:  # noqa: BLE001
        return "default"


def get_active_profile() -> dict:
    try:
        return _profile(active_profile_name())
    except Exception:  # noqa: BLE001
        return _FALLBACK


def render_profile_picker() -> None:
    """Sidebar selector; the choice applies to every page in this session."""
    try:
        data = _profiles()
    except Exception:  # noqa: BLE001
        return
    profiles = data.get("profiles") or []
    if not profiles:
        return
    names = [p["name"] for p in profiles]
    labels = {p["name"]: p.get("display_name") or p["name"] for p in profiles}
    current = active_profile_name()
    index = names.index(current) if current in names else 0
    chosen = st.selectbox(
        "Domain profile",
        names,
        index=index,
        format_func=lambda n: labels.get(n, n),
        key="profile_picker",
        help="Organization, offerings, sections, and categories used by the agents.",
    )
    st.session_state["profile_name"] = chosen


def section_options(profile: dict) -> dict[str, str]:
    """title → key for the profile's sections."""
    return {s["title"]: s["key"] for s in profile.get("sections", [])}


def section_title(profile: dict, key: str) -> str:
    for s in profile.get("sections", []):
        if s["key"] == key:
            return s["title"]
    return key.replace("_", " ").title()


def stage_for_score(stages: list[dict], score: int) -> str:
    ordered = sorted(stages or [], key=lambda s: s.get("max_score", 0))
    for stage in ordered:
        if score <= stage.get("max_score", 0):
            return stage["name"]
    return ordered[-1]["name"] if ordered else ""
