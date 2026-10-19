from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_run_store
from app.api.security import require_api_key
from app.core.errors import NotFoundError
from app.services.run_store import RunStore

router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[Depends(require_api_key)])


@router.get("/workflows/{workflow_id}")
def workflow_usage(workflow_id: str, store: RunStore = Depends(get_run_store)) -> dict:
    """Token and cost report for one workflow run, by agent, tool, section, and model."""
    report = store.usage_for_workflow(workflow_id)
    if report is None:
        raise NotFoundError(f"No usage recorded for workflow {workflow_id}")
    return report


@router.get("/summary")
def usage_summary(days: int = Query(7, ge=1, le=365), store: RunStore = Depends(get_run_store)) -> dict:
    """Aggregate token and cost usage over the last N days."""
    return store.usage_summary(days)
