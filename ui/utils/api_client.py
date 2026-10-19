"""HTTP client for the FastAPI backend.

Configure with environment variables:
    RFP_API_BASE_URL   default http://localhost:8000/api
    RFP_UI_API_KEY     sent as X-API-Key when the API requires keys
"""
from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = os.getenv("RFP_API_BASE_URL", "http://localhost:8000/api").rstrip("/")
API_KEY = os.getenv("RFP_UI_API_KEY", "")
TIMEOUT = int(os.getenv("RFP_UI_TIMEOUT_S", "600"))  # multi-section runs can take minutes under rate limits


class APIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


def _handle(resp: requests.Response) -> dict:
    if resp.ok:
        return resp.json()
    message = f"HTTP {resp.status_code}"
    try:
        body = resp.json()
        if isinstance(body.get("error"), dict):
            message = body["error"].get("message") or message
        elif body.get("detail"):
            detail = body["detail"]
            message = detail if isinstance(detail, str) else "; ".join(
                f"{'.'.join(str(p) for p in d.get('loc', [])[1:])}: {d.get('msg')}" for d in detail
            )
    except ValueError:
        message = resp.text[:300] or message
    raise APIError(message, resp.status_code, resp.headers.get("Retry-After"))


def _get(path: str, timeout: int = 15, **params: Any) -> dict:
    return _handle(requests.get(_url(path), params=params or None, headers=_headers(), timeout=timeout))


def _post(path: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    clean = {k: v for k, v in payload.items() if v not in (None, "", [], {})}
    return _handle(requests.post(_url(path), json=clean, headers=_headers(), timeout=timeout))


# ── Health & configuration ──────────────────────────────────────────────
def health_check() -> dict:
    return _get("/health", timeout=5)


def readiness() -> dict:
    resp = requests.get(_url("/health/ready"), headers=_headers(), timeout=10)
    return resp.json()


def list_profiles() -> dict:
    return _get("/profiles")


def get_profile(name: str) -> dict:
    return _get(f"/profiles/{name}")


# ── Workflows ───────────────────────────────────────────────────────────
def create_workflow_run(
    request_text: str,
    title: str = "Proposal request",
    *,
    client_name: str | None = None,
    industry: str | None = None,
    solution_type: str | None = None,
    user_instruction: str | None = None,
    target_sections: list[str] | None = None,
    profile: str | None = None,
    cache_policy: str = "use",
    metadata: dict | None = None,
) -> dict:
    return _post("/workflow-runs", {
        "request_text": request_text, "title": title, "client_name": client_name, "industry": industry,
        "solution_type": solution_type, "user_instruction": user_instruction, "target_sections": target_sections,
        "profile": profile, "cache_policy": cache_policy, "metadata": metadata,
    })


def revise_section(
    section_id: str,
    instruction: str,
    *,
    section_key: str | None = None,
    base_text: str | None = None,
    requirements: list[str] | None = None,
    profile: str | None = None,
    cache_policy: str = "use",
) -> dict:
    return _post(f"/generated-sections/{section_id}/revise", {
        "instruction": instruction, "section_key": section_key, "base_text": base_text,
        "requirements": requirements, "profile": profile, "cache_policy": cache_policy,
    })


def get_section_revisions(section_id: str) -> dict:
    return _get(f"/generated-sections/{section_id}/revisions")


def run_intent_detection(transcript_text: str, file_name: str | None = None, *, profile: str | None = None,
                         cache_policy: str = "use") -> dict:
    return _post("/intent-detection-runs", {"transcript_text": transcript_text, "file_name": file_name,
                                            "profile": profile, "cache_policy": cache_policy})


def run_market_research(offerings: list[str], requirement_summary: str = "", industry: str | None = None,
                        max_companies: int = 8, *, profile: str | None = None) -> dict:
    return _post("/market-research-runs", {"offerings": offerings, "requirement_summary": requirement_summary,
                                           "industry": industry, "max_companies": max_companies, "profile": profile})


def run_document_match(request_text: str, document_text: str, solution_type: str | None = None, *,
                       industry: str | None = None, profile: str | None = None, cache_policy: str = "use") -> dict:
    return _post("/document-match-runs", {"request_text": request_text, "document_text": document_text,
                                          "solution_type": solution_type, "industry": industry,
                                          "profile": profile, "cache_policy": cache_policy})


# ── Knowledge base ──────────────────────────────────────────────────────
def ingest_historical_proposals(records: list[dict], source_name: str = "ui_upload", profile: str | None = None) -> dict:
    return _post("/historical-proposals/ingest", {"records": records, "source_name": source_name, "profile": profile})


def upload_historical_documents(files: list[tuple[str, bytes]], *, source_name: str = "ui_upload",
                                profile: str | None = None, client_name: str | None = None,
                                industry: str | None = None, solution_type: str | None = None) -> dict:
    data = {k: v for k, v in {"source_name": source_name, "profile": profile, "client_name": client_name,
                              "industry": industry, "solution_type": solution_type}.items() if v}
    resp = requests.post(
        _url("/historical-proposals/upload"),
        files=[("files", (name, content)) for name, content in files],
        data=data,
        headers=_headers(),
        timeout=TIMEOUT,
    )
    return _handle(resp)


def extract_text(file_name: str, content: bytes, profile: str | None = None) -> dict:
    resp = requests.post(
        _url("/documents/extract-text"),
        files={"file": (file_name, content)},
        data={"profile": profile} if profile else None,
        headers=_headers(),
        timeout=120,
    )
    return _handle(resp)


def retrieval_search(query: str, section_type: str | None = None, solution_type: str | None = None,
                     industry: str | None = None, top_k: int = 5, *, profile: str | None = None) -> dict:
    return _post("/retrieval/search", {"query": query, "section_type": section_type, "solution_type": solution_type,
                                       "industry": industry, "top_k": top_k, "profile": profile}, timeout=60)


# ── Usage ───────────────────────────────────────────────────────────────
def get_usage_summary(days: int = 7) -> dict:
    return _get("/usage/summary", days=days)


def get_workflow_usage(workflow_id: str) -> dict:
    return _get(f"/usage/workflows/{workflow_id}")
