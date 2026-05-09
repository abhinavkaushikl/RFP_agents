from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ActorType,
    EmbeddingChunk,
    ProposalDocument,
    ProposalDocumentRevision,
    ProposalSection,
    ProposalSectionRevision,
    SectionType,
    SolutionType,
    SourceType,
)
from app.ingestion.pipeline import ingest_historical_records
from app.services.embedding_service import EmbeddingService


class IngestionService:
    def __init__(self, db: Session, embedding_service: EmbeddingService) -> None:
        self.db = db
        self.embedding_service = embedding_service
        self.settings = get_settings()

    def _get_or_create_solution_type(self, code: str) -> SolutionType:
        existing = self.db.execute(
            select(SolutionType).where(SolutionType.code == code)
        ).scalar_one_or_none()
        if existing:
            return existing
        sol = SolutionType(code=code, name=code.replace("_", " ").title())
        self.db.add(sol)
        self.db.flush()
        return sol

    def _get_or_create_section_type(self, code: str) -> SectionType:
        existing = self.db.execute(
            select(SectionType).where(SectionType.code == code)
        ).scalar_one_or_none()
        if existing:
            return existing
        sec = SectionType(code=code, name=code.replace("_", " ").title())
        self.db.add(sec)
        self.db.flush()
        return sec

    def ingest_historical(self, records: list[dict], source_name: str) -> dict[str, Any]:
        result = ingest_historical_records(
            records, source_name, embedding_service=self.embedding_service
        )

        chunks_by_proposal: dict[str, list[dict]] = {}
        for chunk in result["chunks"]:
            chunks_by_proposal.setdefault(chunk["proposal_id"], []).append(chunk)

        persisted_chunk_count = 0

        for normalized in result["normalized_records"]:
            external_id = normalized["external_id"] or str(uuid.uuid4())
            solution_type = self._get_or_create_solution_type(normalized["solution_type"])

            proposal_doc = ProposalDocument(
                external_id=external_id,
                source_type=SourceType.historical,
                client_name=normalized["client_name"],
                industry=normalized["industry"],
                solution_type_id=solution_type.id,
                title=normalized["title"],
                status="active",
            )
            self.db.add(proposal_doc)
            self.db.flush()

            doc_revision = ProposalDocumentRevision(
                proposal_document_id=proposal_doc.id,
                revision_number=1,
                revision_reason="initial_ingest",
                document_json=normalized["document_json"],
                metadata_json={"source_name": source_name},
                created_by_type=ActorType.system,
                created_by_id=source_name,
            )
            self.db.add(doc_revision)
            self.db.flush()
            proposal_doc.latest_revision_id = doc_revision.id

            section_revisions: dict[str, ProposalSectionRevision] = {}
            for section_key, content in normalized["sections"].items():
                section_type = self._get_or_create_section_type(section_key)
                section = ProposalSection(
                    proposal_document_id=proposal_doc.id,
                    section_type_id=section_type.id,
                    section_key=section_key,
                )
                self.db.add(section)
                self.db.flush()

                section_rev = ProposalSectionRevision(
                    proposal_section_id=section.id,
                    proposal_document_revision_id=doc_revision.id,
                    revision_number=1,
                    content_text=str(content),
                    created_by_type=ActorType.system,
                    created_by_id=source_name,
                )
                self.db.add(section_rev)
                self.db.flush()
                section.latest_revision_id = section_rev.id
                section_revisions[section_key] = section_rev

            proposal_chunks = chunks_by_proposal.get(external_id, [])
            for chunk in proposal_chunks:
                section_key = chunk["section_key"]
                section_rev = section_revisions.get(section_key)
                if section_rev is None:
                    continue
                section_type = self._get_or_create_section_type(section_key)

                self.db.add(
                    EmbeddingChunk(
                        proposal_document_id=proposal_doc.id,
                        proposal_section_revision_id=section_rev.id,
                        solution_type_id=solution_type.id,
                        section_type_id=section_type.id,
                        chunk_index=chunk["chunk_index"],
                        chunk_text=chunk["content"],
                        token_count=chunk["token_count"],
                        embedding_model=self.embedding_service.model_name,
                        content_hash=chunk["content_hash"],
                        metadata_json={
                            "industry": normalized["industry"],
                            "client_name": normalized["client_name"],
                            "external_id": external_id,
                        },
                        embedding=chunk.get("embedding"),
                    )
                )
                persisted_chunk_count += 1

        self.db.commit()

        return {
            "ingested_count": result["ingested_count"],
            "section_count": result["section_count"],
            "chunk_count": persisted_chunk_count,
            "source_name": source_name,
        }
