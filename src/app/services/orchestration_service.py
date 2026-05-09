from __future__ import annotations

from app.orchestration.orchestrator import ProposalWorkflowOrchestrator


class OrchestrationService:
    def __init__(self, orchestrator: ProposalWorkflowOrchestrator) -> None:
        self.orchestrator = orchestrator

    def run_proposal(self, payload: dict) -> dict:
        return self.orchestrator.run_proposal_workflow(payload)

    def run_revision(self, payload: dict, base_section: dict) -> dict:
        return self.orchestrator.run_revision_workflow(payload, base_section)

    def run_document_match(self, payload: dict) -> dict:
        return self.orchestrator.run_document_match_workflow(payload)

    def run_market_research(self, payload: dict) -> dict:
        return self.orchestrator.run_market_research_workflow(payload)

    def run_intent_detection(self, payload: dict) -> dict:
        return self.orchestrator.run_intent_detection_workflow(payload)
