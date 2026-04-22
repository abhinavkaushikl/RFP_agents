from app.ingestion.pipeline import ingest_historical_records
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator


def _seed_chunks() -> list[dict]:
    result = ingest_historical_records(
        [
            {
                "id": "hist-1",
                "title": "AIOps rollout",
                "client_name": "Jio",
                "solutionType": "aiops_operations",
                "proposal_sections": {
                    "executive_summary": "Reduce MTTR with automation and observability.",
                    "implementation_plan": "Deliver phased rollout for Nokia Huawei Ericsson operations.",
                },
            }
        ],
        source_name="tests",
    )
    return result["chunks"]


def test_proposal_workflow_generates_sections() -> None:
    orchestrator = ProposalWorkflowOrchestrator()
    result = orchestrator.run_proposal_workflow(
        {
            "request_text": "Create a proposal for AIOps operations to reduce MTTR across Nokia Huawei Ericsson domains.",
            "title": "AIOps request",
            "solution_type": "aiops_operations",
        },
        _seed_chunks(),
    )

    assert result["status"] == "completed"
    assert result["sections"]
    assert any(section["section_key"] == "implementation_plan" for section in result["sections"])
    assert result["scores"]["composite_score"] >= 0


def test_revision_workflow_appends_instruction() -> None:
    orchestrator = ProposalWorkflowOrchestrator()
    result = orchestrator.run_revision_workflow(
        {
            "instruction": "Add phased rollout and 5 month MTTR target.",
            "requirements": ["phased rollout", "5 month MTTR target"],
            "solution_type": "aiops_operations",
        },
        {
            "section_key": "implementation_plan",
            "draft_text": "Current implementation plan.",
        },
        _seed_chunks(),
    )

    assert result["status"] == "completed"
    assert "Revision Applied" in result["revision"]["draft_text"]
    assert result["validation"]["validation_score"] >= 0
