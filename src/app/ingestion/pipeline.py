from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable


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


def chunk_section_text(section_key: str, text: str, chunk_size: int = 500, overlap: int = 75) -> list[dict]:
    if not text.strip():
        return []
    chunks: list[dict] = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk_text = text[start:end].strip()
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
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
        chunk_index += 1
    return chunks


def build_embedding_stub(text: str, dimensions: int = 8) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round((digest[i] / 255), 6) for i in range(dimensions)]


def ingest_historical_records(records: Iterable[dict], source_name: str) -> dict:
    normalized = [normalize_historical_record(record, source_name) for record in records]
    chunks: list[dict] = []
    for item in normalized:
        proposal_id = item["external_id"] or str(uuid.uuid4())
        for section_key, content in item["sections"].items():
            for chunk in chunk_section_text(section_key, str(content)):
                chunk["proposal_id"] = proposal_id
                chunk["solution_type"] = item["solution_type"]
                chunk["industry"] = item["industry"]
                chunk["embedding"] = build_embedding_stub(chunk["content"])
                chunks.append(chunk)
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
