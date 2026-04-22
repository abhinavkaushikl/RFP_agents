from app.ingestion.pipeline import chunk_section_text, ingest_historical_records, normalize_historical_record


def test_normalize_historical_record_preserves_solution_type() -> None:
    normalized = normalize_historical_record(
        {
            "id": "1",
            "title": "Proposal",
            "client_name": "Client A",
            "solutionType": "aiops_operations",
            "proposal_sections": {"executive_summary": "Summary"},
        },
        "source-a",
    )

    assert normalized["solution_type"] == "aiops_operations"
    assert normalized["sections"]["executive_summary"] == "Summary"


def test_chunk_section_text_generates_hashes() -> None:
    chunks = chunk_section_text("executive_summary", "A" * 700)

    assert len(chunks) >= 2
    assert all(chunk["content_hash"] for chunk in chunks)


def test_ingest_historical_records_returns_chunk_report() -> None:
    result = ingest_historical_records(
        [
            {
                "id": "2",
                "title": "Proposal 2",
                "proposal_sections": {"implementation_plan": "Phased rollout across all domains."},
            }
        ],
        "source-b",
    )

    assert result["ingested_count"] == 1
    assert result["chunk_count"] >= 1
