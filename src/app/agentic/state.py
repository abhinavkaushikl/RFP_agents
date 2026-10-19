"""Workflow state for the agentic runtime.

A single mutable container the runner threads through every phase:
    pick_intent → make_plan → execute → (replan|continue) → decide_done

Tools read earlier `results` to fill in missing args, so the supervisor's plan
doesn't have to plumb every field by hand.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.agentic.events import emit
from app.llm.usage import RunUsage


@dataclass
class WorkflowState:
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent: str | None = None
    intent_hint: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    budget: int = 12
    steps_taken: int = 0
    replans: int = 0
    max_replans: int = 2
    done: bool = False
    final_summary: str = ""
    last_error: str | None = None
    warnings: list[str] = field(default_factory=list)
    usage: RunUsage | None = None

    @property
    def profile(self) -> str | None:
        return self.payload.get("profile")

    def add_trace(self, **kwargs: Any) -> None:
        self.trace.append(kwargs)
        emit("trace", workflow_id=self.workflow_id, entry=kwargs)

    def tool_summaries(self) -> list[str]:
        return [f"{t['tool']}: {t.get('summary', '')}" for t in self.trace if t.get("type") == "tool_call"]

    def failed_tools(self) -> list[str]:
        return [t["tool"] for t in self.trace if t.get("type") == "tool_call" and not t.get("ok")]

    def get_result(self, tool_name: str, key: str | None = None, default: Any = None) -> Any:
        entry = self.results.get(tool_name)
        if not entry or not entry.get("ok"):
            return default
        output = entry.get("output", {}) if isinstance(entry, dict) else {}
        if key is None:
            return output
        return output.get(key, default)

    def usage_report(self, include_calls: bool = True) -> dict[str, Any]:
        if self.usage is None:
            return {"workflow_id": self.workflow_id, "totals": {}, "by_agent": [], "by_tool": [],
                    "by_section": [], "by_model": [], "calls": []}
        return self.usage.report(include_calls=include_calls)
