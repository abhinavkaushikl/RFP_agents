from __future__ import annotations

from app.ingestion.pipeline import ingest_historical_records


class IngestionService:
    def ingest_historical(self, records: list[dict], source_name: str) -> dict:
        return ingest_historical_records(records, source_name)
