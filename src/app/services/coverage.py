"""Requirement coverage: does a draft actually address each requirement?

Each requirement is compared with every sentence of the draft. It counts as
covered when any of these hold:
- the requirement text appears verbatim,
- most of its content words appear in one sentence (lexical match),
- a sentence embedding is similar enough (semantic match, MiniLM by default).

The embedding model is optional; without it, matching is lexical only.
"""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[a-z0-9][a-z0-9+#.-]*")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into", "will", "must", "shall", "should",
    "our", "your", "their", "are", "all", "any", "each", "have", "has", "been", "able", "provide",
    "provides", "providing", "ensure", "support", "supports", "including", "include", "such", "within",
    "across", "vendor", "solution", "required", "requirement", "requirements", "need", "needs",
}


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _STOP}


def split_sentences(text: str) -> list[str]:
    parts = [p.strip(" -*•\t") for p in _SENTENCES.split(text or "")]
    return [p for p in parts if len(p) > 8]


class CoverageAnalyzer:
    def __init__(self, embedding_service: Any = None, threshold: float = 0.5, lexical_threshold: float = 0.6) -> None:
        self.embedding_service = embedding_service
        self.threshold = threshold
        self.lexical_threshold = lexical_threshold

    def _embed(self, texts: list[str]) -> list[list[float]] | None:
        if self.embedding_service is None or not texts:
            return None
        try:
            return self.embedding_service.encode(texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding model unavailable for coverage (%s); using lexical matching", exc)
            self.embedding_service = None
            return None

    def analyze(self, requirements: list[str], text: str) -> dict[str, Any]:
        requirements = [r for r in (requirements or []) if str(r).strip()]
        if not requirements:
            return {
                "requirement_coverage": {},
                "details": [],
                "missing_items": [],
                "coverage_score": None,
                "method": "none",
            }
        lowered = (text or "").lower()
        sentences = split_sentences(text)
        sentence_words = [_content_words(s) for s in sentences]

        vectors = self._embed(requirements + sentences) if sentences else None
        method = "semantic+lexical" if vectors else "lexical"
        req_vecs = vectors[: len(requirements)] if vectors else []
        sent_vecs = vectors[len(requirements):] if vectors else []

        details = []
        for i, req in enumerate(requirements):
            best_score, best_sentence, how = 0.0, "", "none"
            if req.lower() in lowered:
                best_score, how = 1.0, "exact"
            words = _content_words(req)
            if how == "none" and words:
                for s, sw in zip(sentences, sentence_words):
                    overlap = len(words & sw) / len(words)
                    if overlap > best_score:
                        best_score, best_sentence = overlap, s
                if best_score >= self.lexical_threshold:
                    how = "lexical"
            if how == "none" and req_vecs:
                rv = req_vecs[i]
                sem_best, sem_sentence = 0.0, ""
                for s, sv in zip(sentences, sent_vecs):
                    sim = sum(a * b for a, b in zip(rv, sv))  # vectors are L2-normalized
                    if sim > sem_best:
                        sem_best, sem_sentence = sim, s
                if sem_best >= self.threshold:
                    how = "semantic"
                    best_score, best_sentence = sem_best, sem_sentence
                elif sem_best > best_score:
                    best_score, best_sentence = sem_best, sem_sentence
            covered = how != "none"
            details.append(
                {
                    "requirement": req,
                    "covered": covered,
                    "score": round(float(best_score), 3),
                    "method": how,
                    "evidence": best_sentence[:300],
                }
            )
        covered_count = sum(1 for d in details if d["covered"])
        return {
            "requirement_coverage": {d["requirement"]: d["covered"] for d in details},
            "details": details,
            "missing_items": [d["requirement"] for d in details if not d["covered"]],
            "coverage_score": round(covered_count / len(details), 3),
            "method": method,
        }
