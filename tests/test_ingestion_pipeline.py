from __future__ import annotations

from app.domain.profile import load_profile
from app.ingestion.documents import document_to_record, split_into_sections
from app.ingestion.pipeline import chunk_section_text, ingest_historical_records, normalize_historical_record


def test_proposal_sections_dict():
    n = normalize_historical_record(
        {"id": "1", "title": "Proposal", "client_name": "Client A", "solutionType": "Data Platform",
         "proposal_sections": {"executive_summary": "Summary text"}},
        "source-a",
    )
    assert n["solution_type"] == "data_platform"
    assert n["sections"] == {"executive_summary": "Summary text"}


def test_sections_key_is_accepted_and_metadata_is_not_indexed():
    n = normalize_historical_record(
        {"title": "Example", "industry": "Healthcare", "solution_type": "cloud_migration",
         "sections": {"executive_summary": "Our platform...", "Pricing": "Fixed fee."}},
        "ui_upload",
    )
    assert set(n["sections"]) == {"executive_summary", "pricing_notes"}
    assert n["solution_type"] == "cloud_migration"


def test_sections_as_list_and_aliases_merge():
    n = normalize_historical_record(
        {"id": "x", "sections": [{"title": "Architecture", "content": "Layered design."},
                                 {"key": "architecture_diagram", "text": "Event bus."}]},
        "s",
    )
    assert list(n["sections"]) == ["solution_architecture"]
    assert "Layered design." in n["sections"]["solution_architecture"] and "Event bus." in n["sections"]["solution_architecture"]


def test_no_domain_defaults():
    n = normalize_historical_record({"id": "2", "proposal_sections": {"implementation_plan": "Phase 1"}}, "s")
    assert n["industry"] is None and n["solution_type"] == "general" and n["client_name"] is None


def test_free_text_fallback_skips_short_and_metadata_fields():
    n = normalize_historical_record(
        {"id": "3", "rfp_summary": "x" * 200, "approach": "We will deliver in phases. " * 5, "note": "short"}, "s"
    )
    assert list(n["sections"]) == ["technical_approach"]


def test_chunking_hashes_and_records_without_text_are_skipped():
    chunks = chunk_section_text("executive_summary", "A" * 700)
    assert len(chunks) >= 2 and all(c["content_hash"] for c in chunks)
    result = ingest_historical_records(
        [{"id": "a", "proposal_sections": {"implementation_plan": "Phased rollout across all sites."}},
         {"id": "b", "title": "no sections"}],
        "source-b",
    )
    assert result["ingested_count"] == 1 and result["chunk_count"] >= 1
    assert result["skipped"][0]["reason"] == "no section text found"


def test_document_splitting_by_headings():
    text = (
        "Proposal for Contoso\n\n"
        "# Executive Summary\nWe propose a phased programme that delivers value early and reduces risk for Contoso.\n\n"
        "2. Implementation Plan\nPhase one covers discovery and design over six weeks, followed by build and test.\n\n"
        "PRICING AND COMMERCIALS\nA fixed fee per phase with milestone-based payments and a clear change process.\n"
    )
    sections = split_into_sections(text, load_profile())
    assert {"executive_summary", "implementation_plan"} <= set(sections)
    assert any(k.startswith("pricing") for k in sections)
    record = document_to_record("contoso_proposal.md", text.encode(), load_profile(), client_name="Contoso")
    assert record["client_name"] == "Contoso" and record["proposal_sections"]
