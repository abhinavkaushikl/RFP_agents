from __future__ import annotations

from functools import lru_cache

from app.ingestion.pipeline import ingest_historical_records
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
from app.services.ingestion_service import IngestionService
from app.services.orchestration_service import OrchestrationService
from app.services.retrieval_service import RetrievalService


@lru_cache
def get_orchestrator() -> ProposalWorkflowOrchestrator:
    return ProposalWorkflowOrchestrator()


@lru_cache
def get_orchestration_service() -> OrchestrationService:
    return OrchestrationService(get_orchestrator())


@lru_cache
def get_ingestion_service() -> IngestionService:
    return IngestionService()


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


@lru_cache
def get_chunk_store() -> list[dict]:
    seed = ingest_historical_records(
        [
            {
                "id": "seed-001",
                "title": "AIOps Transformation for Multi-Vendor Networks",
                "client_name": "Reliance Jio",
                "industry": "Telecommunications",
                "solutionType": "aiops_operations",
                "proposal_sections": {
                    "executive_summary": "We reduce MTTR through event correlation, workflow automation, and vendor-agnostic observability.",
                    "implementation_plan": "A phased rollout across Nokia, Huawei, and Ericsson domains reduces risk and accelerates measurable operations gains.",
                    "pricing_notes": "Commercials are aligned to phased onboarding and automation milestones.",
                },
            }
        ],
        source_name="seed",
    )
    return seed["chunks"]
