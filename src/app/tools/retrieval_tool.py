from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import Text

from app.services.embedding_service import EmbeddingService

_SQL = text(
    """
    SELECT
        ec.id::text AS id,
        ec.chunk_text AS content,
        ec.chunk_index,
        ec.metadata_json,
        COALESCE(st.code, '') AS section_key,
        COALESCE(slt.code, '') AS solution_type,
        COALESCE(pd.external_id, pd.id::text) AS proposal_id,
        pd.industry AS industry,
        (ec.embedding <=> CAST(:q_emb AS vector)) AS cosine_distance
    FROM embedding_chunks ec
    LEFT JOIN section_types st ON st.id = ec.section_type_id
    LEFT JOIN solution_types slt ON slt.id = ec.solution_type_id
    LEFT JOIN proposal_documents pd ON pd.id = ec.proposal_document_id
    WHERE ec.embedding IS NOT NULL
      AND (CAST(:section_codes AS TEXT[]) IS NULL OR st.code = ANY(CAST(:section_codes AS TEXT[])))
      AND (CAST(:solution_type AS TEXT) IS NULL OR slt.code = CAST(:solution_type AS TEXT))
      AND (CAST(:industries AS TEXT[]) IS NULL OR lower(pd.industry) = ANY(CAST(:industries AS TEXT[])))
    ORDER BY cosine_distance ASC
    LIMIT :top_k
    """
).bindparams(
    bindparam("q_emb"),
    bindparam("section_codes", type_=ARRAY(Text)),
    bindparam("solution_type"),
    bindparam("industries", type_=ARRAY(Text)),
    bindparam("top_k"),
)


class RetrievalTool:
    """pgvector cosine search over embedded proposal chunks."""

    def __init__(self, db, embedding_service: EmbeddingService) -> None:
        self.db = db
        self.embedding_service = embedding_service

    def search(
        self,
        query: str,
        section_codes: list[str] | None = None,
        solution_type: str | None = None,
        industries: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        query_embedding = self.embedding_service.encode_one(query)
        embedding_literal = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"
        rows = self.db.execute(
            _SQL,
            {
                "q_emb": embedding_literal,
                "section_codes": section_codes or None,
                "solution_type": solution_type or None,
                "industries": [i.lower() for i in industries] if industries else None,
                "top_k": int(top_k),
            },
        ).mappings().all()
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "section_key": row["section_key"],
                "solution_type": row["solution_type"],
                "proposal_id": row["proposal_id"],
                "industry": row["industry"],
                "metadata": dict(row["metadata_json"] or {}),
                "score": max(0.0, min(1.0, 1.0 - float(row["cosine_distance"]))),
            }
            for row in rows
        ]
