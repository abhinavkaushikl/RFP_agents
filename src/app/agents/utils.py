from __future__ import annotations

import re


def extract_requirements(text: str) -> list[str]:
    parts = [part.strip(" -") for part in re.split(r"[\n.;]", text) if part.strip()]
    return parts[:8]


def infer_solution_type(text: str) -> str:
    lowered = text.lower()
    if "mttr" in lowered or "incident" in lowered or "alarm" in lowered:
        return "aiops_operations"
    if "observability" in lowered:
        return "aiops_observability"
    return "aiops_general"
