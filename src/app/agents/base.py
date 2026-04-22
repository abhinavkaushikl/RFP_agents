from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import AgentContext, AgentResult


class PlatformAgent(ABC):
    name: str

    @abstractmethod
    def run(self, payload: dict, context: AgentContext) -> AgentResult:
        raise NotImplementedError
