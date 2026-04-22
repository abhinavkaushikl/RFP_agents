from __future__ import annotations

from textwrap import dedent


def build_generation_request(query: str, retrieved_examples: list[dict]) -> str:
    examples_block = []
    for item in retrieved_examples:
        sections = item.get("proposal_sections", {})
        examples_block.append(
            dedent(
                f"""Example Proposal
Client: {item.get("client_name", "")}
Industry: {item.get("industry", "")}
Title: {item.get("rfp_title", "")}
Relevant Requirements:
{chr(10).join(f"- {req}" for req in item.get("requirements", []))}
Executive Summary:
{sections.get("executive_summary", "")}
"""
            )
        )

    joined_examples = "\n\n".join(examples_block) if examples_block else "No retrieved examples."
    return dedent(
        f"""You are preparing a high-quality RFP response.

User Request:
{query}

Retrieved Historical Examples:
{joined_examples}

Write a polished draft that borrows style and structure from the examples but does not copy text verbatim.
"""
    )
