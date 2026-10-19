"""Heuristic text helpers used when the model is unavailable (degraded mode)."""
from __future__ import annotations

import re

_METADATA_LABELS = {
    "client", "client company", "company", "customer", "account", "contact", "contact name",
    "contact phone", "phone", "phone number", "email", "e-mail", "industry", "requested solution",
    "solution type", "drafting instruction", "title", "subject", "from", "to", "date", "cc",
}
_REQUIREMENT_HINT = re.compile(
    r"\b(must|shall|should|required|requires|requirement|need|needs|mandatory|expected to|"
    r"will provide|vendor will|bidder will|ensure|comply)\b",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-*•▪◦]|\d{1,3}[.)]|[a-z][.)])\s+", re.IGNORECASE)
_LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z /&-]{1,40})\s*:\s*(.*)$")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+")


def extract_requirements(text: str, limit: int = 25) -> list[str]:
    """Pick requirement-like statements: bullets and sentences with obligation language.

    Lines that look like form fields or contact details are skipped.
    """
    found: list[str] = []
    seen: set[str] = set()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        label = _LABEL_LINE.match(line)
        if label and label.group(1).strip().lower() in _METADATA_LABELS:
            continue
        is_bullet = bool(_BULLET.match(line))
        body = _BULLET.sub("", line).strip()
        candidates = [body] if is_bullet else _SENTENCE_SPLIT.split(body)
        for candidate in candidates:
            sentence = candidate.strip(" -;")
            if len(sentence) < 12:
                continue
            if not is_bullet and not _REQUIREMENT_HINT.search(sentence):
                continue
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(sentence[:400])
            if len(found) >= limit:
                return found
    return found


def lead_paragraph(text: str) -> str:
    """The opening prose of a document: everything before the first blank line, bullet, or label line."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break
            continue
        if _BULLET.match(line) or (_LABEL_LINE.match(line) and len(line) < 60):
            if lines:
                break
            continue
        lines.append(line)
    return " ".join(lines) or (text or "")


def summarize_text(text: str, max_chars: int = 600) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0] + "…"
