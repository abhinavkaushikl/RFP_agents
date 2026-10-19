"""Check the Groq setup: one call per model tier, then a repeat to show prompt caching.

    PYTHONPATH=src python3 scripts/smoke_groq.py

Uses a few hundred tokens. Prints model, token usage (including cached prompt
tokens), estimated cost, and the rate-limit headers Groq returned.
"""
from __future__ import annotations

import sys

from app.core.config import get_settings
from app.llm.errors import LLMServiceError
from app.llm.service import LLMService
from app.llm.usage import cache_policy, usage_run

# Long enough to exceed the provider's minimum cacheable prefix.
STATIC_SYSTEM = "You are a concise assistant for a proposal team. " + " ".join(
    f"Rule {i}: keep answers factual, short, and free of filler." for i in range(1, 60)
)


def main() -> int:
    settings = get_settings()
    if not settings.groq_key():
        print("RFP_GROQ_API_KEY is not set. Add it to .env first.", file=sys.stderr)
        return 2
    service = LLMService()
    print(f"Organization (from config): {settings.groq_org_id or '(not set)'}")
    with usage_run("smoke") as run, cache_policy("off"):
        try:
            for agent in ("supervisor", "generation"):
                tier, model = service.route(agent)
                for attempt in (1, 2):
                    result = service.complete(
                        agent=agent, system=STATIC_SYSTEM, prompt="Reply with the single word: ready",
                        max_tokens=400, purpose=f"smoke-{attempt}",
                    )
                    u = result.usage
                    print(f"{tier:<8} {model:<22} call {attempt}: '{result.text[:40]}' prompt={u.prompt_tokens} "
                          f"cached={u.cached_prompt_tokens} completion={u.completion_tokens} "
                          f"(reasoning {u.reasoning_tokens}) cost=${u.cost_usd:.6f} {u.latency_ms}ms")
        except LLMServiceError as exc:
            print(f"Groq call failed: {exc}", file=sys.stderr)
            return 1
    totals = run.report()["totals"]
    print(f"Total: {totals['total_tokens']} tokens, ${totals['cost_usd']:.6f}, prompt cache rate {totals['prompt_cache_rate']:.0%}")
    print("A non-zero 'cached' value on call 2 confirms Groq prompt caching is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
