"""HTTP client wrapping the FastAPI backend endpoints."""
from __future__ import annotations

import requests

BASE_URL = "http://localhost:8000/api"
TIMEOUT = 120  # LLM workflows can be slow


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


# ── Health ──────────────────────────────────────────────────────────────
def health_check() -> dict:
    resp = requests.get(_url("/health"), timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── Workflow Runs ───────────────────────────────────────────────────────
def create_workflow_run(
    request_text: str,
    title: str = "AIOps Proposal Request",
    industry: str | None = None,
    solution_type: str | None = None,
    user_instruction: str | None = None,
    target_sections: list[str] | None = None,
) -> dict:
    payload: dict = {"request_text": request_text, "title": title}
    if industry:
        payload["industry"] = industry
    if solution_type:
        payload["solution_type"] = solution_type
    if user_instruction:
        payload["user_instruction"] = user_instruction
    if target_sections:
        payload["target_sections"] = target_sections
    resp = requests.post(_url("/workflow-runs"), json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Section Revision ────────────────────────────────────────────────────
def revise_section(
    section_id: str,
    instruction: str,
    section_key: str | None = None,
) -> dict:
    payload: dict = {"instruction": instruction}
    if section_key:
        payload["section_key"] = section_key
    resp = requests.post(
        _url(f"/generated-sections/{section_id}/revise"),
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


# ── Document Matching ───────────────────────────────────────────────────
def run_document_match(
    request_text: str,
    document_text: str,
    solution_type: str | None = None,
) -> dict:
    payload: dict = {"request_text": request_text, "document_text": document_text}
    if solution_type:
        payload["solution_type"] = solution_type
    resp = requests.post(_url("/document-match-runs"), json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Ingestion ───────────────────────────────────────────────────────────
def ingest_historical_proposals(
    records: list[dict],
    source_name: str = "ui_upload",
) -> dict:
    payload = {"records": records, "source_name": source_name}
    resp = requests.post(
        _url("/historical-proposals/ingest"), json=payload, timeout=TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


# ── Retrieval Search ────────────────────────────────────────────────────
def retrieval_search(
    query: str,
    section_type: str | None = None,
    solution_type: str | None = None,
    industry: str | None = None,
    top_k: int = 5,
) -> dict:
    payload: dict = {"query": query, "top_k": top_k}
    if section_type:
        payload["section_type"] = section_type
    if solution_type:
        payload["solution_type"] = solution_type
    if industry:
        payload["industry"] = industry
    resp = requests.post(_url("/retrieval/search"), json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Revision History ────────────────────────────────────────────────────
def get_section_revisions(section_id: str) -> dict:
    resp = requests.get(
        _url(f"/generated-sections/{section_id}/revisions"), timeout=10
    )
    resp.raise_for_status()
    return resp.json()
