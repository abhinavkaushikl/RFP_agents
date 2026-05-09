"""PDF export helpers for generated Streamlit proposals."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_MARKDOWN_BOLD = re.compile(r"\*\*(.*?)\*\*")
_NUMBERED_ITEM = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
_BULLET_ITEM = re.compile(r"^\s*[-*]\s+(.+)$")


def _strip_markdown(value: Any) -> str:
    text = "" if value is None else str(value)
    text = _MARKDOWN_BOLD.sub(r"\1", text)
    text = text.replace("__", "")
    text = text.replace("###", "").replace("##", "").replace("#", "")
    return text.strip()


def _clean(value: Any) -> str:
    text = _strip_markdown(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#17202A"),
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#687385"),
            spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#246BFE"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#17202A"),
            spaceAfter=8,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#17202A"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "list_text": ParagraphStyle(
            "list_text",
            parent=base["BodyText"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#17202A"),
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#687385"),
        ),
    }


def _append_list_item(story: list[Any], marker: str, text: str, styles: dict[str, ParagraphStyle]) -> None:
    table = Table(
        [[Paragraph(_clean(marker), styles["list_text"]), Paragraph(_clean(text), styles["list_text"])]],
        colWidths=[0.7 * cm, 15.1 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)


def _append_markdown_text(story: list[Any], text: str, styles: dict[str, ParagraphStyle]) -> None:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue

        clean_line = _strip_markdown(line)
        numbered = _NUMBERED_ITEM.match(clean_line)
        bullet = _BULLET_ITEM.match(clean_line)
        if numbered:
            _append_list_item(story, f"{numbered.group(1)}.", numbered.group(2), styles)
        elif bullet:
            _append_list_item(story, "-", bullet.group(1), styles)
        elif raw_line.strip().startswith("**") and raw_line.strip().endswith("**"):
            story.append(Paragraph(_clean(clean_line), styles["section_heading"]))
        else:
            story.append(Paragraph(_clean(clean_line), styles["body"]))


def _append_simple_list(
    story: list[Any],
    items: list[Any],
    styles: dict[str, ParagraphStyle],
    *,
    numbered: bool = False,
) -> None:
    if not items:
        story.append(Paragraph("No items returned by the workflow.", styles["small"]))
        return
    for index, item in enumerate(items, 1):
        marker = f"{index}." if numbered else "-"
        _append_list_item(story, marker, str(item), styles)


def build_proposal_pdf(
    *,
    workflow_result: dict[str, Any],
    metadata: dict[str, Any],
    title: str,
) -> bytes:
    """Render a compact proposal PDF from the API response Streamlit receives."""
    buffer = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=title,
        author="RFP Proposal Platform",
    )

    story: list[Any] = [
        Paragraph(_clean(title), styles["title"]),
        Paragraph(
            f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')} | "
            f"Workflow {_clean(workflow_result.get('workflow_id', ''))}",
            styles["subtitle"],
        ),
    ]

    client_rows = [
        ["Client Company", _clean(metadata.get("client_name") or metadata.get("selected_company"))],
        ["Contact Name", _clean(metadata.get("contact_name"))],
        ["Phone Number", _clean(metadata.get("phone_number"))],
        ["Solution", _clean(metadata.get("solution_label"))],
        ["Priorities", _clean(", ".join(metadata.get("priorities", [])))],
    ]
    table = Table(client_rows, colWidths=[4.2 * cm, 11.6 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F6FA")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#17202A")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DFE5EC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 10)])

    scores = workflow_result.get("scores") or {}
    if scores:
        story.append(Paragraph("Proposal Score", styles["h2"]))
        score_rows = [
            ["Composite", f"{scores.get('composite_score', 0):.2f}"],
            ["Requirement Coverage", f"{scores.get('requirement_coverage_score', 0):.2f}"],
            ["Solution Fit", f"{scores.get('solution_fit_score', 0):.2f}"],
            ["Historical Similarity", f"{scores.get('historical_similarity_score', 0):.2f}"],
        ]
        score_table = Table(score_rows, colWidths=[7.8 * cm, 8 * cm])
        score_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DFE5EC")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([score_table, Spacer(1, 8)])

    request = workflow_result.get("request") or {}
    requirements = request.get("requirements") or []
    story.append(Paragraph("Requirements", styles["h2"]))
    _append_simple_list(story, requirements, styles, numbered=True)
    story.append(Spacer(1, 8))

    solution = workflow_result.get("solution_comparison") or {}
    offerings = solution.get("matching_offerings") or []
    positioning_notes = solution.get("positioning_notes") or []
    story.append(Paragraph("Relevant Offerings", styles["h2"]))
    _append_simple_list(story, offerings, styles)
    if positioning_notes:
        story.append(Paragraph("Positioning Notes", styles["section_heading"]))
        _append_simple_list(story, positioning_notes, styles)
    story.append(Spacer(1, 8))

    for section in workflow_result.get("sections", []):
        section_title = str(section.get("section_key", "Proposal Section")).replace("_", " ").title()
        story.append(Paragraph(_clean(section_title), styles["h2"]))
        _append_markdown_text(story, section.get("draft_text", ""), styles)
        citations = section.get("citations") or []
        if citations:
            story.append(Paragraph(f"Citations: {_clean(', '.join(citations))}", styles["small"]))
        story.append(Spacer(1, 8))

    steps = workflow_result.get("step_summaries") or []
    if steps:
        story.append(Paragraph("Pipeline Trace", styles["h2"]))
        for index, step in enumerate(steps, 1):
            story.append(Paragraph(f"{index}. {_clean(step)}", styles["small"]))

    doc.build(story)
    return buffer.getvalue()
