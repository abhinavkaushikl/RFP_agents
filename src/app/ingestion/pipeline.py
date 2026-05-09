from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.embedding_service import EmbeddingService


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def normalize_historical_record(record: dict, source_name: str) -> dict:
    solution_type = record.get("solutionType") or record.get("solution_type") or "aiops_general"
    sections = record.get("proposal_sections") or {
        key: value
        for key, value in record.items()
        if isinstance(value, str) and key not in {"client_name", "industry", "title"}
    }
    return {
        "external_id": record.get("id"),
        "source_name": source_name,
        "title": record.get("title") or record.get("rfp_title") or "Imported Proposal",
        "client_name": record.get("client_name") or record.get("client") or "Unknown Client",
        "industry": record.get("industry") or "Telecommunications",
        "solution_type": solution_type,
        "document_json": record,
        "sections": sections,
    }


def _sentence_aware_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text on sentence boundaries, packing into chunks of ~chunk_size chars.

    Falls back to a fixed-window slice when a single sentence exceeds chunk_size.
    """
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


def chunk_section_text(
    section_key: str, text: str, chunk_size: int = 500, overlap: int = 75
) -> list[dict]:
    pieces = _sentence_aware_chunks(text, chunk_size=chunk_size, overlap=overlap)
    chunks: list[dict] = []
    for chunk_index, chunk_text in enumerate(pieces):
        content_hash = hashlib.sha256(f"{section_key}:{chunk_text}".encode("utf-8")).hexdigest()
        chunks.append(
            {
                "id": str(uuid.uuid4()),
                "section_key": section_key,
                "content": chunk_text,
                "content_hash": content_hash,
                "chunk_index": chunk_index,
                "token_count": max(1, len(chunk_text.split())),
            }
        )
    return chunks


def ingest_historical_records(
    records: Iterable[dict],
    source_name: str,
    embedding_service: "EmbeddingService | None" = None,
) -> dict:
    normalized = [normalize_historical_record(record, source_name) for record in records]
    chunks: list[dict] = []
    for item in normalized:
        proposal_id = item["external_id"] or str(uuid.uuid4())
        for section_key, content in item["sections"].items():
            for chunk in chunk_section_text(section_key, str(content)):
                chunk["proposal_id"] = proposal_id
                chunk["solution_type"] = item["solution_type"]
                chunk["industry"] = item["industry"]
                chunks.append(chunk)

    if embedding_service is not None and chunks:
        texts = [chunk["content"] for chunk in chunks]
        embeddings = embedding_service.encode(texts)
        for chunk, vec in zip(chunks, embeddings, strict=True):
            chunk["embedding"] = vec

    return {
        "ingested_count": len(normalized),
        "section_count": sum(len(item["sections"]) for item in normalized),
        "chunk_count": len(chunks),
        "normalized_records": normalized,
        "chunks": chunks,
        "source_name": source_name,
        "report": json.dumps(
            {
                "source_name": source_name,
                "ingested_count": len(normalized),
                "chunk_count": len(chunks),
            }
        ),
    }
