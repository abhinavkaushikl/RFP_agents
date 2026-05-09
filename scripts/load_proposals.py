"""Bulk-load historical RFP records into pgvector.

Reads a JSONL file (one JSON record per line) and ingests every record into
PostgreSQL via the IngestionService, generating real 384-dim sentence-transformer
embeddings stored in the embedding_chunks table.

Example:
    PYTHONPATH=src python3 scripts/load_proposals.py \\
        --input data/raw/rfp_records.jsonl \\
        --source rfp-records-200
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_service import IngestionService


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to JSONL file")
    parser.add_argument("--source", default="bulk-load", help="source_name tag for the import")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Records per ingestion batch (smaller = lower memory, larger = faster)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    records = load_jsonl(input_path)
    print(f"Loaded {len(records)} records from {input_path}")

    print("Initialising embedding model (this may take a moment on first run)...")
    embedding_service = EmbeddingService()
    _ = embedding_service.model  # eager-load
    print(f"Embedding model: {embedding_service.model_name} ({embedding_service.dimensions} dims)")

    total_ingested = 0
    total_sections = 0
    total_chunks = 0

    for batch_start in range(0, len(records), args.batch_size):
        batch = records[batch_start : batch_start + args.batch_size]
        print(f"  ingesting records {batch_start + 1}–{batch_start + len(batch)}...")

        db = SessionLocal()
        try:
            ingestion = IngestionService(db=db, embedding_service=embedding_service)
            result = ingestion.ingest_historical(batch, source_name=args.source)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        total_ingested += result["ingested_count"]
        total_sections += result["section_count"]
        total_chunks += result["chunk_count"]

    print("")
    print("=== Done ===")
    print(f"  records ingested: {total_ingested}")
    print(f"  sections persisted: {total_sections}")
    print(f"  chunks embedded: {total_chunks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
