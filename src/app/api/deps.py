from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.security import SESSION_COOKIE
from app.core.access import UNRESTRICTED, AccessScope
from app.core.auth_crypto import read_session
from app.core.config import get_settings
from app.db.session import get_db as _get_db
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService, get_llm_service
from app.services.orchestration_service import OrchestrationService
from app.services.retrieval_service import RetrievalService
from app.services.run_store import RunStore


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()


def get_scope(request: Request, db: Session = Depends(get_db)) -> AccessScope:
    """Signed-in members are restricted to their own runs; admins, API keys and no-auth use are not."""
    user_id = read_session(request.cookies.get(SESSION_COOKIE))
    if not user_id:
        return UNRESTRICTED
    try:
        owner = uuid.UUID(user_id)
    except ValueError:
        return UNRESTRICTED
    admins = get_settings().admin_email_list
    if admins:
        from app.db.models import User

        user = db.get(User, owner)
        if user is not None and user.email.lower() in admins:
            return AccessScope(owner_id=owner, restricted=False)
    return AccessScope(owner_id=owner, restricted=True)


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


def get_run_store(db: Session = Depends(get_db), scope: AccessScope = Depends(get_scope)) -> RunStore:
    return RunStore(db, scope)


def get_orchestration_service(
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    run_store: RunStore = Depends(get_run_store),
) -> OrchestrationService:
    orchestrator = ProposalWorkflowOrchestrator(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
        embedding_service=embedding_service,
        run_store=run_store if get_settings().persist_runs else None,
    )
    return OrchestrationService(orchestrator)
