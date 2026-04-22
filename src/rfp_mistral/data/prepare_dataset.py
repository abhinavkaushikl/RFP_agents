from __future__ import annotations

import argparse

from rfp_mistral.data.io import load_rfp_records, write_training_examples
from rfp_mistral.data.prompting import build_training_example
from rfp_mistral.schemas import TrainingExample


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert raw RFP records into Mistral fine-tuning examples."
    )
    parser.add_argument("--input", required=True, help="Path to raw JSONL records")
    parser.add_argument("--output", required=True, help="Path to output JSONL dataset")
    parser.add_argument(
        "--target-section",
        default="all",
        help="Proposal section to learn during training, or 'all' for every section",
    )
    return parser.parse_args()


def build_training_examples(
    records: list, target_section: str = "all"
) -> list[TrainingExample]:
    examples: list[TrainingExample] = []
    for record in records:
        if target_section == "all":
            sections = sorted(record.proposal_sections)
        else:
            sections = [target_section] if target_section in record.proposal_sections else []

        examples.extend(build_training_example(record, section) for section in sections)
    return examples


def main() -> None:
    args = parse_args()
    records = load_rfp_records(args.input)
    examples = build_training_examples(records, args.target_section)
    write_training_examples(args.output, examples)
    print(f"Wrote {len(examples)} training examples to {args.output}")


if __name__ == "__main__":
    main()
