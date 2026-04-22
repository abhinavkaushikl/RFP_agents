from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class ProposalRetriever:
    def __init__(self, index_dir: str | Path):
        index_dir = Path(index_dir)
        with (index_dir / "manifest.json").open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        with (index_dir / "metadata.jsonl").open("r", encoding="utf-8") as handle:
            self.metadata = [json.loads(line) for line in handle if line.strip()]

        self.model = SentenceTransformer(manifest["embedding_model"])
        self.index = faiss.read_index(str(index_dir / "proposal.index"))

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        embedding = self.model.encode([query], normalize_embeddings=True)
        scores, indices = self.index.search(np.asarray(embedding, dtype=np.float32), top_k)
        results: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            item = dict(self.metadata[idx])
            item["retrieval_score"] = float(score)
            results.append(item)
        return results

