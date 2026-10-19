from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.domain.profile import DomainProfile, load_profile
from app.ingestion.pipeline import ingest_historical_records
from app.services.embedding_service import EmbeddingService


class IngestionService:
    def __init__(self, db: Session, embedding_service: EmbeddingService) -> None:
        self.db = db
        self.embedding_service = embedding_service

    def _solution_type(self, code: str) -> SolutionType:
        existing = self.db.execute(select(SolutionType).where(SolutionType.code == code)).scalar_one_or_none()
        if existing:
            return existing
        sol = SolutionType(code=code, name=code.replace("_", " ").title())
        self.db.add(sol)
        self.db.flush()
        return sol

    def _section_type(self, code: str, profile: DomainProfile) -> SectionType:
        existing = self.db.execute(select(SectionType).where(SectionType.code == code)).scalar_one_or_none()
        if existing:
            return existing
        sec = SectionType(code=code, name=profile.section_title(code))
        self.db.add(sec)
        self.db.flush()
        return sec

    def _exists(self, external_id: str | None, source_name: str) -> bool:
        if not external_id:
            return False
        rows = self.db.execute(
            select(ProposalDocument.id, ProposalDocument.latest_revision_id).where(ProposalDocument.external_id == external_id)
        ).all()
        for _, rev_id in rows:
            rev = self.db.get(ProposalDocumentRevision, rev_id) if rev_id else None
            if rev is None or (rev.metadata_json or {}).get("source_name") == source_name:
                return True
        return False

    def ingest_historical(self, records: list[dict], source_name: str, profile_name: str | None = None) -> dict[str, Any]:
        profile = load_profile(profile_name)
        fresh, duplicates = [], 0
        for record in records:
            if isinstance(record, dict) and self._exists(str(record.get("id") or "") or None, source_name):
                duplicates += 1
                continue
            fresh.append(record)

        result = ingest_historical_records(fresh, source_name, embedding_service=self.embedding_service, profile=profile)
        chunks_by_proposal: dict[str, list[dict]] = {}
        for chunk in result["chunks"]:
            chunks_by_proposal.setdefault(chunk["proposal_id"], []).append(chunk)

        persisted_chunks = 0
        try:
            for normalized in result["normalized_records"]:
                solution_type = self._solution_type(normalized["solution_type"])
                doc = ProposalDocument(
                    external_id=normalized["external_id"] or normalized["proposal_key"],
                    source_type=SourceType.historical,
                    client_name=normalized["client_name"],
                    industry=normalized["industry"],
                    solution_type_id=solution_type.id,
                    title=str(normalized["title"])[:255],
                    status="active",
                )
                self.db.add(doc)
                self.db.flush()
                doc_rev = ProposalDocumentRevision(
                    proposal_document_id=doc.id,
                    revision_number=1,
                    revision_reason="initial_ingest",
                    document_json=normalized["document_json"],
                    metadata_json={"source_name": source_name, "profile": profile.name},
                    created_by_type=ActorType.import_job,
                    created_by_id=source_name,
                )
                self.db.add(doc_rev)
                self.db.flush()
                doc.latest_revision_id = doc_rev.id

                section_revisions: dict[str, ProposalSectionRevision] = {}
                section_types: dict[str, SectionType] = {}
                for section_key, content in normalized["sections"].items():
                    section_type = self._section_type(section_key, profile)
                    section_types[section_key] = section_type
                    section = ProposalSection(proposal_document_id=doc.id, section_type_id=section_type.id, section_key=section_key)
                    self.db.add(section)
                    self.db.flush()
                    rev = ProposalSectionRevision(
                        proposal_section_id=section.id,
                        proposal_document_revision_id=doc_rev.id,
                        revision_number=1,
                        content_text=str(content),
                        created_by_type=ActorType.import_job,
                        created_by_id=source_name,
                    )
                    self.db.add(rev)
                    self.db.flush()
                    section.latest_revision_id = rev.id
                    section_revisions[section_key] = rev

                for chunk in chunks_by_proposal.get(normalized["proposal_key"], []):
                    section_rev = section_revisions.get(chunk["section_key"])
                    if section_rev is None:
                        continue
                    self.db.add(
                        EmbeddingChunk(
                            proposal_document_id=doc.id,
                            proposal_section_revision_id=section_rev.id,
                            solution_type_id=solution_type.id,
                            section_type_id=section_types[chunk["section_key"]].id,
                            chunk_index=chunk["chunk_index"],
                            chunk_text=chunk["content"],
                            token_count=chunk["token_count"],
                            embedding_model=self.embedding_service.model_name,
                            content_hash=chunk["content_hash"],
                            metadata_json={
                                "industry": normalized["industry"],
                                "client_name": normalized["client_name"],
                                "external_id": doc.external_id,
                                "source_name": source_name,
                            },
                            embedding=chunk.get("embedding"),
                        )
                    )
                    persisted_chunks += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "ingested_count": result["ingested_count"],
            "section_count": result["section_count"],
            "chunk_count": persisted_chunks,
            "skipped_duplicates": duplicates,
            "skipped": result["skipped"],
            "source_name": source_name,
            "profile": profile.name,
        }
