from __future__ import annotations


def cost_usd(
    pricing: dict[str, dict[str, float]],
    model: str,
    *,
    prompt_tokens: int,
    cached_prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimated cost of one call in USD. Prices are per 1M tokens."""
    rates = pricing.get(model) or {}
    if not rates:
        return 0.0
    input_rate = rates.get("input", 0.0)
    cached_rate = rates.get("cached_input", input_rate)
    output_rate = rates.get("output", 0.0)
    cached = min(max(cached_prompt_tokens, 0), max(prompt_tokens, 0))
    uncached = max(prompt_tokens - cached, 0)
    total = uncached * input_rate + cached * cached_rate + max(completion_tokens, 0) * output_rate
    return round(total / 1_000_000, 8)
