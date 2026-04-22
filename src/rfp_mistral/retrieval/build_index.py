from __future__ import annotations

import argparse
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rfp_mistral.data.io import load_rfp_records, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a FAISS index for proposals.")
    parser.add_argument("--input", required=True, help="Path to raw JSONL records")
    parser.add_argument("--output-dir", required=True, help="Directory for index files")
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-transformers embedding model",
    )
    return parser.parse_args()


def build_document(record: dict) -> str:
    sections = record.get("proposal_sections", {})
    section_text = "\n".join(f"{name}: {text}" for name, text in sections.items())
    requirements = "\n".join(f"- {item}" for item in record.get("requirements", []))
    return (
        f"Client: {record.get('client_name', '')}\n"
        f"Industry: {record.get('industry', '')}\n"
        f"Title: {record.get('rfp_title', '')}\n"
        f"Summary: {record.get('rfp_summary', '')}\n"
        f"Requirements:\n{requirements}\n"
        f"Proposal:\n{section_text}"
    )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = [record.__dict__ for record in load_rfp_records(args.input)]
    documents = [build_document(record) for record in records]

    model = SentenceTransformer(args.embedding_model)
    embeddings = model.encode(documents, normalize_embeddings=True)
    matrix = np.asarray(embeddings, dtype=np.float32)

    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    faiss.write_index(index, str(output_dir / "proposal.index"))

    metadata_path = output_dir / "metadata.jsonl"
    write_jsonl(metadata_path, records)

    manifest = {
        "embedding_model": args.embedding_model,
        "dimension": int(matrix.shape[1]),
        "count": int(matrix.shape[0]),
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    print(f"Saved index with {len(records)} records to {output_dir}")


if __name__ == "__main__":
    main()

