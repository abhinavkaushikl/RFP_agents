"""Helpers that coerce model output into clean, bounded values."""
from __future__ import annotations

from typing import Any


def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return " ".join(str(value).split())


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def as_text_list(value: Any, limit: int = 8) -> list[str]:
    return [clean_text(item) for item in as_list(value)[:limit] if clean_text(item)]


def clamp_int(value: Any, minimum: int = 0, maximum: int = 100) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    if maximum == 100 and 0 < number <= 1:
        number *= 100
    return max(minimum, min(maximum, int(round(number))))


def clamp_float(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, round(number, 3)))


def normalize_choice(value: Any, allowed: list[str] | tuple[str, ...], default: str) -> str:
    text = clean_text(value)
    lowered = text.lower()
    for option in allowed:
        if lowered == option.lower():
            return option
    return default
