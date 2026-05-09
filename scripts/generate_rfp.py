"""End-to-end RFP proposal generator: input details -> full agent workflow -> PDF.

Runs the 8-agent pipeline on the supplied RFP brief, calls Mistral via Ollama
for each section's prose, and renders a professional, executive-grade PDF.

Usage:

    # JSON config mode (recommended)
    PYTHONPATH=src python3 scripts/generate_rfp.py \\
        --config configs/sample_rfp_input.json \\
        --output out/vodafone_rfp.pdf

    # Quick CLI mode
    PYTHONPATH=src python3 scripts/generate_rfp.py \\
        --title "AIOps Modernization for Vodafone India" \\
        --client "Vodafone India" \\
        --industry "Telecommunications" \\
        --request-text "Vodafone India operates a heterogeneous network..." \\
        --output out/vodafone_rfp.pdf
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.session import SessionLocal
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService

# ── Defaults ─────────────────────────────────────────────────────────
DEFAULT_SECTIONS = [
    "executive_summary",
    "deal_storytelling",
    "competitor_positioning",
    "architecture_diagram",
    "implementation_plan",
    "pricing_notes",
    "financials",
    "contract_annexure",
]

SECTION_TITLES = {
    "executive_summary": "Executive Summary",
    "deal_storytelling": "Engagement Narrative",
    "competitor_positioning": "Competitive Positioning",
    "architecture_diagram": "Solution Architecture",
    "implementation_plan": "Implementation Plan",
    "pricing_notes": "Pricing & Commercials",
    "financials": "Financial Benefits & Business Case",
    "contract_annexure": "Contractual Terms & SLA Annexure",
}

# ── Color palette (corporate navy + slate) ───────────────────────────
NAVY = HexColor("#0F2C4D")
TEAL = HexColor("#1F6F8B")
SLATE = HexColor("#374151")
MUTED = HexColor("#6B7280")
SOFT_BG = HexColor("#F3F4F6")
ACCENT = HexColor("#C9A961")  # gold accent for headers


# ── Styles ───────────────────────────────────────────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}

    s["cover_overline"] = ParagraphStyle(
        "cover_overline",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=ACCENT,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    s["cover_title"] = ParagraphStyle(
        "cover_title",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        textColor=NAVY,
        spaceAfter=10,
        alignment=TA_LEFT,
    )
    s["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=14,
        textColor=SLATE,
        spaceAfter=10,
    )
    s["cover_prepared"] = ParagraphStyle(
        "cover_prepared",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=11,
        textColor=MUTED,
        spaceAfter=4,
    )
    s["cover_meta_label"] = ParagraphStyle(
        "cover_meta_label",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=NAVY,
    )
    s["cover_meta_value"] = ParagraphStyle(
        "cover_meta_value",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=SLATE,
    )

    s["h1"] = ParagraphStyle(
        "h1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY,
        spaceBefore=18,
        spaceAfter=10,
    )
    s["h2"] = ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=TEAL,
        spaceBefore=12,
        spaceAfter=4,
    )
    s["h3"] = ParagraphStyle(
        "h3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=2,
    )
    s["body"] = ParagraphStyle(
        "body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        textColor=SLATE,
    )
    s["bullet"] = ParagraphStyle(
        "bullet",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        leftIndent=16,
        bulletIndent=4,
        spaceAfter=2,
        textColor=SLATE,
    )
    s["caption"] = ParagraphStyle(
        "caption",
        parent=base["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=MUTED,
        spaceAfter=8,
    )
    s["meta"] = ParagraphStyle(
        "meta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=MUTED,
    )
    s["toc_entry"] = ParagraphStyle(
        "toc_entry",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=18,
        textColor=NAVY,
        leftIndent=4,
    )
    s["section_kicker"] = ParagraphStyle(
        "section_kicker",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=ACCENT,
        spaceAfter=2,
    )
    s["section_h"] = ParagraphStyle(
        "section_h",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=NAVY,
        spaceAfter=4,
    )
    s["table_header"] = ParagraphStyle(
        "table_header",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=HexColor("#FFFFFF"),
        alignment=TA_CENTER,
    )
    s["table_cell"] = ParagraphStyle(
        "table_cell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=SLATE,
    )
    return s


# ── Markdown-ish text rendering ──────────────────────────────────────
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


def _safe(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md(text: str) -> str:
    """Convert **bold** markdown to ReportLab <b> tags (after escape)."""
    return _BOLD_RE.sub(r"<b>\1</b>", _safe(text))


def render_markdown_blocks(text: str, styles: dict[str, ParagraphStyle]) -> list:
    """Convert simple markdown-flavored LLM output into ReportLab flowables."""
    flow: list = []
    if not text:
        return flow

    lines = text.splitlines()
    paragraph_buf: list[str] = []
    bullet_buf: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buf:
            return
        flow.append(Paragraph(_inline_md(" ".join(paragraph_buf).strip()), styles["body"]))
        paragraph_buf.clear()

    def flush_bullets() -> None:
        if not bullet_buf:
            return
        for item in bullet_buf:
            flow.append(Paragraph(f"• {_inline_md(item.strip())}", styles["bullet"]))
        bullet_buf.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_bullets()
            continue

        heading_match = _HEADING_RE.match(line.strip())
        bold_only = (
            line.strip().startswith("**")
            and line.strip().endswith("**")
            and line.strip().count("**") == 2
        )

        if heading_match:
            flush_paragraph()
            flush_bullets()
            text_only = heading_match.group(1).strip().strip("*")
            flow.append(Paragraph(_safe(text_only), styles["h3"]))
        elif bold_only:
            flush_paragraph()
            flush_bullets()
            text_only = line.strip().strip("*").strip()
            flow.append(Paragraph(_safe(text_only), styles["h3"]))
        elif line.lstrip().startswith(("- ", "* ", "• ")):
            flush_paragraph()
            bullet_buf.append(line.lstrip()[2:].strip())
        elif re.match(r"^\d+[.)]\s+", line.lstrip()):
            flush_paragraph()
            cleaned = re.sub(r"^\d+[.)]\s+", "", line.lstrip())
            bullet_buf.append(cleaned)
        else:
            flush_bullets()
            paragraph_buf.append(line.strip())

    flush_paragraph()
    flush_bullets()
    return flow


# ── Page decoration ──────────────────────────────────────────────────
def _on_page(canvas, doc) -> None:
    canvas.saveState()
    width, _height = A4

    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.5 * cm, width - 2 * cm, 1.5 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.0 * cm, "CONFIDENTIAL — RFP RESPONSE")
    canvas.drawRightString(width - 2 * cm, 1.0 * cm, f"Page {doc.page}")

    canvas.restoreState()


# ── Compliance matrix builder ────────────────────────────────────────
def build_compliance_matrix(requirements: list[str], sections: list[dict]) -> list[list[str]]:
    rows: list[list[str]] = [["#", "Requirement", "Addressed In"]]
    for i, req in enumerate(requirements[:20], 1):
        req_lower = req.lower()
        addressed: list[str] = []
        for sec in sections:
            text = str(sec.get("draft_text", "")).lower()
            head = req_lower[:24]
            if head and head in text:
                addressed.append(SECTION_TITLES.get(sec["section_key"], sec["section_key"]))
        if not addressed:
            addressed = ["Executive Summary"]
        rows.append([str(i), req[:120], ", ".join(addressed[:2])])
    return rows


# ── Cover, TOC, and section renderers ────────────────────────────────
def render_cover(
    flow: list,
    styles: dict[str, ParagraphStyle],
    *,
    title: str,
    client: str,
    industry: str,
    solution_type: str,
    workflow_id: str,
    composite_score: float,
) -> None:
    flow.append(Spacer(1, 4 * cm))
    flow.append(Paragraph("RFP RESPONSE DOCUMENT", styles["cover_overline"]))
    flow.append(Paragraph(_safe(title), styles["cover_title"]))
    flow.append(HRFlowable(width="35%", thickness=2, color=ACCENT, spaceBefore=4, spaceAfter=14))
    flow.append(Paragraph(f"Prepared for <b>{_safe(client)}</b>", styles["cover_subtitle"]))
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("Prepared by the AIOps Solutions Practice", styles["cover_prepared"]))

    flow.append(Spacer(1, 3 * cm))

    meta_rows = [
        [Paragraph("Industry", styles["cover_meta_label"]), Paragraph(_safe(industry), styles["cover_meta_value"])],
        [Paragraph("Solution Family", styles["cover_meta_label"]), Paragraph(_safe(solution_type), styles["cover_meta_value"])],
        [
            Paragraph("Document Date", styles["cover_meta_label"]),
            Paragraph(datetime.now(timezone.utc).strftime("%d %B %Y"), styles["cover_meta_value"]),
        ],
        [Paragraph("Document Version", styles["cover_meta_label"]), Paragraph("1.0 (Draft)", styles["cover_meta_value"])],
        [Paragraph("Workflow Reference", styles["cover_meta_label"]), Paragraph(_safe(workflow_id[:8]), styles["cover_meta_value"])],
        [
            Paragraph("Quality Composite", styles["cover_meta_label"]),
            Paragraph(f"<b>{composite_score:.2f}</b> / 1.00", styles["cover_meta_value"]),
        ],
    ]
    table = Table(meta_rows, colWidths=[5 * cm, 11 * cm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, NAVY),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    flow.append(table)


def render_toc(flow: list, styles: dict[str, ParagraphStyle], section_order: list[str]) -> None:
    flow.append(Paragraph("Table of Contents", styles["h1"]))
    flow.append(HRFlowable(width="100%", thickness=0.4, color=NAVY, spaceAfter=10))
    items = ["Engagement Brief", "Compliance Matrix"]
    items += [SECTION_TITLES.get(k, k.replace("_", " ").title()) for k in section_order]
    items += ["Validation & Quality Scores", "Pipeline Trace"]
    for i, name in enumerate(items, 1):
        flow.append(Paragraph(f"{i:>2}. &nbsp;&nbsp;{_safe(name)}", styles["toc_entry"]))


def render_engagement_brief(
    flow: list,
    styles: dict[str, ParagraphStyle],
    request: dict,
    solution: dict,
) -> None:
    flow.append(Paragraph("Engagement Brief", styles["h1"]))
    flow.append(HRFlowable(width="100%", thickness=0.4, color=NAVY, spaceAfter=8))

    flow.append(Paragraph("Request Summary", styles["h2"]))
    flow.append(Paragraph(_safe(request.get("request_summary", "")), styles["body"]))

    requirements = request.get("requirements", [])
    if requirements:
        flow.append(Paragraph(f"Requirements ({len(requirements)})", styles["h2"]))
        for r in requirements[:15]:
            flow.append(Paragraph(f"• {_safe(r)}", styles["bullet"]))

    vendors = request.get("vendors", [])
    if vendors:
        flow.append(Paragraph("Vendor Environment", styles["h2"]))
        flow.append(Paragraph(_safe(", ".join(vendors)), styles["body"]))

    if solution.get("matching_offerings"):
        flow.append(Paragraph("Solution Family Mapping", styles["h2"]))
        for off in solution["matching_offerings"]:
            flow.append(Paragraph(f"• {_safe(off)}", styles["bullet"]))


def render_compliance_matrix(
    flow: list,
    styles: dict[str, ParagraphStyle],
    matrix_rows: list[list[str]],
) -> None:
    flow.append(Paragraph("Compliance Matrix", styles["h1"]))
    flow.append(HRFlowable(width="100%", thickness=0.4, color=NAVY, spaceAfter=8))
    flow.append(
        Paragraph(
            "Mapping of each requirement in the brief to the section(s) of this response that address it.",
            styles["caption"],
        )
    )

    rendered: list[list] = [
        [
            Paragraph("#", styles["table_header"]),
            Paragraph("Requirement", styles["table_header"]),
            Paragraph("Addressed In", styles["table_header"]),
        ]
    ]
    for row in matrix_rows[1:]:
        rendered.append(
            [
                Paragraph(_safe(row[0]), styles["table_cell"]),
                Paragraph(_safe(row[1]), styles["table_cell"]),
                Paragraph(_safe(row[2]), styles["table_cell"]),
            ]
        )

    table = Table(rendered, colWidths=[1 * cm, 11 * cm, 5 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOFT_BG, HexColor("#FFFFFF")]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, MUTED),
            ]
        )
    )
    flow.append(table)


def render_section(
    flow: list,
    styles: dict[str, ParagraphStyle],
    *,
    section_index: int,
    section: dict,
) -> None:
    section_key = section["section_key"]
    title = SECTION_TITLES.get(section_key, section_key.replace("_", " ").title())

    flow.append(Paragraph(f"SECTION {section_index:02d}", styles["section_kicker"]))
    flow.append(Paragraph(_safe(title), styles["section_h"]))
    flow.append(HRFlowable(width="35%", thickness=1.5, color=ACCENT, spaceBefore=2, spaceAfter=14))

    body_blocks = render_markdown_blocks(str(section.get("draft_text", "")), styles)
    flow.extend(body_blocks)

    validation = section.get("validation", {}) or {}
    validation_score = validation.get("validation_score", 0.0)
    missing = validation.get("missing_items", []) or []
    citations = section.get("citations", []) or []

    flow.append(Spacer(1, 0.3 * cm))
    footer_bits = [f"<b>Validation Score:</b> {validation_score:.2f}"]
    if missing:
        footer_bits.append(
            f"<b>Open items:</b> {_safe(', '.join(str(m)[:50] for m in missing[:2]))}"
        )
    if citations:
        footer_bits.append(
            f"<b>Evidence chunks:</b> {_safe(', '.join(c[:8] for c in citations[:5]))}"
        )
    flow.append(Paragraph(" &nbsp;|&nbsp; ".join(footer_bits), styles["meta"]))


def render_quality_scores(
    flow: list, styles: dict[str, ParagraphStyle], scores: dict
) -> None:
    flow.append(Paragraph("Validation & Quality Scores", styles["h1"]))
    flow.append(HRFlowable(width="100%", thickness=0.4, color=NAVY, spaceAfter=8))

    rows = [
        [
            Paragraph("Metric", styles["table_header"]),
            Paragraph("Score (0–1)", styles["table_header"]),
            Paragraph("Interpretation", styles["table_header"]),
        ],
        [
            Paragraph("Composite", styles["table_cell"]),
            Paragraph(f"<b>{scores.get('composite_score', 0):.2f}</b>", styles["table_cell"]),
            Paragraph("Overall response quality", styles["table_cell"]),
        ],
        [
            Paragraph("Requirement Coverage", styles["table_cell"]),
            Paragraph(f"{scores.get('requirement_coverage_score', 0):.2f}", styles["table_cell"]),
            Paragraph("Fraction of stated requirements addressed in the response", styles["table_cell"]),
        ],
        [
            Paragraph("Solution Fit", styles["table_cell"]),
            Paragraph(f"{scores.get('solution_fit_score', 0):.2f}", styles["table_cell"]),
            Paragraph("Alignment with chosen solution family", styles["table_cell"]),
        ],
        [
            Paragraph("Historical Similarity", styles["table_cell"]),
            Paragraph(f"{scores.get('historical_similarity_score', 0):.2f}", styles["table_cell"]),
            Paragraph("Match against precedent retrieved from the corpus", styles["table_cell"]),
        ],
        [
            Paragraph("Completeness", styles["table_cell"]),
            Paragraph(f"{scores.get('completeness_score', 0):.2f}", styles["table_cell"]),
            Paragraph("All target sections present and populated", styles["table_cell"]),
        ],
    ]
    table = Table(rows, colWidths=[5 * cm, 3 * cm, 9 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOFT_BG, HexColor("#FFFFFF")]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, MUTED),
            ]
        )
    )
    flow.append(table)


def render_pipeline_trace(
    flow: list, styles: dict[str, ParagraphStyle], step_summaries: list[str]
) -> None:
    flow.append(Paragraph("Pipeline Trace (Annex)", styles["h1"]))
    flow.append(HRFlowable(width="100%", thickness=0.4, color=NAVY, spaceAfter=8))
    flow.append(
        Paragraph(
            "Each entry below corresponds to one agent invocation in the multi-agent workflow that produced this document.",
            styles["caption"],
        )
    )
    for i, step in enumerate(step_summaries, 1):
        flow.append(Paragraph(f"{i:>2}. {_safe(step)}", styles["bullet"]))


# ── Main builder ─────────────────────────────────────────────────────
def render_pdf(
    *,
    output_path: Path,
    title: str,
    client: str,
    industry: str,
    solution_type: str,
    workflow_result: dict,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
        author="RFP-LLM Platform",
    )

    flow: list = []

    render_cover(
        flow,
        styles,
        title=title,
        client=client,
        industry=industry,
        solution_type=solution_type,
        workflow_id=workflow_result["workflow_id"],
        composite_score=workflow_result["scores"]["composite_score"],
    )
    flow.append(PageBreak())

    section_keys = [s["section_key"] for s in workflow_result["sections"]]
    render_toc(flow, styles, section_keys)
    flow.append(PageBreak())

    render_engagement_brief(
        flow,
        styles,
        request=workflow_result["request"],
        solution=workflow_result.get("solution_comparison", {}),
    )
    flow.append(PageBreak())

    matrix = build_compliance_matrix(
        workflow_result["request"].get("requirements", []),
        workflow_result["sections"],
    )
    render_compliance_matrix(flow, styles, matrix)
    flow.append(PageBreak())

    for i, section in enumerate(workflow_result["sections"], 1):
        render_section(flow, styles, section_index=i, section=section)
        flow.append(PageBreak())

    render_quality_scores(flow, styles, workflow_result["scores"])
    flow.append(PageBreak())

    render_pipeline_trace(flow, styles, workflow_result.get("step_summaries", []))

    doc.build(flow, onFirstPage=_on_page, onLaterPages=_on_page)


# ── Workflow + CLI ───────────────────────────────────────────────────
def run_workflow(payload: dict) -> dict:
    db = SessionLocal()
    try:
        embedding_service = EmbeddingService()
        retrieval_service = RetrievalService(db=db, embedding_service=embedding_service)
        llm_service = LLMService()
        orchestrator = ProposalWorkflowOrchestrator(
            retrieval_service=retrieval_service,
            llm_service=llm_service,
        )
        return orchestrator.run_proposal_workflow(payload)
    finally:
        db.close()


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", type=Path, help="Path to JSON file with RFP details")
    parser.add_argument("--title", help="Proposal title")
    parser.add_argument("--client", help="Client / customer name")
    parser.add_argument("--industry", default="Telecommunications", help="Industry vertical")
    parser.add_argument("--solution-type", default="aiops_general", help="Solution type code")
    parser.add_argument("--request-text", help="Raw RFP / requirements text")
    parser.add_argument(
        "--sections",
        nargs="+",
        default=DEFAULT_SECTIONS,
        help=f"Target sections (default: {' '.join(DEFAULT_SECTIONS)})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("out/rfp_response.pdf"),
        help="Output PDF path (default: out/rfp_response.pdf)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    config = load_config(args.config) if args.config else {}

    title = args.title or config.get("title")
    client = args.client or config.get("client")
    industry = args.industry or config.get("industry", "Telecommunications")
    solution_type = args.solution_type or config.get("solution_type", "aiops_general")
    request_text = args.request_text or config.get("request_text")
    sections = (
        args.sections if args.sections != DEFAULT_SECTIONS else config.get("sections", DEFAULT_SECTIONS)
    )

    if not (title and client and request_text):
        print(
            "ERROR: --title, --client, and --request-text are required (or supplied via --config).",
            file=sys.stderr,
        )
        return 2

    payload = {
        "request_text": request_text,
        "title": title,
        "industry": industry,
        "solution_type": solution_type,
        "target_sections": sections,
        "metadata": {"client_name": client},
    }

    print(f"Running RFP workflow for: {title}")
    print(f"  client    : {client}")
    print(f"  industry  : {industry}")
    print(f"  sections  : {len(sections)}")
    print()
    print("Generating sections via Mistral (Ollama). First section may take ~10s...")

    result = run_workflow(payload)
    print()
    print(f"Workflow completed: {result['workflow_id']}")
    print(f"  composite score    : {result['scores']['composite_score']:.2f}")
    print(f"  sections generated : {len(result['sections'])}")
    for sec in result["sections"]:
        chars = len(str(sec.get("draft_text", "")))
        print(f"    - {sec['section_key']}: {chars} chars")
    print()
    print(f"Rendering PDF to: {args.output}")
    render_pdf(
        output_path=args.output,
        title=title,
        client=client,
        industry=industry,
        solution_type=solution_type,
        workflow_result=result,
    )
    print(f"Done: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
