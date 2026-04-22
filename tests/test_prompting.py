from rfp_mistral.data.prepare_dataset import build_training_examples
from rfp_mistral.data.prompting import build_training_example
from rfp_mistral.schemas import RFPRecord


def test_build_training_example_includes_target_section() -> None:
    record = RFPRecord(
        id="rfp-1",
        client_name="Acme",
        industry="Healthcare",
        rfp_title="Cloud",
        rfp_summary="Need migration support.",
        requirements=["Requirement A"],
        evaluation_criteria=["Capability"],
        solution_summary="Phased delivery.",
        proposal_sections={"executive_summary": "Draft summary."},
        tags=["cloud"],
    )

    example = build_training_example(record, "executive_summary")

    assert "Generate the `executive_summary` section" in example.prompt
    assert example.response.endswith("</s>")
    assert example.record_id == "rfp-1"


def test_build_training_examples_all_sections() -> None:
    record = RFPRecord(
        id="rfp-2",
        client_name="Acme",
        industry="Healthcare",
        rfp_title="Cloud",
        rfp_summary="Need migration support.",
        requirements=["Requirement A"],
        evaluation_criteria=["Capability"],
        solution_summary="Phased delivery.",
        proposal_sections={
            "executive_summary": "Draft summary.",
            "implementation_plan": "Phase 1, Phase 2.",
        },
        tags=["cloud"],
    )

    examples = build_training_examples([record], "all")

    assert len(examples) == 2
    assert {example.target_section for example in examples} == {
        "executive_summary",
        "implementation_plan",
    }
