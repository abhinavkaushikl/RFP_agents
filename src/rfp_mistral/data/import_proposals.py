from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rfp_mistral.data.io import write_jsonl, write_training_examples
from rfp_mistral.data.prepare_dataset import build_training_examples
from rfp_mistral.schemas import RFPRecord

DEFAULT_ULTRA_INPUT = Path.home() / "Downloads" / "final_ultra_proposals_100.json"
DEFAULT_TONE_INPUT = (
    Path.home() / "Downloads" / "ultimate_proposals_with_tone_visuals(1).json"
)
DEFAULT_RAW_OUTPUT = Path("data/raw/rfp_records.jsonl")
DEFAULT_TRAIN_OUTPUT = Path("data/processed/train.jsonl")

CLIENT_INDUSTRY_MAP = {
    "AT&T US": "Telecommunications",
    "Airtel India": "Telecommunications",
    "BT Group UK": "Telecommunications",
    "Etisalat UAE": "Telecommunications",
    "MTN Africa": "Telecommunications",
    "Orange France": "Telecommunications",
    "Reliance Jio": "Telecommunications",
    "T-Mobile US": "Telecommunications",
    "Telefonica Spain": "Telecommunications",
    "Vodafone EU": "Telecommunications",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge proposal sample JSON files into normalized raw and training datasets."
    )
    parser.add_argument(
        "--ultra-input",
        default=str(DEFAULT_ULTRA_INPUT),
        help="Path to the core proposal JSON file",
    )
    parser.add_argument(
        "--tone-input",
        default=str(DEFAULT_TONE_INPUT),
        help="Path to the tone and visuals proposal JSON file",
    )
    parser.add_argument(
        "--raw-output",
        default=str(DEFAULT_RAW_OUTPUT),
        help="Output path for normalized raw JSONL records",
    )
    parser.add_argument(
        "--train-output",
        default=str(DEFAULT_TRAIN_OUTPUT),
        help="Output path for instruction-tuning JSONL examples",
    )
    parser.add_argument(
        "--target-section",
        default="all",
        help="Proposal section to prepare for training, or 'all' for every section",
    )
    return parser.parse_args()


def _read_json(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return [item for item in payload if isinstance(item, dict)]


def _labelize(text: str) -> str:
    return text.replace("_", " ").strip().title()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "record"


def _stringify_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _flatten_kv_items(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in payload.items():
        label = _labelize(key)
        if isinstance(value, dict):
            nested = ", ".join(_flatten_kv_items(value))
            if nested:
                lines.append(f"{label}: {nested}")
        elif isinstance(value, list):
            rendered = ", ".join(_stringify_scalar(item) for item in value if item is not None)
            if rendered:
                lines.append(f"{label}: {rendered}")
        else:
            rendered = _stringify_scalar(value)
            if rendered:
                lines.append(f"{label}: {rendered}")
    return lines


def _format_section_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        lines = _flatten_kv_items(value)
        return "\n".join(f"- {line}" for line in lines)
    if isinstance(value, list):
        return "\n".join(f"- {_stringify_scalar(item)}" for item in value if item is not None)
    return _stringify_scalar(value).strip()


def _build_requirements(record: dict[str, Any]) -> list[str]:
    requirements: list[str] = []
    for field in ("client_kpis", "delivery", "contract_annexure", "visual_assets", "negotiation_hooks"):
        value = record.get(field)
        if isinstance(value, dict):
            requirements.extend(_flatten_kv_items(value))
    if isinstance(record.get("financials"), dict):
        requirements.extend(_flatten_kv_items(record["financials"]))
    if isinstance(record.get("roi_summary"), dict):
        requirements.extend(_flatten_kv_items(record["roi_summary"]))
    return requirements


def _build_evaluation_criteria(record: dict[str, Any]) -> list[str]:
    criteria = [
        "Business impact and ROI clarity",
        "Technical fit for telecom operations",
        "Delivery feasibility and timeline confidence",
        "Commercial flexibility and implementation value",
    ]
    if record.get("competitor_positioning"):
        criteria.append("Differentiation against incumbent vendors")
    if record.get("visual_assets"):
        criteria.append("Executive-friendly presentation and visual storytelling")
    return criteria


def _build_sections(record: dict[str, Any], source: str) -> dict[str, str]:
    field_map = {
        "executive_summary": "executive_summary",
        "tone_specific_summary": "tone_specific_summary",
        "deal_storytelling": "deal_storytelling",
        "competitor_positioning": "competitor_positioning",
        "architecture_diagram_text": "architecture_diagram",
        "financials": "financials",
        "pricing": "pricing_notes",
        "contract_annexure": "contract_annexure",
        "delivery": "implementation_plan",
        "visual_assets": "visual_assets",
        "negotiation_hooks": "negotiation_hooks",
        "roi_summary": "roi_summary",
    }
    sections: dict[str, str] = {}
    for source_key, target_key in field_map.items():
        value = record.get(source_key)
        if value in (None, "", [], {}):
            continue
        rendered = _format_section_value(value)
        if rendered:
            sections[target_key] = rendered

    if "executive_summary" not in sections and "tone_specific_summary" in sections:
        sections["executive_summary"] = sections["tone_specific_summary"]
    if "pricing_notes" not in sections and "financials" in sections:
        sections["pricing_notes"] = sections["financials"]

    sections["source_dataset"] = source
    return sections


def _build_summary(record: dict[str, Any], sections: dict[str, str]) -> str:
    parts = [
        _stringify_scalar(record.get("executive_summary")),
        _stringify_scalar(record.get("tone_specific_summary")),
        _stringify_scalar(record.get("deal_storytelling")),
    ]
    summary = " ".join(part.strip() for part in parts if part and part.strip())
    if summary:
        return summary
    for key in ("executive_summary", "tone_specific_summary", "deal_storytelling"):
        if key in sections:
            return sections[key]
    return "Telecom transformation proposal focused on measurable operational outcomes."


def normalize_record(record: dict[str, Any], source: str, sequence: int) -> RFPRecord:
    client_name = _stringify_scalar(record.get("client")) or "Unknown Client"
    sections = _build_sections(record, source)
    summary = _build_summary(record, sections)
    requirements = _build_requirements(record)

    return RFPRecord(
        id=f"{_slugify(source)}-{sequence:03d}",
        client_name=client_name,
        industry=CLIENT_INDUSTRY_MAP.get(client_name, "Telecommunications"),
        rfp_title=f"AIOps Transformation Proposal for {client_name}",
        rfp_summary=summary,
        requirements=requirements,
        evaluation_criteria=_build_evaluation_criteria(record),
        solution_summary=sections.get("executive_summary", summary),
        proposal_sections=sections,
        tags=[
            "telecommunications",
            "aiops",
            "proposal",
            _slugify(client_name),
            _slugify(source),
        ],
    )


def main() -> None:
    args = parse_args()

    ultra_records = _read_json(args.ultra_input)
    tone_records = _read_json(args.tone_input)

    records = [
        *[
            normalize_record(record, "final_ultra_proposals_100", index)
            for index, record in enumerate(ultra_records, start=1)
        ],
        *[
            normalize_record(record, "ultimate_proposals_with_tone_visuals", index)
            for index, record in enumerate(tone_records, start=1)
        ],
    ]

    write_jsonl(args.raw_output, (record.__dict__ for record in records))
    examples = build_training_examples(records, args.target_section)
    write_training_examples(args.train_output, examples)

    print(f"Wrote {len(records)} raw records to {args.raw_output}")
    print(f"Wrote {len(examples)} training examples to {args.train_output}")


if __name__ == "__main__":
    main()
