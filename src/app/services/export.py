"""Client-facing proposal export (PDF and Markdown) built from a stored workflow result."""
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



def _requirements_appendix(story: list[Any], result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    details = (result.get("scores") or {}).get("coverage_details") or []
    if not details:
        return
    story.append(Paragraph("Appendix: Requirement Coverage", styles["h2"]))
    rows = [["Requirement", "Addressed"]]
    for item in details:
        rows.append([Paragraph(_clean(item.get("requirement", "")), styles["list_text"]),
                     "Yes" if item.get("covered") else "Not explicitly"])
    table = Table(rows, colWidths=[13 * cm, 2.8 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F6FA")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DFE5EC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)


def export_pdf(result: dict[str, Any], *, organization: str = "") -> bytes:
    """Proposal document for the buyer: title page block, every section, coverage appendix."""
    request = result.get("request") or {}
    title = request.get("title") or "Proposal"
    client = request.get("client_name") or ""
    buffer = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.8 * cm, leftMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=title, author=organization or "Proposal team",
    )
    subtitle = ", ".join(p for p in (f"Prepared for {client}" if client else "",
                                       f"by {organization}" if organization else "",
                                       datetime.now().strftime("%d %B %Y")) if p)
    story: list[Any] = [Paragraph(_clean(title), styles["title"]), Paragraph(_clean(subtitle), styles["subtitle"])]
    for section in result.get("sections") or []:
        if section.get("error") or not section.get("draft_text"):
            continue
        heading = section.get("title") or str(section.get("section_key", "Section")).replace("_", " ").title()
        story.append(Paragraph(_clean(heading), styles["h2"]))
        _append_markdown_text(story, section.get("draft_text", ""), styles)
        story.append(Spacer(1, 10))
    _requirements_appendix(story, result, styles)
    doc.build(story)
    return buffer.getvalue()


def export_markdown(result: dict[str, Any], *, organization: str = "") -> str:
    request = result.get("request") or {}
    lines = [f"# {request.get('title') or 'Proposal'}", ""]
    if request.get("client_name"):
        lines += [f"Prepared for {request['client_name']}" + (f" by {organization}" if organization else ""), ""]
    for section in result.get("sections") or []:
        if section.get("error") or not section.get("draft_text"):
            continue
        heading = section.get("title") or str(section.get("section_key", "Section")).replace("_", " ").title()
        lines += [f"## {heading}", "", section["draft_text"].strip(), ""]
    return "\n".join(lines).rstrip() + "\n"
