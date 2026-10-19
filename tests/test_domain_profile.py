from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agents.prompts import build_section_messages, system_prompt
from app.domain.profile import ProfileNotFoundError, load_profile

ROOT = Path(__file__).resolve().parents[1]
# Terms from the original telecom/AIOps dataset that must not reappear in generic code or defaults.
DATASET_TERMS = re.compile(r"(?i)\b(aiops|nokia|huawei|ericsson|vodafone|mttr|airtel|reliance jio|meridian)\b")


def test_default_profile_loads_with_generic_sections():
    p = load_profile()
    assert p.name == "default" and p.version
    assert p.resolved_default_sections() == ["executive_summary", "solution_overview", "implementation_plan", "pricing_notes"]
    assert p.offerings == []


def test_section_aliases_cover_legacy_keys():
    p = load_profile()
    assert p.canonical_section_key("architecture_diagram") == "solution_architecture"
    assert p.canonical_section_key("Pricing") == "pricing_notes"
    assert "architecture_diagram" in p.section_codes("solution_architecture")
    unknown = p.section("data_migration_strategy")
    assert unknown.title == "Data Migration Strategy"


def test_industry_canonicalization():
    p = load_profile()
    assert p.canonical_industry("telecom") == "Telecommunications"
    assert p.canonical_industry("Space Mining") == "Space Mining"
    assert p.canonical_industry("") is None
    assert "healthcare & life sciences" in p.industry_match_values("Healthcare")


def test_profile_inheritance():
    p = load_profile("example_company")
    assert p.organization.name == "Northbeam Solutions"
    assert len(p.sections) == len(load_profile().sections)
    assert p.offering("data_analytics").name == "Data and Analytics"
    assert p.version != load_profile().version


@pytest.mark.parametrize("name", ["../secrets", "UPPER", "a/b", "missing_profile"])
def test_bad_profile_names_rejected(name):
    with pytest.raises(ProfileNotFoundError):
        load_profile(name)


def test_stage_for_score():
    p = load_profile()
    stages = p.buyer_intelligence.readiness_stages
    assert p.stage_for_score(stages, 0) == "Cold"
    assert p.stage_for_score(stages, 60) == "Evaluation Stage"
    assert p.stage_for_score(stages, 100) == "Ready to Buy"


def test_prompts_are_generic_and_static_first():
    p = load_profile()
    ctx = {"client_name": "Acme", "requirements": ["Do X"], "request_summary": "Summary."}
    messages = build_section_messages(p, ctx, "implementation_plan", [])
    assert messages[0]["content"] == system_prompt(p)
    assert messages[1]["content"].startswith("## RFP CONTEXT")
    other = build_section_messages(p, ctx, "executive_summary", [])
    shared = messages[1]["content"].split("## SECTION TO WRITE")[0]
    assert other[1]["content"].startswith(shared)  # identical prefix across sections → provider cache hits
    assert not DATASET_TERMS.search(messages[0]["content"] + messages[1]["content"])


def test_no_dataset_terms_in_generic_code():
    offenders = []
    for folder in ("src/app", "ui", "web/src", "configs/domain_profiles"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix not in {".py", ".yaml", ".yml", ".ts", ".tsx"} or "__pycache__" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if DATASET_TERMS.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:80]}")
    assert not offenders, "\n".join(offenders)
