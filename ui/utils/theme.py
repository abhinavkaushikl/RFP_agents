"""RFP.ai Enterprise Theme — Modern Enterprise Intelligence design system.

Design tokens follow the Stitch "Modern Enterprise Intelligence" design system
with Intelligence Blue (#0058be), Compliance Teal (#0d9488), and Deep Slate
primary palette. Uses Inter for UI, JetBrains Mono for technical data.

Each page calls `apply_theme()` after `st.set_page_config(...)`,
then `render_header(title=...)` to draw the top bar.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_LOGO_PNG = _STATIC_DIR / "agentqa_logo.png"
_LOGO_SVG = _STATIC_DIR / "agentqa_logo.svg"

# ── Design tokens (Stitch: Modern Enterprise Intelligence) ────────────

_DARK_VARS = """
--bg-base: #0a1628;
--bg-surface: #111d33;
--bg-elevated: #162544;
--bg-popover: #152240;
--bg-hover: #1a2d52;
--bg-pressed: #1f3460;
--border: rgba(255, 255, 255, 0.07);
--border-strong: rgba(255, 255, 255, 0.12);
--border-accent: rgba(0, 88, 190, 0.35);
--inner-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.04);
--text: #e8edf5;
--text-secondary: #a0aec0;
--text-muted: #64748b;
--text-dim: #475569;
--accent: #2170e4;
--accent-hover: #3b82f6;
--accent-pressed: #0058be;
--accent-soft: rgba(33, 112, 228, 0.12);
--accent-glow: 0 0 0 3px rgba(33, 112, 228, 0.15);
--teal: #0d9488;
--teal-soft: rgba(13, 148, 136, 0.12);
--amber: #f59e0b;
--amber-soft: rgba(245, 158, 11, 0.12);
--red: #ef4444;
--red-soft: rgba(239, 68, 68, 0.10);
--code-bg: #0d1829;
--code-text: #c8d6e5;
--shadow-sm: 0 1px 2px rgba(0,0,0,0.25);
--shadow-md: 0 2px 8px rgba(0,0,0,0.30), 0 8px 24px rgba(0,0,0,0.20);
--shadow-lg: 0 4px 16px rgba(0,0,0,0.35), 0 20px 50px rgba(0,0,0,0.30);
--glass: rgba(17, 29, 51, 0.75);
--glass-border: rgba(255, 255, 255, 0.08);
--hero-grad: linear-gradient(135deg, #111d33 0%, #0e1a2e 40%, #0a1628 100%);
--hero-glow: radial-gradient(ellipse 60% 50% at 15% 50%, rgba(33, 112, 228, 0.08) 0%, transparent 70%);
--page-grad: #0a1628;
--sidebar-bg: #0d1829;
--sidebar-border: rgba(255, 255, 255, 0.06);
"""

_LIGHT_VARS = """
--bg-base: #f8f9ff;
--bg-surface: #ffffff;
--bg-elevated: #ffffff;
--bg-popover: #ffffff;
--bg-hover: #eff4ff;
--bg-pressed: #e5eeff;
--border: #e2e8f0;
--border-strong: #cbd5e1;
--border-accent: rgba(0, 88, 190, 0.25);
--inner-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.8);
--text: #0b1c30;
--text-secondary: #45464d;
--text-muted: #64748b;
--text-dim: #94a3b8;
--accent: #0058be;
--accent-hover: #004395;
--accent-pressed: #003580;
--accent-soft: rgba(0, 88, 190, 0.08);
--accent-glow: 0 0 0 3px rgba(0, 88, 190, 0.12);
--teal: #0d9488;
--teal-soft: rgba(13, 148, 136, 0.08);
--amber: #d97706;
--amber-soft: rgba(217, 119, 6, 0.08);
--red: #dc2626;
--red-soft: rgba(220, 38, 38, 0.06);
--code-bg: #f1f5f9;
--code-text: #0b1c30;
--shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
--shadow-md: 0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 20px rgba(15, 23, 42, 0.05);
--shadow-lg: 0 4px 16px rgba(15, 23, 42, 0.08), 0 20px 50px rgba(15, 23, 42, 0.06);
--glass: rgba(255, 255, 255, 0.80);
--glass-border: rgba(15, 23, 42, 0.08);
--hero-grad: linear-gradient(135deg, #ffffff 0%, #f8f9ff 40%, #eff4ff 100%);
--hero-glow: radial-gradient(ellipse 60% 50% at 15% 50%, rgba(0, 88, 190, 0.04) 0%, transparent 70%);
--page-grad: #f8f9ff;
--sidebar-bg: #ffffff;
--sidebar-border: #e2e8f0;
"""

_BASE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

:root {
    %VARS%
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    --r-xs: 4px;
    --r-sm: 6px;
    --r-md: 8px;
    --r-lg: 12px;
    --r-xl: 16px;
    --r-pill: 999px;
    --t-fast: 120ms cubic-bezier(0.4, 0, 0.2, 1);
    --t-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
    --t-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1);
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 40px;
}

/* ── Global canvas ──────────────────────────────────────────────────── */
html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--page-grad) !important;
    color: var(--text) !important;
    font-family: var(--font-sans) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
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
    max-width: 1320px;
}

/* ── Typography ─────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    color: var(--text) !important;
    font-family: var(--font-sans) !important;
    font-weight: 600;
}
h1 { font-size: 1.85rem; line-height: 1.2; letter-spacing: -0.02em; font-weight: 700; }
h2 { font-size: 1.35rem; line-height: 1.25; letter-spacing: -0.01em; }
h3 { font-size: 1.1rem; line-height: 1.3; }
p, span, label, li, div { color: var(--text); font-family: var(--font-sans); }
small, [data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
    font-size: 0.8rem;
    letter-spacing: 0.01em;
}
a { color: var(--accent) !important; text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }
code, .stCodeBlock code {
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: 1px solid var(--sidebar-border) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.5rem;
    padding-bottom: 1rem;
}
[data-testid="stSidebar"] * { color: var(--text); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--text-muted) !important; }
[data-testid="stSidebar"] hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 0.75rem 0 !important;
}
[data-testid="stSidebarNav"] { padding-top: 0.3rem; }
[data-testid="stSidebarNav"] a {
    border-radius: var(--r-md);
    padding: 0.5rem 0.7rem !important;
    margin: 1px 0;
    font-size: 0.88rem;
    font-weight: 500;
    transition: background var(--t-fast), color var(--t-fast);
}
[data-testid="stSidebarNav"] a:hover {
    background: var(--bg-hover) !important;
    text-decoration: none !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
    border-left: 3px solid var(--accent);
    font-weight: 600;
}

/* ── Inputs ─────────────────────────────────────────────────────────── */
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea,
.stNumberInput input, .stDateInput input {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    color: var(--text) !important;
    font-family: var(--font-sans) !important;
    font-size: 14px !important;
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
    color: var(--text-secondary) !important;
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.01em;
    text-transform: uppercase;
    font-family: var(--font-sans) !important;
}
input::placeholder, textarea::placeholder { color: var(--text-dim) !important; }

/* ── Dropdowns ──────────────────────────────────────────────────────── */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[role="listbox"] {
    background: var(--bg-popover) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-lg) !important;
    overflow: hidden;
    backdrop-filter: blur(12px);
}
div[data-baseweb="popover"] *,
div[data-baseweb="menu"] *,
ul[role="listbox"] * {
    background: transparent !important;
    color: var(--text) !important;
}
[role="option"] {
    padding: 0.5rem 0.75rem !important;
    border-radius: 0 !important;
    font-size: 14px;
    transition: background var(--t-fast);
}
[role="option"]:hover { background: var(--bg-hover) !important; }
[role="option"][aria-selected="true"] {
    background: var(--accent-soft) !important;
    font-weight: 500;
}
[data-baseweb="tag"] {
    background: var(--accent-soft) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: var(--r-pill) !important;
    color: var(--accent) !important;
    padding: 0.15rem 0.5rem !important;
    font-size: 13px;
}
[data-baseweb="tag"] svg { fill: var(--text-muted) !important; }

/* ── Buttons ────────────────────────────────────────────────────────── */
div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {
    background: var(--accent) !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: var(--r-md) !important;
    font-weight: 600;
    font-size: 14px;
    font-family: var(--font-sans) !important;
    letter-spacing: 0.01em;
    padding: 0.55rem 1.2rem;
    box-shadow: var(--shadow-sm);
    transition: background var(--t-fast), transform 80ms ease, box-shadow var(--t-fast);
}
div.stButton > button:hover,
div.stFormSubmitButton > button:hover,
div.stDownloadButton > button:hover {
    background: var(--accent-hover) !important;
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
div.stButton > button:active {
    background: var(--accent-pressed) !important;
    transform: translateY(0);
}
div.stButton > button:focus-visible,
div.stFormSubmitButton > button:focus-visible {
    outline: none !important;
    box-shadow: var(--accent-glow) !important;
}
div.stButton > button[kind="secondary"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text) !important;
    box-shadow: none;
}
div.stButton > button[kind="secondary"]:hover {
    background: var(--bg-hover) !important;
    border-color: var(--accent) !important;
}
div.stButton > button:disabled {
    opacity: 0.45;
    box-shadow: none;
    transform: none;
}

/* ── Cards / Containers ─────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow: hidden;
}
[data-testid="stExpander"] details { padding: 0.15rem 0.3rem; }
[data-testid="stExpander"] details summary {
    color: var(--text) !important;
    font-weight: 500;
    padding: 0.6rem 0.75rem;
    border-radius: var(--r-md);
    font-size: 0.9rem;
    transition: background var(--t-fast);
}
[data-testid="stExpander"] details summary:hover { background: var(--bg-hover); }

/* Metric tiles */
[data-testid="stMetric"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1rem 1.1rem;
    box-shadow: var(--shadow-sm);
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-family: var(--font-sans) !important;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-weight: 700;
    font-size: 1.6rem;
    font-family: var(--font-sans) !important;
}
[data-testid="stMetricDelta"] { color: var(--teal) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border);
    gap: 0;
    padding: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--text-muted) !important;
    padding: 0.55rem 1rem;
    font-weight: 500;
    font-size: 0.88rem;
    transition: color var(--t-fast), background var(--t-fast);
    border-radius: 0;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
    background: var(--bg-hover);
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    background: transparent !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600;
}

/* Tables */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
}
[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
    background: var(--bg-surface) !important;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: var(--r-md) !important;
    border: 1px solid var(--border) !important;
    font-size: 0.9rem;
}
[data-testid="stAlert"] * { color: inherit !important; }

/* File uploader */
[data-testid="stFileUploader"] section {
    background: var(--bg-surface) !important;
    border: 2px dashed var(--border-strong) !important;
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
.stCheckbox label { color: var(--text) !important; }
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
    font-family: var(--font-mono) !important;
}

/* Dividers */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.2rem 0 !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background: var(--accent) !important;
    border-radius: var(--r-pill);
}
.stProgress > div > div {
    background: var(--bg-hover) !important;
    border-radius: var(--r-pill);
}

/* Containers with border */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
    border-color: var(--border) !important;
    border-radius: var(--r-lg) !important;
    background: var(--bg-surface) !important;
}

/* Form */
[data-testid="stForm"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.25rem 1.4rem;
    box-shadow: var(--shadow-sm);
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] { margin-top: 0.5rem; }

/* ── Custom Components ──────────────────────────────────────────────── */

/* Page shell */
.rfp-shell { max-width: 1280px; margin: 0 auto; }

/* Hero Section */
.rfp-hero {
    background: var(--hero-grad);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: 2rem 2.2rem;
    box-shadow: var(--shadow-md);
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.rfp-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: var(--hero-glow);
}
.rfp-kicker {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--accent);
    font-weight: 600;
    font-size: 0.7rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0.25rem 0.65rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    border: 1px solid var(--border-accent);
    margin-bottom: 0.85rem;
    font-family: var(--font-sans);
}
.rfp-title {
    font-size: 1.85rem;
    line-height: 1.15;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin: 0;
    color: var(--text);
    font-family: var(--font-sans);
}
.rfp-copy {
    color: var(--text-secondary);
    max-width: 720px;
    font-size: 0.95rem;
    margin-top: 0.65rem;
    line-height: 1.6;
}

/* Panel card */
.rfp-panel {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.25rem 1.4rem;
    box-shadow: var(--shadow-sm);
    color: var(--text);
}
.result-box {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.25rem 1.4rem;
    box-shadow: var(--shadow-sm);
    color: var(--text);
}

/* ── Dashboard Components ───────────────────────────────────────────── */

/* Stat card */
.stat-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.1rem 1.3rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--t-base), border-color var(--t-base);
}
.stat-card:hover {
    box-shadow: var(--shadow-md);
    border-color: var(--border-strong);
}
.stat-card-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-sans);
}
.stat-card-value {
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
    font-family: var(--font-sans);
}
.stat-card-sub {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    font-family: var(--font-mono);
    letter-spacing: 0.01em;
}

/* Agent card */
.agent-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--t-base), transform var(--t-base);
}
.agent-card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
.agent-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.6rem;
}
.agent-card-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--r-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}
.agent-card-icon.blue { background: var(--accent-soft); color: var(--accent); }
.agent-card-icon.teal { background: var(--teal-soft); color: var(--teal); }
.agent-card-icon.amber { background: var(--amber-soft); color: var(--amber); }
.agent-card-name {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text);
}
.agent-card-role {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
}
.agent-card-desc {
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
}

/* Status chip */
.status-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 0.2rem 0.55rem;
    border-radius: var(--r-pill);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-family: var(--font-mono);
}
.status-chip.active { background: var(--teal-soft); color: var(--teal); }
.status-chip.processing { background: var(--accent-soft); color: var(--accent); }
.status-chip.queued { background: var(--bg-hover); color: var(--text-muted); }
.status-chip.error { background: var(--red-soft); color: var(--red); }
.status-chip.warning { background: var(--amber-soft); color: var(--amber); }

/* Workflow pipeline visualization */
.pipeline-flow {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 1rem 0;
    overflow-x: auto;
    flex-wrap: wrap;
}
.pipeline-step {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0.35rem 0.7rem;
    border-radius: var(--r-md);
    font-size: 0.78rem;
    font-weight: 500;
    font-family: var(--font-mono);
    white-space: nowrap;
    transition: all var(--t-fast);
    border: 1px solid var(--border);
    background: var(--bg-surface);
    color: var(--text-secondary);
}
.pipeline-step.completed {
    background: var(--teal-soft);
    border-color: rgba(13, 148, 136, 0.25);
    color: var(--teal);
}
.pipeline-step.active {
    background: var(--accent-soft);
    border-color: var(--border-accent);
    color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
    animation: pulseStep 2s ease-in-out infinite;
}
.pipeline-step.failed {
    background: var(--red-soft);
    border-color: rgba(239, 68, 68, 0.25);
    color: var(--red);
}
.pipeline-step.done-step {
    background: var(--teal-soft);
    border-color: rgba(13, 148, 136, 0.3);
    color: var(--teal);
    font-weight: 600;
}
.pipeline-arrow {
    color: var(--text-dim);
    font-size: 0.7rem;
    flex-shrink: 0;
}
@keyframes pulseStep {
    0%, 100% { box-shadow: 0 0 0 2px var(--accent-soft); }
    50% { box-shadow: 0 0 0 4px var(--accent-soft); }
}

/* Score gauge */
.score-gauge {
    text-align: center;
    padding: 0.8rem;
}
.score-gauge-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    font-family: var(--font-sans);
}
.score-gauge-value.good { color: var(--teal); }
.score-gauge-value.warn { color: var(--amber); }
.score-gauge-value.bad { color: var(--red); }
.score-gauge-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-top: 0.35rem;
    font-family: var(--font-sans);
}
.score-gauge-bar {
    height: 4px;
    border-radius: var(--r-pill);
    background: var(--bg-hover);
    margin-top: 0.5rem;
    overflow: hidden;
}
.score-gauge-fill {
    height: 100%;
    border-radius: var(--r-pill);
    transition: width var(--t-slow);
}
.score-gauge-fill.good { background: var(--teal); }
.score-gauge-fill.warn { background: var(--amber); }
.score-gauge-fill.bad { background: var(--red); }

/* Section heading */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 1.5rem 0 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}
.section-header-icon {
    color: var(--accent);
    font-size: 20px;
}
.section-header-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
}
.section-header-badge {
    margin-left: auto;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 0.15rem 0.5rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent);
    font-family: var(--font-mono);
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 3rem 2rem;
    color: var(--text-muted);
}
.empty-state-icon {
    font-size: 48px;
    color: var(--text-dim);
    margin-bottom: 1rem;
    opacity: 0.6;
}
.empty-state-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 0.4rem;
}
.empty-state-desc {
    font-size: 0.88rem;
    color: var(--text-muted);
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.5;
}

/* ── Header ─────────────────────────────────────────────────────────── */
.aq-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.15rem 0 0.5rem;
    margin-bottom: 0.3rem;
}
.aq-header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.aq-logo {
    color: var(--accent);
    display: inline-flex;
    align-items: center;
    height: 38px;
}
.aq-logo svg { height: 38px; width: auto; }
.aq-logo img { height: 38px; width: auto; display: block; }
.aq-page-title {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0.25rem 0.65rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--border);
    background: var(--bg-surface);
    font-family: var(--font-sans);
}
.aq-sidebar-logo {
    padding: 0.3rem 0 0.7rem;
    color: var(--accent);
}
.aq-sidebar-logo svg { height: 28px; width: auto; }
.aq-sidebar-logo img { height: 28px; width: auto; display: block; }

/* Status dot */
.rfp-status-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 0.5rem;
    vertical-align: middle;
}
.rfp-status-ok { background: var(--teal); box-shadow: 0 0 0 3px var(--teal-soft); }
.rfp-status-bad { background: var(--red); box-shadow: 0 0 0 3px var(--red-soft); }

/* ── Agent Trace Timeline ───────────────────────────────────────────── */
.agent-timeline {
    position: relative;
    padding-left: 20px;
}
.agent-timeline::before {
    content: "";
    position: absolute;
    left: 8px;
    top: 4px;
    bottom: 4px;
    width: 2px;
    background: var(--border);
    border-radius: 1px;
}
.tt-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 0.5rem 0;
    position: relative;
}
.tt-row-decision { padding: 0.55rem 0; }
.tt-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 4px;
    position: relative;
    z-index: 1;
    border: 2px solid var(--bg-surface);
}
.tt-ok { background: var(--teal); }
.tt-bad { background: var(--red); }
.tt-warn { background: var(--amber); }
.tt-info { background: var(--accent); }
.tt-pending { background: var(--text-dim); animation: pulseDot 1.5s ease-in-out infinite; }
@keyframes pulseDot {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
}
.tt-body { flex: 1; min-width: 0; }
.tt-meta {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-family: var(--font-mono);
}
.tt-title {
    font-size: 0.85rem;
    color: var(--text);
    line-height: 1.4;
    margin-top: 2px;
}
.tt-monospace {
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--accent);
    font-size: 0.82rem;
}
.tt-sub {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 3px;
    line-height: 1.4;
}

/* Trace summary chips */
.trace-summary {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
}
.trace-summary-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0.2rem 0.55rem;
    border-radius: var(--r-pill);
    font-size: 0.72rem;
    font-weight: 600;
    font-family: var(--font-mono);
    background: var(--teal-soft);
    color: var(--teal);
}
.trace-summary-bad {
    background: var(--red-soft);
    color: var(--red);
}
.trace-summary-info {
    background: var(--accent-soft);
    color: var(--accent);
}

/* Plan strip */
.plan-strip {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
}
.plan-strip-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    font-family: var(--font-mono);
}
.plan-strip-chips {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
}
.plan-chip {
    display: inline-block;
    padding: 0.25rem 0.55rem;
    border-radius: var(--r-md);
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-mono);
    background: var(--bg-hover);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}
.plan-chip-completed {
    background: var(--teal-soft);
    color: var(--teal);
    border-color: rgba(13, 148, 136, 0.2);
}
.plan-chip-failed {
    background: var(--red-soft);
    color: var(--red);
    border-color: rgba(239, 68, 68, 0.2);
}
.plan-chip-done {
    background: var(--accent-soft);
    color: var(--accent);
    border-color: var(--border-accent);
    font-weight: 600;
}
.plan-arrow {
    color: var(--text-dim);
    font-size: 0.7rem;
}

/* Confidence pill */
.confidence-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0.4rem 0.8rem;
    border-radius: var(--r-md);
    border: 1px solid var(--border);
}
.confidence-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    font-family: var(--font-sans);
}
.confidence-value {
    font-size: 1rem;
    font-weight: 700;
    font-family: var(--font-mono);
}
.confidence-good { background: var(--teal-soft); }
.confidence-good .confidence-value { color: var(--teal); }
.confidence-warn { background: var(--amber-soft); }
.confidence-warn .confidence-value { color: var(--amber); }
.confidence-bad { background: var(--red-soft); }
.confidence-bad .confidence-value { color: var(--red); }

/* Replan banner */
.replan-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0.6rem 1rem;
    border-radius: var(--r-md);
    background: var(--amber-soft);
    border: 1px solid rgba(245, 158, 11, 0.2);
    font-size: 0.82rem;
    color: var(--amber);
    margin-bottom: 0.75rem;
}
.replan-banner-icon {
    font-size: 1.1rem;
    font-weight: 700;
}

/* Thinking indicator */
.thinking-indicator {
    position: relative;
    padding: 0.8rem 1rem;
    border-radius: var(--r-md);
    background: var(--bg-surface);
    border: 1px solid var(--border-accent);
    overflow: hidden;
    margin: 0.5rem 0;
}
.thinking-shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 0%, var(--accent-soft) 50%, transparent 100%);
    animation: shimmer 2s ease-in-out infinite;
}
@keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}
.thinking-label {
    position: relative;
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--accent);
    font-family: var(--font-mono);
}

/* ── Scrollbars ─────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ── Spacing rhythm ─────────────────────────────────────────────────── */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stMarkdownContainer"]) {
    margin-bottom: 0;
}
[data-testid="stHorizontalBlock"] { gap: 0.85rem; }
.stMarkdown p { margin-bottom: 0.5rem; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { margin-top: 1rem; margin-bottom: 0.5rem; }

/* ── Fade-in animation ──────────────────────────────────────────────── */
.block-container > div {
    animation: fadeSlideIn 280ms cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Sidebar user section ───────────────────────────────────────────── */
.sidebar-user {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.5rem 0;
}
.sidebar-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.8rem;
    flex-shrink: 0;
}
.sidebar-user-info {
    min-width: 0;
}
.sidebar-user-email {
    font-size: 0.8rem;
    color: var(--text);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.sidebar-user-role {
    font-size: 0.68rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── Info cards for dashboard ───────────────────────────────────────── */
.info-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1rem;
    box-shadow: var(--shadow-sm);
}
.info-card-title {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 6px;
}
</style>
"""


def _current_theme() -> str:
    return st.session_state.get("aq_theme", "dark")


def apply_theme() -> None:
    """Inject theme CSS based on session state. Call once per page."""
    vars_block = _DARK_VARS if _current_theme() == "dark" else _LIGHT_VARS
    st.markdown(_BASE_CSS.replace("%VARS%", vars_block), unsafe_allow_html=True)


def _logo_html(height_px: int = 38) -> str:
    if _LOGO_PNG.exists():
        b64 = base64.b64encode(_LOGO_PNG.read_bytes()).decode("ascii")
        return f'<img src="data:image/png;base64,{b64}" alt="RFP.ai" style="height:{height_px}px"/>'
    if _LOGO_SVG.exists():
        return _LOGO_SVG.read_text(encoding="utf-8")
    return '<span style="font-weight:700;color:var(--accent);font-size:1.15rem;font-family:var(--font-sans);letter-spacing:-0.02em">RFP<span style="opacity:0.5">.ai</span></span>'


def render_header(title: str | None = None) -> None:
    """Page header row: logo + page-title pill on the left, theme toggle on the right."""
    left, _spacer, right = st.columns([0.62, 0.23, 0.15])
    with left:
        title_pill = f'<div class="aq-page-title">{title}</div>' if title else ""
        st.markdown(
            f'<div class="aq-header">'
            f'<div class="aq-header-left">'
            f'<div class="aq-logo">{_logo_html(38)}</div>'
            f'{title_pill}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with right:
        current = _current_theme()
        label = "Dark" if current == "dark" else "Light"
        icon = "dark_mode" if current == "dark" else "light_mode"
        if st.button(f"{label}", key="aq_theme_toggle", type="secondary", use_container_width=True):
            st.session_state["aq_theme"] = "light" if current == "dark" else "dark"
            st.rerun()


def render_sidebar_logo() -> None:
    st.markdown(
        f'<div class="aq-sidebar-logo">{_logo_html(28)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Unified sidebar: logo, user section, backend status."""
    with st.sidebar:
        render_sidebar_logo()
        email = st.session_state.get("user_email", "demo@rfp.ai")
        initials = email[0].upper() if email else "U"
        st.markdown(
            f'<div class="sidebar-user">'
            f'<div class="sidebar-avatar">{initials}</div>'
            f'<div class="sidebar-user-info">'
            f'<div class="sidebar-user-email">{email}</div>'
            f'<div class="sidebar-user-role">analyst</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Log out", use_container_width=True, type="secondary", key="aq_sidebar_logout"):
            st.session_state["authenticated"] = False
            st.rerun()
        st.divider()
        api_ok = True
        msg = "Backend online"
        try:
            from utils.api_client import health_check
            status = health_check()
            msg = f"API: {status.get('status', 'ok')}"
        except Exception:
            api_ok = False
            msg = "API unreachable"
        render_status_footer(api_ok, msg)


def render_status_footer(api_ok: bool, message: str = "") -> None:
    dot = "rfp-status-ok" if api_ok else "rfp-status-bad"
    label = message or ("Backend online" if api_ok else "Backend offline")
    st.markdown(
        f'<div style="padding:0.5rem 0;color:var(--text-muted);font-size:0.8rem;font-family:var(--font-mono)">'
        f'<span class="rfp-status-dot {dot}"></span>{label}</div>',
        unsafe_allow_html=True,
    )


# ── Dashboard helper components ──────────────────────────────────────

def render_stat_card(label: str, value: str, sub: str = "", icon: str = "") -> None:
    icon_html = f'<span class="material-symbols-outlined" style="font-size:14px">{icon}</span>' if icon else ""
    sub_html = f'<div class="stat-card-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-card-label">{icon_html}{label}</div>'
        f'<div class="stat-card-value">{value}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_score_gauge(value: float, label: str) -> None:
    tone = "good" if value >= 0.8 else "warn" if value >= 0.6 else "bad"
    pct = min(value * 100, 100)
    st.markdown(
        f'<div class="score-gauge">'
        f'<div class="score-gauge-value {tone}">{value:.2f}</div>'
        f'<div class="score-gauge-label">{label}</div>'
        f'<div class="score-gauge-bar">'
        f'<div class="score-gauge-fill {tone}" style="width:{pct}%"></div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_section_header(title: str, icon: str = "auto_awesome", badge: str = "") -> None:
    badge_html = f'<span class="section-header-badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="section-header-icon material-symbols-outlined">{icon}</span>'
        f'<span class="section-header-title">{title}</span>'
        f'{badge_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, desc: str, icon: str = "inbox") -> None:
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="empty-state-icon"><span class="material-symbols-outlined" style="font-size:48px">{icon}</span></div>'
        f'<div class="empty-state-title">{title}</div>'
        f'<div class="empty-state-desc">{desc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
