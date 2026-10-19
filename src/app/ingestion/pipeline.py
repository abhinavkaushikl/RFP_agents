"""Normalize historical proposal records and chunk their sections for embedding.

Accepted record shapes (all keys optional except some section text):

    {"id", "title" | "rfp_title" | "name", "client_name" | "client" | "customer",
     "industry", "solution_type" | "solutionType",
     "proposal_sections" | "sections": {"<section>": "<text>", ...}
                                     | [{"key" | "title" | "heading": ..., "content" | "text": ...}, ...]}

Without a sections field, long free-text fields that are not metadata become
sections. Section keys and industry names are canonicalized through the domain
profile, so "Pricing", "commercials", and "pricing_notes" land in one section type.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from app.domain.profile import DomainProfile, load_profile, slugify

if TYPE_CHECKING:
    from app.services.embedding_service import EmbeddingService

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_MIN_FREE_TEXT_CHARS = 80

METADATA_KEYS = {
    "id", "external_id", "title", "rfp_title", "name", "client", "client_name", "customer", "industry",
    "sector", "solution_type", "solutiontype", "tags", "source", "source_name", "date", "created_at",
    "updated_at", "url", "language", "requirements", "evaluation_criteria", "rfp_summary", "summary",
    "solution_summary", "metadata", "proposal_sections", "sections", "status", "author", "version",
}


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            text = _flatten(v)
            if text:
                lines.append(f"- {str(k).replace('_', ' ').strip().capitalize()}: {text}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(f"- {_flatten(v)}" for v in value if _flatten(v))
    return str(value).strip()


def extract_sections(record: dict, profile: DomainProfile) -> dict[str, str]:
    raw = record.get("proposal_sections")
    if raw in (None, "", [], {}):
        raw = record.get("sections")
    items: list[tuple[str, Any]] = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        for i, entry in enumerate(raw, 1):
            if isinstance(entry, dict):
                key = entry.get("key") or entry.get("section_key") or entry.get("title") or entry.get("heading") or f"section_{i}"
                items.append((str(key), entry.get("content") or entry.get("text") or entry.get("body") or ""))
    else:
        for key, value in record.items():
            if key.lower() in METADATA_KEYS:
                continue
            text = _flatten(value)
            if len(text) >= _MIN_FREE_TEXT_CHARS:
                items.append((key, text))

    sections: dict[str, str] = {}
    for key, value in items:
        text = _flatten(value)
        if not text:
            continue
        code = profile.canonical_section_key(slugify(str(key), fallback="section"))
        sections[code] = f"{sections[code]}\n\n{text}" if code in sections else text
    return sections


def normalize_historical_record(record: dict, source_name: str, profile: DomainProfile | None = None) -> dict:
    profile = profile or load_profile()
    solution = record.get("solution_type") or record.get("solutionType") or "general"
    return {
        "external_id": str(record["id"]) if record.get("id") not in (None, "") else None,
        "source_name": source_name,
        "title": record.get("title") or record.get("rfp_title") or record.get("name") or "Imported proposal",
        "client_name": record.get("client_name") or record.get("client") or record.get("customer") or None,
        "industry": profile.canonical_industry(record.get("industry") or record.get("sector")),
        "solution_type": slugify(str(solution)),
        "document_json": record,
        "sections": extract_sections(record, profile),
    }


def _sentence_aware_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split on sentence boundaries into ~chunk_size-character chunks; hard-split overlong sentences."""
    text = text.strip()
    if not text:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(sentence):
                end = min(len(sentence), start + chunk_size)
                chunks.append(sentence[start:end])
                if end == len(sentence):
                    break
                start = max(end - overlap, start + 1)
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def chunk_section_text(section_key: str, text: str, chunk_size: int = 500, overlap: int = 75) -> list[dict]:
    chunks: list[dict] = []
    for chunk_index, chunk_text in enumerate(_sentence_aware_chunks(text, chunk_size=chunk_size, overlap=overlap)):
        chunks.append(
            {
                "id": str(uuid.uuid4()),
                "section_key": section_key,
                "content": chunk_text,
                "content_hash": hashlib.sha256(f"{section_key}:{chunk_text}".encode("utf-8")).hexdigest(),
                "chunk_index": chunk_index,
                "token_count": max(1, len(chunk_text.split())),
            }
        )
    return chunks


def ingest_historical_records(
    records: Iterable[dict],
    source_name: str,
    embedding_service: "EmbeddingService | None" = None,
    profile: DomainProfile | None = None,
) -> dict:
    profile = profile or load_profile()
    normalized: list[dict] = []
    skipped: list[dict] = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            skipped.append({"index": i, "reason": "not an object"})
            continue
        item = normalize_historical_record(record, source_name, profile)
        if not item["sections"]:
            skipped.append({"index": i, "id": item["external_id"], "reason": "no section text found"})
            continue
        item["proposal_key"] = item["external_id"] or str(uuid.uuid4())
        normalized.append(item)

    chunks: list[dict] = []
    for item in normalized:
        for section_key, content in item["sections"].items():
            for chunk in chunk_section_text(section_key, str(content)):
                chunk["proposal_id"] = item["proposal_key"]
                chunk["solution_type"] = item["solution_type"]
                chunk["industry"] = item["industry"]
                chunks.append(chunk)

    if embedding_service is not None and chunks:
        embeddings = embedding_service.encode([chunk["content"] for chunk in chunks])
        for chunk, vec in zip(chunks, embeddings, strict=True):
            chunk["embedding"] = vec

    return {
        "ingested_count": len(normalized),
        "section_count": sum(len(item["sections"]) for item in normalized),
        "chunk_count": len(chunks),
        "skipped": skipped,
        "normalized_records": normalized,
        "chunks": chunks,
        "source_name": source_name,
        "report": json.dumps({"source_name": source_name, "ingested_count": len(normalized), "chunk_count": len(chunks)}),
    }
