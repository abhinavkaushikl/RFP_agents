from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentContext:
    workflow_id: str
    request_id: str | None = None
    proposal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    agent_name: str
    output: dict[str, Any]
    summary: str
    confidence: float = 0.0


@dataclass(slots=True)
class RetrievalCandidate:
    chunk_id: str
    score: float
    section_key: str
    proposal_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
