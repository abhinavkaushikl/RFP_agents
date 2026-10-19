"""Convert proposal exports (JSON arrays or JSONL) into RFPRecord JSONL and training examples.

Works with any corpus. Field names are detected from common conventions, and a
`--field-map` JSON file can map source fields to section keys explicitly:

    {"exec_summary": "executive_summary", "delivery": "implementation_plan"}

Example:
    PYTHONPATH=src python -m rfp_mistral.data.import_proposals \\
        --input exports/proposals_2024.json exports/proposals_2025.jsonl \\
        --raw-output data/raw/rfp_records.jsonl \\
        --train-output data/processed/train.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rfp_mistral.data.io import write_jsonl, write_training_examples
from rfp_mistral.data.prepare_dataset import build_training_examples
from rfp_mistral.schemas import RFPRecord

DEFAULT_EVALUATION_CRITERIA = [
    "Understanding of the buyer's requirements",
    "Quality and feasibility of the proposed solution",
    "Delivery plan and timeline credibility",
    "Value for money",
]
_METADATA = {
    "id", "client", "client_name", "customer", "industry", "sector", "title", "rfp_title", "name",
    "rfp_summary", "summary", "requirements", "evaluation_criteria", "tags", "solution_type",
    "proposal_sections", "sections", "metadata",
}
_MIN_SECTION_CHARS = 80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", nargs="+", required=True, help="JSON array or JSONL files")
    parser.add_argument("--raw-output", default="data/raw/rfp_records.jsonl")
    parser.add_argument("--train-output", default="data/processed/train.jsonl")
    parser.add_argument("--target-section", default="all", help="Section to train on, or 'all'")
    parser.add_argument("--default-industry", default="", help="Industry for records that do not state one")
    parser.add_argument("--field-map", help="JSON file mapping source field names to section keys")
    return parser.parse_args()


def _read_records(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        payload = json.loads(text)
        return [item for item in payload if isinstance(item, dict)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or "section"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, dict):
        return "\n".join(f"- {k.replace('_', ' ').capitalize()}: {_stringify(v)}" for k, v in value.items() if _stringify(v))
    if isinstance(value, list):
        return "\n".join(f"- {_stringify(v)}" for v in value if _stringify(v))
    return str(value).strip()


def _sections(record: dict[str, Any], field_map: dict[str, str]) -> dict[str, str]:
    raw = record.get("proposal_sections") or record.get("sections")
    if isinstance(raw, dict):
        return {_slugify(k): _stringify(v) for k, v in raw.items() if _stringify(v)}
    if isinstance(raw, list):
        out: dict[str, str] = {}
        for entry in raw:
            if isinstance(entry, dict):
                key = entry.get("key") or entry.get("title") or entry.get("heading") or "section"
                text = _stringify(entry.get("content") or entry.get("text"))
                if text:
                    out[_slugify(key)] = text
        return out
    out = {}
    for source_key, value in record.items():
        if source_key in field_map:
            target = field_map[source_key]
        elif source_key.lower() in _METADATA:
            continue
        else:
            target = _slugify(source_key)
        text = _stringify(value)
        if text and (source_key in field_map or len(text) >= _MIN_SECTION_CHARS):
            out[target] = f"{out[target]}\n\n{text}" if target in out else text
    return out


def normalize_record(
    record: dict[str, Any],
    source: str,
    sequence: int,
    *,
    default_industry: str = "",
    field_map: dict[str, str] | None = None,
) -> RFPRecord:
    client = _stringify(record.get("client_name") or record.get("client") or record.get("customer")) or "Unknown client"
    industry = _stringify(record.get("industry") or record.get("sector")) or default_industry
    sections = _sections(record, field_map or {})
    summary = _stringify(record.get("rfp_summary") or record.get("summary")) or sections.get("executive_summary", "")[:600]
    requirements = record.get("requirements")
    criteria = record.get("evaluation_criteria")
    tags = record.get("tags") if isinstance(record.get("tags"), list) else [t for t in (_slugify(industry), _slugify(client)) if t]
    return RFPRecord(
        id=str(record.get("id") or f"{_slugify(source)}-{sequence:04d}"),
        client_name=client,
        industry=industry,
        rfp_title=_stringify(record.get("title") or record.get("rfp_title")) or f"Proposal for {client}",
        rfp_summary=summary,
        requirements=[_stringify(r) for r in requirements] if isinstance(requirements, list) else [],
        evaluation_criteria=[_stringify(c) for c in criteria] if isinstance(criteria, list) else list(DEFAULT_EVALUATION_CRITERIA),
        solution_summary=sections.get("solution_overview") or sections.get("executive_summary", summary),
        proposal_sections=sections,
        tags=[str(t) for t in tags],
    )


def main() -> None:
    args = parse_args()
    field_map = json.loads(Path(args.field_map).read_text(encoding="utf-8")) if args.field_map else {}
    records: list[RFPRecord] = []
    for path in args.input:
        source = Path(path).stem
        for index, raw in enumerate(_read_records(path), start=1):
            record = normalize_record(raw, source, index, default_industry=args.default_industry, field_map=field_map)
            if record.proposal_sections:
                records.append(record)
    write_jsonl(args.raw_output, (record.__dict__ for record in records))
    examples = build_training_examples(records, args.target_section)
    write_training_examples(args.train_output, examples)
    print(f"Wrote {len(records)} raw records to {args.raw_output}")
    print(f"Wrote {len(examples)} training examples to {args.train_output}")


if __name__ == "__main__":
    main()
