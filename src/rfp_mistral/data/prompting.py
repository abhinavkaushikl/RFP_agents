from __future__ import annotations

from textwrap import dedent

from rfp_mistral.schemas import RFPRecord, TrainingExample


SYSTEM_PROMPT = (
    "You are an enterprise proposal specialist. Produce accurate, persuasive, "
    "and requirement-aligned RFP response sections."
)


def _format_bullets(items: list[str]) -> str:
    if not items:
        return "- None provided"
    return "\n".join(f"- {item}" for item in items)


def build_instruction_prompt(record: RFPRecord, target_section: str) -> str:
    return dedent(
        f"""<s>[INST] {SYSTEM_PROMPT}

Generate the `{target_section}` section for the following RFP.

Client: {record.client_name}
Industry: {record.industry}
RFP Title: {record.rfp_title}

RFP Summary:
{record.rfp_summary}

Requirements:
{_format_bullets(record.requirements)}

Evaluation Criteria:
{_format_bullets(record.evaluation_criteria)}

Known Solution Direction:
{record.solution_summary or "Not provided"}

Instructions:
- Be specific and business-ready
- Align to the listed requirements
- Avoid unsupported claims
- Write only the requested section
[/INST]
"""
    )


def build_training_example(record: RFPRecord, target_section: str) -> TrainingExample:
    if target_section not in record.proposal_sections:
        raise ValueError(
            f"Record {record.id} is missing proposal section '{target_section}'"
        )

    return TrainingExample(
        record_id=record.id,
        prompt=build_instruction_prompt(record, target_section),
        response=record.proposal_sections[target_section] + "</s>",
        target_section=target_section,
    )

