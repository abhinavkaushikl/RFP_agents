from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services.embedding_service import EmbeddingService


class RetrievalTool:
    name: str = "retrieval_tool"
    description: str = "Retrieve the most relevant proposal chunks for a query using pgvector cosine similarity."

    def __init__(self, db: Session, embedding_service: EmbeddingService) -> None:
        self.db = db
        self.embedding_service = embedding_service

    def invoke(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self.search(
            query=payload["query"],
            section_type=payload.get("section_type"),
            solution_type=payload.get("solution_type"),
            industry=payload.get("industry"),
            top_k=payload.get("top_k", 5),
        )

    def search(
        self,
        query: str,
        section_type: str | None = None,
        solution_type: str | None = None,
        industry: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        query_embedding = self.embedding_service.encode_one(query)
        embedding_literal = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"

        sql = text(
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
            WHERE (CAST(:section_type AS TEXT) IS NULL OR st.code = CAST(:section_type AS TEXT))
              AND (CAST(:solution_type AS TEXT) IS NULL OR slt.code = CAST(:solution_type AS TEXT))
              AND (CAST(:industry AS TEXT) IS NULL OR pd.industry = CAST(:industry AS TEXT))
            ORDER BY cosine_distance ASC
            LIMIT :top_k
            """
        ).bindparams(
            bindparam("q_emb"),
            bindparam("section_type"),
            bindparam("solution_type"),
            bindparam("industry"),
            bindparam("top_k"),
        )

        rows = self.db.execute(
            sql,
            {
                "q_emb": embedding_literal,
                "section_type": section_type,
                "solution_type": solution_type,
                "industry": industry,
                "top_k": top_k,
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
