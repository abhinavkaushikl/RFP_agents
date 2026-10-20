from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


class EmbeddingsUnavailableError(AppError):
    status_code = 503
    code = "embeddings_not_configured"


class EmbeddingService:
    def __init__(self, model_name: str | None = None) -> None:
        settings = get_settings()
        self.provider = settings.embedding_provider
        self.model_name = model_name or settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._model: Any = None

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                # Imported lazily so serverless deployments without torch can still boot.
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingsUnavailableError(
                    "Local embeddings need sentence-transformers. Install it, or set "
                    "RFP_EMBEDDING_PROVIDER=remote with RFP_EMBEDDING_API_URL and RFP_EMBEDDING_API_KEY."
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode_remote(self, texts: list[str]) -> list[list[float]]:
        settings = get_settings()
        if not settings.embedding_api_url or settings.embedding_api_key is None:
            raise EmbeddingsUnavailableError("Set RFP_EMBEDDING_API_URL and RFP_EMBEDDING_API_KEY for remote embeddings.")
        resp = httpx.post(
            settings.embedding_api_url,
            headers={"Authorization": f"Bearer {settings.embedding_api_key.get_secret_value()}"},
            json={"model": self.model_name, "input": texts, "dimensions": self.dimensions},
            timeout=60,
        )
        resp.raise_for_status()
        rows = sorted(resp.json()["data"], key=lambda row: row["index"])
        vectors = [row["embedding"] for row in rows]
        if vectors and len(vectors[0]) != self.dimensions:
            raise EmbeddingsUnavailableError(
                f"The embeddings API returned {len(vectors[0])} dimensions; the database expects {self.dimensions}."
            )
        return vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.provider == "remote":
            return self._encode_remote(texts)
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [vec.tolist() for vec in vectors]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
