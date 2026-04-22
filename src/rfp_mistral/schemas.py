from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RFPRecord:
    id: str
    client_name: str
    industry: str
    rfp_title: str
    rfp_summary: str
    requirements: list[str] = field(default_factory=list)
    evaluation_criteria: list[str] = field(default_factory=list)
    solution_summary: str = ""
    proposal_sections: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RFPRecord":
        return cls(
            id=str(payload["id"]),
            client_name=str(payload.get("client_name", "")),
            industry=str(payload.get("industry", "")),
            rfp_title=str(payload.get("rfp_title", "")),
            rfp_summary=str(payload.get("rfp_summary", "")),
            requirements=[str(item) for item in payload.get("requirements", [])],
            evaluation_criteria=[
                str(item) for item in payload.get("evaluation_criteria", [])
            ],
            solution_summary=str(payload.get("solution_summary", "")),
            proposal_sections={
                str(key): str(value)
                for key, value in payload.get("proposal_sections", {}).items()
            },
            tags=[str(item) for item in payload.get("tags", [])],
        )


@dataclass
class TrainingExample:
    record_id: str
    prompt: str
    response: str
    target_section: str

    def to_dict(self) -> dict[str, str]:
        return {
            "record_id": self.record_id,
            "prompt": self.prompt,
            "response": self.response,
            "target_section": self.target_section,
            "text": f"{self.prompt}{self.response}",
        }
