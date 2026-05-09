from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


class EmbeddingService:
    def __init__(self, model_name: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [vec.tolist() for vec in vectors]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
