from __future__ import annotations

from app.orchestration.orchestrator import ProposalWorkflowOrchestrator


class OrchestrationService:
    def __init__(self, orchestrator: ProposalWorkflowOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or ProposalWorkflowOrchestrator()

    def run_proposal(self, payload: dict, candidate_chunks: list[dict]) -> dict:
        return self.orchestrator.run_proposal_workflow(payload, candidate_chunks)

    def run_revision(self, payload: dict, base_section: dict, candidate_chunks: list[dict]) -> dict:
        return self.orchestrator.run_revision_workflow(payload, base_section, candidate_chunks)

    def run_document_match(self, payload: dict, candidate_chunks: list[dict]) -> dict:
        return self.orchestrator.run_document_match_workflow(payload, candidate_chunks)
