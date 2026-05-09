from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService, get_llm_service
from app.services.orchestration_service import OrchestrationService
from app.services.retrieval_service import RetrievalService


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()


def get_retrieval_service(
    db: Session = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> RetrievalService:
    return RetrievalService(db=db, embedding_service=embedding_service)


def get_ingestion_service(
    db: Session = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> IngestionService:
    return IngestionService(db=db, embedding_service=embedding_service)


def get_orchestration_service(
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> OrchestrationService:
    orchestrator = ProposalWorkflowOrchestrator(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )
    return OrchestrationService(orchestrator)
