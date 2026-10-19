"""Token accounting for agentic runs.

A run opens `usage_run(workflow_id)`; every LLM call made inside it (including
from worker threads started with `contextvars.copy_context()`) is appended to
that run. Tools add `usage_tags(tool=..., section_key=...)` so the report can
break consumption down by agent, tool, section, and model.
"""
from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.llm.types import UsageRecord

CACHE_POLICIES = ("use", "refresh", "off")

_run_var: ContextVar["RunUsage | None"] = ContextVar("llm_usage_run", default=None)
_tags_var: ContextVar[dict[str, Any]] = ContextVar("llm_usage_tags", default={})
_cache_policy_var: ContextVar[str] = ContextVar("llm_cache_policy", default="use")

_METRICS = (
    "prompt_tokens",
    "cached_prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "total_tokens",
    "saved_tokens",
)


class RunUsage:
    def __init__(self, workflow_id: str | None = None) -> None:
        self.workflow_id = workflow_id
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()

    def add(self, record: UsageRecord) -> None:
        with self._lock:
            self._records.append(record)

    @property
    def records(self) -> list[UsageRecord]:
        with self._lock:
            return list(self._records)

    def totals(self) -> dict[str, Any]:
        return _aggregate(r.to_dict() for r in self.records)

    def report(self, *, include_calls: bool = True) -> dict[str, Any]:
        return build_report(
            [r.to_dict() for r in self.records],
            workflow_id=self.workflow_id,
            include_calls=include_calls,
        )


@contextmanager
def usage_run(workflow_id: str | None = None) -> Iterator[RunUsage]:
    run = RunUsage(workflow_id)
    token = _run_var.set(run)
    try:
        yield run
    finally:
        _run_var.reset(token)


@contextmanager
def usage_tags(**tags: Any) -> Iterator[None]:
    merged = {**_tags_var.get(), **{k: v for k, v in tags.items() if v is not None}}
    token = _tags_var.set(merged)
    try:
        yield
    finally:
        _tags_var.reset(token)


@contextmanager
def cache_policy(policy: str | None) -> Iterator[None]:
    value = policy if policy in CACHE_POLICIES else "use"
    token = _cache_policy_var.set(value)
    try:
        yield
    finally:
        _cache_policy_var.reset(token)


def current_run() -> RunUsage | None:
    return _run_var.get()


def current_tags() -> dict[str, Any]:
    return dict(_tags_var.get())


def current_cache_policy() -> str:
    return _cache_policy_var.get()


def record_usage(record: UsageRecord) -> None:
    run = _run_var.get()
    if run is not None:
        if record.workflow_id is None:
            record.workflow_id = run.workflow_id
        run.add(record)


# ── reporting ──────────────────────────────────────────────────────────
def _aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {m: 0 for m in _METRICS}
    out.update(calls=0, model_calls=0, cache_hits=0, errors=0, cost_usd=0.0, saved_cost_usd=0.0, latency_ms=0)
    for rec in records:
        out["calls"] += 1
        if rec.get("status") != "ok":
            out["errors"] += 1
        if rec.get("cache_hit"):
            out["cache_hits"] += 1
        elif rec.get("status") == "ok":
            out["model_calls"] += 1
        for metric in _METRICS:
            out[metric] += int(rec.get(metric) or 0)
        out["cost_usd"] += float(rec.get("cost_usd") or 0.0)
        out["saved_cost_usd"] += float(rec.get("saved_cost_usd") or 0.0)
        out["latency_ms"] += int(rec.get("latency_ms") or 0)
    out["cost_usd"] = round(out["cost_usd"], 6)
    out["saved_cost_usd"] = round(out["saved_cost_usd"], 6)
    prompt = out["prompt_tokens"]
    out["prompt_cache_rate"] = round(out["cached_prompt_tokens"] / prompt, 4) if prompt else 0.0
    return out


def _group(records: list[dict[str, Any]], key: str, label: str | None = None) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        value = rec.get(key)
        if value in (None, ""):
            continue
        buckets.setdefault(str(value), []).append(rec)
    rows = []
    for value, recs in buckets.items():
        row = {label or key: value, **_aggregate(recs)}
        if key == "model":
            row["tier"] = recs[0].get("tier")
        rows.append(row)
    rows.sort(key=lambda r: (-r["total_tokens"], -r["saved_tokens"], str(r[label or key])))
    return rows


def build_report(
    records: list[dict[str, Any]],
    *,
    workflow_id: str | None = None,
    include_calls: bool = True,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "workflow_id": workflow_id,
        "totals": _aggregate(records),
        "by_agent": _group(records, "agent"),
        "by_tool": _group(records, "tool"),
        "by_section": _group(records, "section_key"),
        "by_model": _group(records, "model"),
    }
    if include_calls:
        report["calls"] = records
    return report


__all__ = [
    "CACHE_POLICIES",
    "RunUsage",
    "build_report",
    "cache_policy",
    "current_cache_policy",
    "current_run",
    "current_tags",
    "record_usage",
    "usage_run",
    "usage_tags",
]
