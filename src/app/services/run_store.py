"""Persistence for workflow runs, generated sections, revisions, and token usage.

Writes are best-effort: a database error is logged and the API still returns
the generated result (flagged `persisted: false`).
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.prompts import PROMPT_VERSION
from app.core.access import UNRESTRICTED, AccessScope
from app.core.logging import get_logger
from app.db.models import (
    GeneratedSection,
    GeneratedSectionRevision,
    LLMUsageEvent,
    SectionType,
    WorkflowRun,
    WorkflowStatus,
)
from app.llm.usage import build_report

logger = get_logger(__name__)

_STATUS = {
    "completed": WorkflowStatus.completed,
    "partial": WorkflowStatus.completed,
    "incomplete": WorkflowStatus.failed,
    "failed": WorkflowStatus.failed,
}
_USAGE_FIELDS = (
    "agent", "tool", "section_key", "purpose", "provider", "model", "tier", "prompt_tokens",
    "cached_prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens", "cost_usd",
    "cache_hit", "saved_tokens", "saved_cost_usd", "latency_ms", "status", "error",
)


def _run_labels(run: WorkflowRun) -> tuple[str, str]:
    """(title, client name) for a stored run, from its result, then its request payload."""
    result = run.result_json or {}
    request = result.get("request") or {}
    payload = run.payload_json or {}
    overview = result.get("client_overview") or {}
    title = request.get("title") or payload.get("title") or overview.get("opportunity_name") or ""
    client = request.get("client_name") or payload.get("client_name") or overview.get("client_name") or ""
    return title, client


def _uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


class RunStore:
    """Reads are limited to what `scope` may see; writes record `scope.owner_id` as the owner."""

    def __init__(self, db: Session, scope: AccessScope = UNRESTRICTED) -> None:
        self.db = db
        self.scope = scope

    # ── access ────────────────────────────────────────────────────────
    def _visible_run(self, run_id: uuid.UUID | None) -> WorkflowRun | None:
        """The run if this viewer may see it; None otherwise, so callers answer "not found"."""
        run = self.db.get(WorkflowRun, run_id) if run_id else None
        return run if run is not None and self.scope.allows(run.owner_id) else None

    def _only_mine(self, query, column):
        return query.where(column == self.scope.owner_id) if self.scope.restricted else query

    # ── writes ────────────────────────────────────────────────────────
    def save_workflow(
        self,
        *,
        workflow_id: str,
        workflow_type: str,
        status: str,
        profile: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        sections: list[dict[str, Any]] | None = None,
        usage_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, str]] | None:
        """Persist a run. Returns {section_key: {section_id, revision_id}}, or None on failure."""
        try:
            run = WorkflowRun(
                id=_uuid(workflow_id),
                workflow_type=workflow_type,
                status=_STATUS.get(status, WorkflowStatus.completed),
                profile=profile,
                owner_id=self.scope.owner_id,
                payload_json=payload,
                result_json=result,
                completed_at=datetime.now(timezone.utc),
            )
            self.db.add(run)
            self.db.flush()
            ids: dict[str, dict[str, str]] = {}
            for sec in sections or []:
                if sec.get("error"):
                    continue
                section = GeneratedSection(
                    workflow_run_id=run.id,
                    section_type_id=self._section_type_id(sec["section_key"]),
                    section_key=sec["section_key"],
                )
                self.db.add(section)
                self.db.flush()
                rev = GeneratedSectionRevision(
                    generated_section_id=section.id,
                    revision_number=1,
                    draft_text=sec.get("draft_text", ""),
                    citations_json=sec.get("citations", []),
                    prompt_snapshot_json={"prompt_version": PROMPT_VERSION},
                    generation_metadata_json={
                        "title": sec.get("title"),
                        "model": sec.get("model"),
                        "generation_mode": sec.get("generation_mode"),
                        "cache_hit": sec.get("cache_hit"),
                        "word_count": sec.get("word_count"),
                        "usage": sec.get("usage"),
                        "validation_score": (sec.get("validation") or {}).get("validation_score"),
                    },
                )
                self.db.add(rev)
                self.db.flush()
                section.latest_revision_id = rev.id
                ids[sec["section_key"]] = {"section_id": str(section.id), "revision_id": str(rev.id)}
            if ids and isinstance(result.get("sections"), list):
                stored = copy.deepcopy(result)
                for sec in stored["sections"]:
                    sec.update(ids.get(sec.get("section_key"), {}))
                run.result_json = stored
            self._add_usage(workflow_id, workflow_type, usage_records or [])
            self.db.commit()
            return ids
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Could not persist workflow %s: %s", workflow_id, exc)
            return None

    def save_usage(self, workflow_id: str, workflow_type: str, usage_records: list[dict[str, Any]]) -> bool:
        try:
            self._add_usage(workflow_id, workflow_type, usage_records)
            self.db.commit()
            return True
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Could not persist usage for %s: %s", workflow_id, exc)
            return False

    def save_section_revision(
        self,
        *,
        section_id: str,
        instruction: str,
        revision: dict[str, Any],
        validation: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        try:
            section = self.db.get(GeneratedSection, _uuid(section_id))
            if section is None:
                return None
            latest_number = self.db.execute(
                select(func.max(GeneratedSectionRevision.revision_number)).where(
                    GeneratedSectionRevision.generated_section_id == section.id
                )
            ).scalar() or 0
            rev = GeneratedSectionRevision(
                generated_section_id=section.id,
                revision_number=latest_number + 1,
                base_revision_id=section.latest_revision_id,
                revision_instruction=instruction,
                revision_summary=revision.get("revision_summary"),
                changed_topics_json=revision.get("changed_topics", []),
                preserved_constraints_json=revision.get("preserved_constraints", []),
                draft_text=revision.get("draft_text", ""),
                prompt_snapshot_json={"prompt_version": PROMPT_VERSION},
                generation_metadata_json={
                    "model": revision.get("model"),
                    "cache_hit": revision.get("cache_hit"),
                    "generation_mode": revision.get("generation_mode"),
                    "validation_score": (validation or {}).get("validation_score"),
                },
            )
            self.db.add(rev)
            self.db.flush()
            section.latest_revision_id = rev.id
            self.db.commit()
            return {"revision_id": str(rev.id), "revision_number": rev.revision_number}
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Could not persist revision for section %s: %s", section_id, exc)
            return None

    def _section_type_id(self, code: str) -> uuid.UUID | None:
        row = self.db.execute(select(SectionType.id).where(SectionType.code == code)).scalar_one_or_none()
        return row

    def _add_usage(self, workflow_id: str, workflow_type: str, records: list[dict[str, Any]]) -> None:
        wid = _uuid(workflow_id)
        for rec in records:
            data = {k: rec.get(k) for k in _USAGE_FIELDS}
            data["error"] = (data.get("error") or None) and str(data["error"])[:2000]
            self.db.add(LLMUsageEvent(workflow_id=wid, workflow_type=workflow_type, owner_id=self.scope.owner_id, **{k: v for k, v in data.items() if v is not None}))

    # ── reads ─────────────────────────────────────────────────────────
    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """A stored run; each section carries its latest revision text."""
        run = self._visible_run(_uuid(workflow_id))
        if run is None:
            return None
        result = copy.deepcopy(run.result_json or {})
        latest = self._latest_sections(run.id)
        for sec in result.get("sections") or []:
            current = latest.get(sec.get("section_key"))
            if current:
                sec.update(current)
        return {
            "workflow_id": str(run.id),
            "workflow_type": run.workflow_type,
            "status": run.status.value if run.status else None,
            "profile": run.profile,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "result": result,
        }

    def _latest_sections(self, run_id: uuid.UUID) -> dict[str, dict[str, Any]]:
        rows = self.db.execute(
            select(GeneratedSection, GeneratedSectionRevision)
            .join(GeneratedSectionRevision, GeneratedSectionRevision.id == GeneratedSection.latest_revision_id)
            .where(GeneratedSection.workflow_run_id == run_id)
        ).all()
        return {
            section.section_key: {
                "section_id": str(section.id),
                "revision_id": str(rev.id),
                "revision_number": rev.revision_number,
                "draft_text": rev.draft_text,
                "word_count": len((rev.draft_text or "").split()),
            }
            for section, rev in rows
        }

    def list_workflows(self, *, limit: int = 20, workflow_type: str | None = None) -> list[dict[str, Any]]:
        query = select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(max(1, min(limit, 100)))
        query = self._only_mine(query, WorkflowRun.owner_id)
        if workflow_type:
            query = query.where(WorkflowRun.workflow_type == workflow_type)
        out = []
        for run in self.db.execute(query).scalars():
            result = run.result_json or {}
            totals = (result.get("token_usage") or {}).get("totals") or {}
            title, client_name = _run_labels(run)
            out.append(
                {
                    "workflow_id": str(run.id),
                    "workflow_type": run.workflow_type,
                    "status": result.get("status") or (run.status.value if run.status else None),
                    "profile": run.profile,
                    "title": title,
                    "client_name": client_name,
                    "composite_score": (result.get("scores") or {}).get("composite_score"),
                    "section_count": len([s for s in result.get("sections") or [] if not s.get("error")]),
                    "total_tokens": totals.get("total_tokens", 0),
                    "cost_usd": totals.get("cost_usd", 0.0),
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                }
            )
        return out

    def load_section(self, section_id: str) -> dict[str, Any] | None:
        sid = _uuid(section_id)
        if sid is None:
            return None
        section = self.db.get(GeneratedSection, sid)
        if section is None or self._visible_run(section.workflow_run_id) is None:
            return None
        rev = self.db.get(GeneratedSectionRevision, section.latest_revision_id) if section.latest_revision_id else None
        return {
            "section_id": str(section.id),
            "section_key": section.section_key,
            "workflow_id": str(section.workflow_run_id),
            "draft_text": rev.draft_text if rev else "",
            "revision_id": str(rev.id) if rev else None,
            "revision_number": rev.revision_number if rev else 0,
        }

    def list_section_revisions(self, section_id: str) -> list[dict[str, Any]]:
        sid = _uuid(section_id)
        if sid is None:
            return []
        section = self.db.get(GeneratedSection, sid)
        if section is None or self._visible_run(section.workflow_run_id) is None:
            return []
        rows = self.db.execute(
            select(GeneratedSectionRevision)
            .where(GeneratedSectionRevision.generated_section_id == sid)
            .order_by(GeneratedSectionRevision.revision_number)
        ).scalars()
        return [
            {
                "revision_id": str(r.id),
                "revision_number": r.revision_number,
                "base_revision_id": str(r.base_revision_id) if r.base_revision_id else None,
                "instruction": r.revision_instruction,
                "summary": r.revision_summary,
                "draft_text": r.draft_text,
                "metadata": r.generation_metadata_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def usage_for_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        wid = _uuid(workflow_id)
        if wid is None:
            return None
        query = self._only_mine(
            select(LLMUsageEvent).where(LLMUsageEvent.workflow_id == wid), LLMUsageEvent.owner_id,
        )
        rows = self.db.execute(query.order_by(LLMUsageEvent.created_at)).scalars().all()
        if not rows:
            return None
        return build_report([self._usage_dict(r) for r in rows], workflow_id=workflow_id)

    def usage_summary(self, days: int = 7) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        rows = self.db.execute(
            self._only_mine(select(LLMUsageEvent).where(LLMUsageEvent.created_at >= since), LLMUsageEvent.owner_id)
        ).scalars().all()
        records = [self._usage_dict(r) for r in rows]
        report = build_report(records, include_calls=False)
        by_day: dict[str, list[dict]] = {}
        by_type: dict[str, list[dict]] = {}
        for rec in records:
            by_day.setdefault(rec["created_at"][:10], []).append(rec)
            by_type.setdefault(rec.get("workflow_type") or "unknown", []).append(rec)
        report["by_day"] = [{"day": d, **build_report(v, include_calls=False)["totals"]} for d, v in sorted(by_day.items())]
        report["by_workflow_type"] = [
            {"workflow_type": t, **build_report(v, include_calls=False)["totals"]} for t, v in sorted(by_type.items())
        ]
        report["workflows"] = len({rec["workflow_id"] for rec in records if rec.get("workflow_id")})
        report["since"] = since.isoformat()
        return report

    def usage_by_run(
        self, days: int = 30, limit: int = 12, workflow_type: str | None = "proposal_generation",
    ) -> dict[str, Any]:
        """Tokens per run, split by section, for the most recent runs in the last N days.

        Tokens from calls not tied to one section (planning, requirement extraction, scoring)
        are reported per run as `other_tokens`.
        """
        since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        query = select(LLMUsageEvent).where(
            LLMUsageEvent.created_at >= since, LLMUsageEvent.workflow_id.is_not(None),
        )
        query = self._only_mine(query, LLMUsageEvent.owner_id)
        if workflow_type:
            query = query.where(LLMUsageEvent.workflow_type == workflow_type)
        by_run: dict[str, list[dict[str, Any]]] = {}
        for row in self.db.execute(query).scalars():
            rec = self._usage_dict(row)
            by_run.setdefault(rec["workflow_id"], []).append(rec)

        # Newest first, by when each run started spending.
        recent = sorted(by_run.items(), key=lambda item: min(r["created_at"] for r in item[1]), reverse=True)
        recent = recent[: max(1, min(limit, 50))]
        ids = [rid for rid, _ in recent if _uuid(rid)]
        runs_meta = {
            str(run.id): run
            for run in self.db.execute(select(WorkflowRun).where(WorkflowRun.id.in_([_uuid(i) for i in ids]))).scalars()
        } if ids else {}

        runs = []
        for workflow_id, records in recent:
            report = build_report(records, include_calls=False)
            totals = report["totals"]
            sections = [
                {"section_key": s["section_key"], "total_tokens": s["total_tokens"], "cost_usd": s["cost_usd"]}
                for s in report["by_section"]
            ]
            meta = runs_meta.get(workflow_id)
            title, client_name = _run_labels(meta) if meta else ("", "")
            runs.append({
                "workflow_id": workflow_id,
                "workflow_type": records[0].get("workflow_type"),
                "title": title,
                "client_name": client_name,
                "saved": meta is not None,
                "started_at": min(r["created_at"] for r in records),
                "total_tokens": totals["total_tokens"],
                "cost_usd": totals["cost_usd"],
                "sections": sections,
                "other_tokens": totals["total_tokens"] - sum(s["total_tokens"] for s in sections),
                "other_cost_usd": round(totals["cost_usd"] - sum(s["cost_usd"] for s in sections), 6),
            })
        return {"since": since.isoformat(), "runs": runs}

    @staticmethod
    def _usage_dict(row: LLMUsageEvent) -> dict[str, Any]:
        data = {k: getattr(row, k) for k in _USAGE_FIELDS}
        data["workflow_id"] = str(row.workflow_id) if row.workflow_id else None
        data["workflow_type"] = row.workflow_type
        data["created_at"] = row.created_at.isoformat() if row.created_at else ""
        return data
