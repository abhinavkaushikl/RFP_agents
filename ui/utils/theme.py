"""agentQA / RFP Pro theme — refined dark + light with a runtime toggle.

Design tokens follow an 8-pt vertical rhythm. Surfaces are layered
(base → surface → elevated → popover) and elevation reads through
a dual shadow + 1px inner highlight rather than heavy borders.

Each page calls `apply_theme()` after `st.set_page_config(...)`,
then `render_header(title=...)` to draw the logo + theme toggle row.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_LOGO_PNG = _STATIC_DIR / "agentqa_logo.png"
_LOGO_SVG = _STATIC_DIR / "agentqa_logo.svg"


# ── Design tokens ───────────────────────────────────────────────────────
_DARK_VARS = """
--bg-base: #060c1d;
--bg-surface: #0f1a35;
--bg-elevated: #16234a;
--bg-popover: #142048;
--bg-hover: #1c2c5b;
--bg-pressed: #233670;
--border: rgba(255, 255, 255, 0.06);
--border-strong: rgba(255, 255, 255, 0.10);
--inner-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.05);
--text: #eef3fc;
--text-muted: #94a3bd;
--text-dim: #5d6c8c;
--accent: #2E90FF;
--accent-hover: #4ea2ff;
--accent-pressed: #1f7ae8;
--accent-soft: rgba(46, 144, 255, 0.14);
--accent-glow: 0 0 0 6px rgba(46, 144, 255, 0.08);
--code-bg: #08101f;
--code-text: #cfe1ff;
--shadow-1: 0 1px 2px rgba(0, 0, 0, 0.35), 0 6px 18px rgba(0, 0, 0, 0.30);
--shadow-2: 0 2px 6px rgba(0, 0, 0, 0.40), 0 18px 48px rgba(0, 0, 0, 0.45);
--hero-grad: radial-gradient(120% 140% at 0% 0%, rgba(46, 144, 255, 0.18) 0%, transparent 55%), linear-gradient(160deg, #11214a 0%, #0a1430 65%, #060c1d 100%);
--page-grad: radial-gradient(80% 60% at 100% 0%, rgba(46, 144, 255, 0.06) 0%, transparent 60%), radial-gradient(60% 50% at 0% 100%, rgba(118, 80, 220, 0.05) 0%, transparent 60%), #060c1d;
"""

_LIGHT_VARS = """
--bg-base: #f3f6fb;
--bg-surface: #ffffff;
--bg-elevated: #ffffff;
--bg-popover: #ffffff;
--bg-hover: #eef3fb;
--bg-pressed: #e2ebfa;
--border: rgba(15, 26, 51, 0.08);
--border-strong: rgba(15, 26, 51, 0.14);
--inner-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.6);
--text: #0a1429;
--text-muted: #5a6779;
--text-dim: #8a98ad;
--accent: #2563eb;
--accent-hover: #1d4ed8;
--accent-pressed: #1e40af;
--accent-soft: rgba(37, 99, 235, 0.10);
--accent-glow: 0 0 0 6px rgba(37, 99, 235, 0.08);
--code-bg: #f1f5fb;
--code-text: #0a1429;
--shadow-1: 0 1px 2px rgba(15, 26, 51, 0.04), 0 6px 18px rgba(15, 26, 51, 0.06);
--shadow-2: 0 2px 8px rgba(15, 26, 51, 0.06), 0 22px 60px rgba(15, 26, 51, 0.08);
--hero-grad: radial-gradient(120% 140% at 0% 0%, rgba(37, 99, 235, 0.12) 0%, transparent 55%), linear-gradient(160deg, #eaf2ff 0%, #f5f8fd 65%, #ffffff 100%);
--page-grad: radial-gradient(80% 60% at 100% 0%, rgba(37, 99, 235, 0.05) 0%, transparent 60%), radial-gradient(60% 50% at 0% 100%, rgba(118, 80, 220, 0.04) 0%, transparent 60%), #f3f6fb;
"""


_BASE_CSS = """
<style>
:root {
    %VARS%
    --r-pill: 999px;
    --r-sm: 10px;
    --r-md: 14px;
    --r-lg: 18px;
    --r-xl: 22px;
    --t-fast: 120ms cubic-bezier(0.4, 0.0, 0.2, 1);
    --t-base: 200ms cubic-bezier(0.4, 0.0, 0.2, 1);
}

/* Global canvas */
html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--page-grad) !important;
    color: var(--text) !important;
    font-feature-settings: "ss01", "cv01";
}
[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
    height: 0 !important;
}
[data-testid="stToolbar"] { right: 1rem; }
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 4rem;
    max-width: 1240px;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    color: var(--text) !important;
    letter-spacing: -0.02em;
    font-weight: 700;
}
h1 { font-size: 2.0rem; line-height: 1.15; }
h2 { font-size: 1.5rem; line-height: 1.2; }
h3 { font-size: 1.18rem; line-height: 1.25; }
p, span, label, li, div { color: var(--text); }
small, [data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
    font-size: 0.82rem;
    letter-spacing: 0.01em;
}
a { color: var(--accent) !important; text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }

/* ── Sidebar ─────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border);
    box-shadow: var(--shadow-1);
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.6rem;
    padding-bottom: 1rem;
}
[data-testid="stSidebar"] * { color: var(--text); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--text-muted) !important; }
[data-testid="stSidebar"] hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 0.9rem 0 !important;
}
[data-testid="stSidebarNav"] { padding-top: 0.4rem; }
[data-testid="stSidebarNav"] a {
    border-radius: var(--r-md);
    padding: 0.55rem 0.75rem !important;
    margin: 2px 0;
    transition: background var(--t-fast), color var(--t-fast);
}
[data-testid="stSidebarNav"] a:hover {
    background: var(--bg-hover) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: var(--accent-soft) !important;
    color: var(--text) !important;
    box-shadow: inset 0 0 0 1px var(--border);
}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {
    content: "";
    display: inline-block;
    width: 4px; height: 16px;
    background: var(--accent);
    border-radius: 4px;
    margin-right: 0.55rem;
    vertical-align: -3px;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea,
.stNumberInput input, .stDateInput input {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    color: var(--text) !important;
    transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea,
[data-baseweb="select"] input,
[data-baseweb="select"] [class*="ValueContainer"],
[data-baseweb="select"] [data-baseweb="tag"] {
    background: transparent !important;
    color: var(--text) !important;
}
[data-baseweb="input"] > div:hover,
[data-baseweb="textarea"] > div:hover,
[data-baseweb="select"] > div:hover { border-color: var(--border-strong) !important; }
[data-baseweb="input"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within,
[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: var(--accent-glow) !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label,
.stNumberInput label, .stDateInput label, .stRadio label, .stCheckbox label,
.stSlider label, .stFileUploader label {
    color: var(--text) !important;
    font-weight: 500;
    font-size: 0.92rem;
}
input::placeholder, textarea::placeholder { color: var(--text-dim) !important; }

/* ── Dropdown / popover (BaseWeb) ────────────────────────────────────── */
/* The portal that BaseWeb opens for select / multiselect / autocomplete */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[role="listbox"] {
    background: var(--bg-popover) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-2) !important;
    overflow: hidden;
    backdrop-filter: blur(8px);
}
div[data-baseweb="popover"] *,
div[data-baseweb="menu"] *,
ul[role="listbox"] * {
    background: transparent !important;
    color: var(--text) !important;
}
[role="option"] {
    padding: 0.55rem 0.85rem !important;
    border-radius: 0 !important;
    transition: background var(--t-fast);
}
[role="option"]:hover {
    background: var(--bg-hover) !important;
    color: var(--text) !important;
}
[role="option"][aria-selected="true"] {
    background: var(--accent-soft) !important;
    color: var(--text) !important;
    font-weight: 500;
}
/* Multiselect tag chips */
[data-baseweb="tag"] {
    background: var(--accent-soft) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-pill) !important;
    color: var(--text) !important;
    padding: 0.15rem 0.55rem !important;
}
[data-baseweb="tag"] svg { fill: var(--text-muted) !important; }

/* ── Buttons ─────────────────────────────────────────────────────────── */
div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {
    background: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    color: #ffffff !important;
    border-radius: var(--r-pill) !important;
    font-weight: 600;
    font-size: 0.92rem;
    padding: 0.55rem 1.15rem;
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.15) inset, 0 6px 18px rgba(46, 144, 255, 0.22);
    transition: background var(--t-fast), transform 80ms ease, box-shadow var(--t-fast);
    letter-spacing: 0;
}
div.stButton > button:hover,
div.stFormSubmitButton > button:hover,
div.stDownloadButton > button:hover {
    background: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
    color: #ffffff !important;
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.2) inset, 0 8px 22px rgba(46, 144, 255, 0.30);
}
div.stButton > button:active {
    background: var(--accent-pressed) !important;
    transform: translateY(1px);
}
div.stButton > button:focus-visible,
div.stFormSubmitButton > button:focus-visible {
    outline: none !important;
    box-shadow: var(--accent-glow), 0 6px 18px rgba(46, 144, 255, 0.22) !important;
}
div.stButton > button[kind="secondary"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text) !important;
    box-shadow: var(--shadow-1);
}
div.stButton > button[kind="secondary"]:hover {
    background: var(--bg-hover) !important;
    border-color: var(--accent) !important;
    color: var(--text) !important;
}
div.stButton > button:disabled {
    opacity: 0.5;
    box-shadow: none;
}

/* ── Cards / containers ──────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-1), var(--inner-highlight) !important;
    overflow: hidden;
}
[data-testid="stExpander"] details { padding: 0.2rem 0.4rem; }
[data-testid="stExpander"] details summary {
    color: var(--text) !important;
    font-weight: 500;
    padding: 0.7rem 0.8rem;
    border-radius: var(--r-md);
    transition: background var(--t-fast);
}
[data-testid="stExpander"] details summary:hover { background: var(--bg-hover); }

/* Metric tiles */
[data-testid="stMetric"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.1rem 1.2rem;
    box-shadow: var(--shadow-1), var(--inner-highlight);
}
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 0.82rem; letter-spacing: 0.04em; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-weight: 700; font-size: 1.7rem; }
[data-testid="stMetricDelta"] { color: var(--accent) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border);
    gap: 0.1rem;
    padding: 0 0.2rem;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--text-muted) !important;
    border-radius: var(--r-md) var(--r-md) 0 0;
    padding: 0.6rem 1rem;
    font-weight: 500;
    transition: color var(--t-fast), background var(--t-fast);
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; background: var(--bg-hover); }
.stTabs [aria-selected="true"] {
    color: var(--text) !important;
    background: var(--bg-surface) !important;
    border-bottom: 2px solid var(--accent) !important;
    box-shadow: 0 1px 0 var(--bg-surface);
}

/* Tables / dataframes */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-1);
    overflow: hidden;
}
[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] { background: var(--bg-surface) !important; }

/* Alerts — round corners and lift, but preserve Streamlit's semantic tinting */
[data-testid="stAlert"] {
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-1);
}
[data-testid="stAlert"] * { color: inherit !important; }

/* File uploader */
[data-testid="stFileUploader"] section {
    background: var(--bg-surface) !important;
    border: 1px dashed var(--border-strong) !important;
    border-radius: var(--r-lg) !important;
    transition: border-color var(--t-fast), background var(--t-fast);
}
[data-testid="stFileUploader"] section:hover {
    border-color: var(--accent) !important;
    background: var(--bg-hover) !important;
}
[data-testid="stFileUploader"] small { color: var(--text-muted) !important; }

/* Slider */
.stSlider [data-baseweb="slider"] [role="slider"] {
    background: var(--accent) !important;
    border: 2px solid var(--bg-surface) !important;
    box-shadow: var(--accent-glow) !important;
}
.stSlider [data-baseweb="slider"] div[role="progressbar"] { background: var(--accent) !important; }
.stSlider [data-baseweb="slider"] > div > div:first-child > div { background: var(--border-strong) !important; }

/* Radio / checkbox */
.stRadio [role="radiogroup"] label,
.stCheckbox label {
    color: var(--text) !important;
}
.stCheckbox [data-baseweb="checkbox"] [data-checked="true"] {
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* Code blocks */
code, pre, .stCodeBlock, [data-testid="stCodeBlock"] {
    background: var(--code-bg) !important;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: var(--code-text) !important;
}

/* Dividers */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.4rem 0 !important;
}

/* ── Custom helpers ──────────────────────────────────────────────────── */
.rfp-shell {
    max-width: 1180px;
    margin: 0 auto;
    padding: 0.4rem 0 2rem;
}
.rfp-hero {
    background: var(--hero-grad);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: 2rem 2.2rem;
    box-shadow: var(--shadow-2), var(--inner-highlight);
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
}
.rfp-hero::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: radial-gradient(60% 80% at 100% 100%, rgba(46, 144, 255, 0.10) 0%, transparent 60%);
}
.rfp-kicker {
    display: inline-block;
    color: var(--accent);
    font-weight: 600;
    font-size: 0.7rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    padding: 0.28rem 0.7rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    border: 1px solid var(--border);
    margin-bottom: 1rem;
}
.rfp-title {
    font-size: 2.1rem;
    line-height: 1.12;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin: 0;
    color: var(--text);
}
.rfp-copy {
    color: var(--text-muted);
    max-width: 760px;
    font-size: 0.99rem;
    margin-top: 0.85rem;
    line-height: 1.6;
}
.rfp-panel,
.result-box {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.4rem 1.5rem;
    box-shadow: var(--shadow-1), var(--inner-highlight);
    color: var(--text);
}

/* Page header (logo row) */
.aq-header {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 1rem;
    padding: 0.2rem 0 0.6rem;
    margin-bottom: 0.4rem;
}
.aq-logo {
    color: var(--accent);
    display: inline-flex;
    align-items: center;
    height: 44px;
}
.aq-logo svg { height: 44px; width: auto; }
.aq-logo img { height: 44px; width: auto; display: block; }
.aq-page-title {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 0.35rem 0.8rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--border);
    background: var(--bg-surface);
}

/* Sidebar logo */
.aq-sidebar-logo {
    padding: 0.4rem 0 0.9rem;
    color: var(--accent);
}
.aq-sidebar-logo svg { height: 30px; width: auto; }
.aq-sidebar-logo img { height: 30px; width: auto; display: block; }

/* Status pill */
.rfp-status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 0.55rem;
    vertical-align: middle;
}
.rfp-status-ok { background: #22c55e; box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.18); }
.rfp-status-bad { background: #ef4444; box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.18); }

/* Scrollbars (WebKit) */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* Spacing rhythm fixes */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stMarkdownContainer"]) {
    margin-bottom: 0;
}
[data-testid="stHorizontalBlock"] { gap: 1rem; }
.stMarkdown p { margin-bottom: 0.6rem; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { margin-top: 1.2rem; margin-bottom: 0.6rem; }

/* Form spacing */
[data-testid="stForm"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.4rem 1.5rem;
    box-shadow: var(--shadow-1), var(--inner-highlight);
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] { margin-top: 0.4rem; }

/* Fade-in for top-level content blocks */
.block-container > div { animation: aqFadeIn 320ms cubic-bezier(0.4, 0.0, 0.2, 1); }
@keyframes aqFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
"""


def _current_theme() -> str:
    return st.session_state.get("aq_theme", "dark")


def apply_theme() -> None:
    """Inject theme CSS based on session state. Call once per page."""
    vars_block = _DARK_VARS if _current_theme() == "dark" else _LIGHT_VARS
    st.markdown(_BASE_CSS.replace("%VARS%", vars_block), unsafe_allow_html=True)


def _logo_html(height_px: int = 44) -> str:
    """Return logo as HTML — prefer PNG at ui/static/agentqa_logo.png, else inline SVG."""
    if _LOGO_PNG.exists():
        b64 = base64.b64encode(_LOGO_PNG.read_bytes()).decode("ascii")
        return f'<img src="data:image/png;base64,{b64}" alt="agentQA" style="height:{height_px}px"/>'
    if _LOGO_SVG.exists():
        return _LOGO_SVG.read_text(encoding="utf-8")
    return '<span style="font-weight:700;color:var(--accent);font-size:1.1rem">agentQA</span>'


def render_header(title: str | None = None) -> None:
    """Page header row: logo (with optional page-title pill) on the left, theme toggle on the right."""
    left, _spacer, right = st.columns([0.62, 0.23, 0.15])
    with left:
        title_pill = (
            f'<div class="aq-page-title">{title}</div>' if title else ""
        )
        st.markdown(
            f'<div class="aq-header">'
            f'<div class="aq-logo">{_logo_html(44)}</div>'
            f'{title_pill}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with right:
        current = _current_theme()
        label = "🌙 Dark" if current == "dark" else "☀️ Light"
        if st.button(label, key="aq_theme_toggle", type="secondary", use_container_width=True):
            st.session_state["aq_theme"] = "light" if current == "dark" else "dark"
            st.rerun()


def render_sidebar_logo() -> None:
    """Compact logo for the sidebar header."""
    st.markdown(
        f'<div class="aq-sidebar-logo">{_logo_html(30)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Unified sidebar content: logo, user, log out, divider, backend status.

    Call this from each page so the sidebar is consistent across navigation.
    """
    with st.sidebar:
        render_sidebar_logo()
        st.caption(st.session_state.get("user_email", "demo@rfp.ai"))
        if st.button("Log out", use_container_width=True, type="secondary", key="aq_sidebar_logout"):
            st.session_state["authenticated"] = False
            st.rerun()
        st.divider()
        api_ok = True
        msg = "Backend online"
        try:
            from utils.api_client import health_check  # noqa: PLC0415

            status = health_check()
            msg = f"API: {status.get('status', 'ok')}"
        except Exception:
            api_ok = False
            msg = "API unreachable — start backend"
        render_status_footer(api_ok, msg)


def render_status_footer(api_ok: bool, message: str = "") -> None:
    """Sidebar status footer with a colored dot."""
    dot = "rfp-status-ok" if api_ok else "rfp-status-bad"
    label = message or ("Backend online" if api_ok else "Backend offline")
    st.markdown(
        f'<div style="padding:0.7rem 0.2rem;color:var(--text-muted);font-size:0.85rem">'
        f'<span class="rfp-status-dot {dot}"></span>{label}</div>',
        unsafe_allow_html=True,
    )
