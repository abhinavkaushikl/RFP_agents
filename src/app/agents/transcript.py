"""Shared prompt layout for the four transcript-analysis agents.

All four send the same system message, then the transcript, then their own task.
That keeps the start of every request identical, so Groq's prompt cache can
reuse the transcript tokens across agents that run on the same model.
"""
from __future__ import annotations

MAX_TRANSCRIPT_CHARS = 60_000

TRANSCRIPT_SYSTEM = (
    "You analyze business conversations (meeting transcripts, call notes, email threads, and "
    "opportunity documents) for a proposal and sales team. Ground every statement in the text. "
    "Never invent names, roles, dates, figures, budgets, or commitments. When evidence is partial, "
    "infer conservatively and say so through lower confidence. Return only the JSON requested."
)


def transcript_messages(transcript: str, task: str) -> list[dict[str, str]]:
    text = (transcript or "")[:MAX_TRANSCRIPT_CHARS]
    return [
        {"role": "system", "content": TRANSCRIPT_SYSTEM},
        {"role": "user", "content": f"TRANSCRIPT:\n<<<\n{text}\n>>>\n\nTASK:\n{task}"},
    ]
