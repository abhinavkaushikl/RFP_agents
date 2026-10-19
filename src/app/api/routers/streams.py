"""Server-Sent Events versions of the long-running workflows.

Each endpoint returns `text/event-stream` with:
    event: trace            supervisor and tool steps as they happen
    event: sections_planned the sections about to be drafted
    event: section_started / section_done
    event: result           the same body the non-streaming endpoint returns
    event: error            {status, code, message, retry_after}
The run happens in a worker thread with its own database session, so it is not
tied to the request's dependency lifetime.
"""
from __future__ import annotations

import contextvars
import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.agentic.events import event_sink
from app.api.security import rate_limit_requests, require_api_key
from app.core.config import get_settings
from app.core.errors import describe_exception
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.orchestration.orchestrator import ProposalWorkflowOrchestrator
from app.schemas.api import DocumentMatchRequest, IntentDetectionRequest, WorkflowRunRequest
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.retrieval_service import RetrievalService
from app.services.run_store import RunStore

logger = get_logger(__name__)
router = APIRouter(tags=["streams"], dependencies=[Depends(require_api_key), Depends(rate_limit_requests)])

_KEEPALIVE_S = 15
_DONE = object()

OrchestratorFactory = Callable[[Any], ProposalWorkflowOrchestrator]


def _default_factory(llm: LLMService, embedding: EmbeddingService) -> OrchestratorFactory:
    def build(db) -> ProposalWorkflowOrchestrator:
        return ProposalWorkflowOrchestrator(
            retrieval_service=RetrievalService(db=db, embedding_service=embedding),
            llm_service=llm,
            embedding_service=embedding,
            run_store=RunStore(db) if get_settings().persist_runs else None,
        )

    return build


def get_orchestrator_factory(
    llm: LLMService = Depends(get_llm_service),
    embedding: EmbeddingService = Depends(get_embedding_service),
) -> OrchestratorFactory:
    return _default_factory(llm, embedding)


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data), default=str)}\n\n"


def stream_run(factory: OrchestratorFactory, run: Callable[[ProposalWorkflowOrchestrator], dict]) -> StreamingResponse:
    events: queue.Queue = queue.Queue()

    def worker() -> None:
        db = SessionLocal()
        try:
            orchestrator = factory(db)
            with event_sink(events.put):
                result = run(orchestrator)
            events.put({"type": "result", "data": result})
        except Exception as exc:  # noqa: BLE001
            status, code, message, retry_after = describe_exception(exc)
            if status >= 500 and code == "internal_error":
                logger.exception("Streamed workflow failed: %s", exc)
            events.put({"type": "error", "status": status, "code": code, "message": message, "retry_after": retry_after})
        finally:
            db.close()
            events.put(_DONE)

    context = contextvars.copy_context()
    threading.Thread(target=context.run, args=(worker,), daemon=True, name="workflow-stream").start()

    def body() -> Iterator[str]:
        yield ": connected\n\n"
        while True:
            try:
                item = events.get(timeout=_KEEPALIVE_S)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if item is _DONE:
                break
            kind = item.pop("type", "message")
            yield _sse(kind, item.get("data", item) if kind == "result" else item)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/workflow-runs/stream")
def stream_workflow_run(payload: WorkflowRunRequest, factory: OrchestratorFactory = Depends(get_orchestrator_factory)):
    body = payload.model_dump()
    return stream_run(factory, lambda orch: orch.run_proposal_workflow(body))


@router.post("/intent-detection-runs/stream")
def stream_intent_detection(payload: IntentDetectionRequest, factory: OrchestratorFactory = Depends(get_orchestrator_factory)):
    body = payload.model_dump()
    return stream_run(factory, lambda orch: orch.run_intent_detection_workflow(body))


@router.post("/document-match-runs/stream")
def stream_document_match(payload: DocumentMatchRequest, factory: OrchestratorFactory = Depends(get_orchestrator_factory)):
    body = payload.model_dump()
    return stream_run(factory, lambda orch: orch.run_document_match_workflow(body))
