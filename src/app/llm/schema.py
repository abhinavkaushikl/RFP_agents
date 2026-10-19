"""Builders for strict JSON Schemas (Groq structured outputs, strict mode).

Strict mode requires every property to be listed in `required` and
`additionalProperties: false` on every object; these helpers enforce both.
"""
from __future__ import annotations

from typing import Any

STR: dict[str, Any] = {"type": "string"}
NUM: dict[str, Any] = {"type": "number"}
INT: dict[str, Any] = {"type": "integer"}
BOOL: dict[str, Any] = {"type": "boolean"}


def obj(**properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def enum(*values: str) -> dict[str, Any]:
    unique = list(dict.fromkeys(v for v in values if v))
    return {"type": "string", "enum": unique} if unique else dict(STR)
