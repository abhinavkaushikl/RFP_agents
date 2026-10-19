"""Domain profiles: everything industry- or company-specific, as data.

A profile is a YAML file in `configs/domain_profiles/`. It defines the
organization writing the proposals, its offering catalog, the proposal
sections and their writing guidance, industry names, sales-analysis
categories, and scoring weights. Code never hardcodes any of these.

Profiles can inherit with `extends: <other profile>`; mappings are merged
recursively and lists are replaced.
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, fallback: str = "general") -> str:
    slug = _SLUG_RE.sub("_", (value or "").strip().lower()).strip("_")
    return slug[:100] or fallback


class ProfileNotFoundError(LookupError):
    pass


class OrganizationDef(BaseModel):
    name: str = "our organization"
    description: str = ""
    differentiators: list[str] = Field(default_factory=list)


class WritingDef(BaseModel):
    tone: str = "professional, specific, and evidence-based"
    locale: str = "en-US"
    currency: str = "USD"
    style_rules: list[str] = Field(default_factory=list)


class IndustryDef(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class OfferingDef(BaseModel):
    code: str
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def _slug(cls, value: str) -> str:
        return slugify(value)


class SectionDef(BaseModel):
    key: str
    title: str
    words: tuple[int, int] = (200, 300)
    guidance: str = ""
    headings: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _slug(cls, value: str) -> str:
        return slugify(value)


class StageDef(BaseModel):
    name: str
    max_score: int


class BuyerIntelligenceDef(BaseModel):
    readiness_stages: list[StageDef] = Field(default_factory=list)
    intent_types: list[str] = Field(default_factory=list)
    gap_types: list[str] = Field(default_factory=list)
    stakeholder_categories: list[str] = Field(default_factory=list)


class ProductFitDef(BaseModel):
    fit_stages: list[StageDef] = Field(default_factory=list)
    gap_types: list[str] = Field(default_factory=list)
    capability_areas: list[str] = Field(default_factory=list)


class ScoringDef(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
    default_evaluation_criteria: list[str] = Field(default_factory=list)


class LexiconsDef(BaseModel):
    competitors: list[str] = Field(default_factory=list)
    compliance_frameworks: list[str] = Field(default_factory=list)


class MarketResearchDef(BaseModel):
    default_offerings: list[str] = Field(default_factory=list)


class DomainProfile(BaseModel):
    name: str
    version: str = ""
    display_name: str = ""
    description: str = ""
    organization: OrganizationDef = Field(default_factory=OrganizationDef)
    writing: WritingDef = Field(default_factory=WritingDef)
    industries: list[IndustryDef] = Field(default_factory=list)
    offerings: list[OfferingDef] = Field(default_factory=list)
    sections: list[SectionDef] = Field(default_factory=list)
    default_sections: list[str] = Field(default_factory=list)
    buyer_intelligence: BuyerIntelligenceDef = Field(default_factory=BuyerIntelligenceDef)
    product_fit: ProductFitDef = Field(default_factory=ProductFitDef)
    scoring: ScoringDef = Field(default_factory=ScoringDef)
    lexicons: LexiconsDef = Field(default_factory=LexiconsDef)
    market_research: MarketResearchDef = Field(default_factory=MarketResearchDef)

    # ── sections ──────────────────────────────────────────────────────
    def _section_index(self) -> dict[str, SectionDef]:
        index: dict[str, SectionDef] = {}
        for sec in self.sections:
            index.setdefault(sec.key, sec)
        for sec in self.sections:
            for alias in sec.aliases:
                index.setdefault(slugify(alias), sec)
        return index

    def canonical_section_key(self, key: str) -> str:
        slug = slugify(key, fallback="section")
        sec = self._section_index().get(slug)
        return sec.key if sec else slug

    def section(self, key: str) -> SectionDef:
        slug = slugify(key, fallback="section")
        sec = self._section_index().get(slug)
        if sec:
            return sec
        return SectionDef(
            key=slug,
            title=slug.replace("_", " ").title(),
            words=(200, 300),
            guidance="Address the parts of the RFP that relate to this topic, using three or four bold sub-headings.",
        )

    def section_title(self, key: str) -> str:
        return self.section(key).title

    def section_codes(self, key: str) -> list[str]:
        """Section codes to match in retrieval: the canonical key plus its aliases."""
        sec = self.section(key)
        codes = [sec.key, *(slugify(a) for a in sec.aliases)]
        raw = slugify(key, fallback="section")
        if raw not in codes:
            codes.append(raw)
        return list(dict.fromkeys(codes))

    def resolved_default_sections(self) -> list[str]:
        if self.default_sections:
            return [self.canonical_section_key(k) for k in self.default_sections]
        return [s.key for s in self.sections[:4]] or ["executive_summary"]

    # ── industries ────────────────────────────────────────────────────
    def canonical_industry(self, value: str | None) -> str | None:
        if not value or not str(value).strip():
            return None
        text = str(value).strip()
        lowered = text.lower()
        for ind in self.industries:
            if lowered == ind.name.lower() or lowered in (a.lower() for a in ind.aliases):
                return ind.name
        return text

    def industry_match_values(self, value: str | None) -> list[str] | None:
        """Lower-cased names that should match a stored industry for this filter."""
        if not value:
            return None
        canonical = self.canonical_industry(value) or value
        values = {canonical.lower(), str(value).strip().lower()}
        for ind in self.industries:
            if ind.name == canonical:
                values.update(a.lower() for a in ind.aliases)
        return sorted(values)

    @property
    def industry_names(self) -> list[str]:
        return [ind.name for ind in self.industries]

    # ── offerings ─────────────────────────────────────────────────────
    def offering(self, code: str | None) -> OfferingDef | None:
        if not code:
            return None
        slug = slugify(code)
        return next((o for o in self.offerings if o.code == slug), None)

    def catalog_text(self) -> str:
        """Deterministic text rendering of the offering catalog for prompts."""
        lines: list[str] = []
        for off in self.offerings:
            lines.append(f"- {off.code}: {off.name}" + (f" — {off.description}" if off.description else ""))
            if off.capabilities:
                lines.append("  capabilities: " + "; ".join(off.capabilities))
            if off.differentiators:
                lines.append("  differentiators: " + "; ".join(off.differentiators))
        return "\n".join(lines)

    # ── scoring helpers ───────────────────────────────────────────────
    @staticmethod
    def stage_for_score(stages: list[StageDef], score: int) -> str:
        ordered = sorted(stages, key=lambda s: s.max_score)
        for stage in ordered:
            if score <= stage.max_score:
                return stage.name
        return ordered[-1].name if ordered else ""

    def public_view(self) -> dict[str, Any]:
        """What the UI needs to build forms; excludes nothing sensitive by design."""
        return {
            "name": self.name,
            "version": self.version,
            "display_name": self.display_name or self.name,
            "description": self.description,
            "organization": self.organization.model_dump(),
            "industries": self.industry_names,
            "offerings": [o.model_dump() for o in self.offerings],
            "sections": [
                {"key": s.key, "title": s.title, "words": list(s.words), "headings": s.headings}
                for s in self.sections
            ],
            "default_sections": self.resolved_default_sections(),
            "buyer_intelligence": self.buyer_intelligence.model_dump(),
            "product_fit": self.product_fit.model_dump(),
            "scoring": self.scoring.model_dump(),
            "lexicons": self.lexicons.model_dump(),
            "market_research": self.market_research.model_dump(),
        }


# ── loading ───────────────────────────────────────────────────────────
_cache: dict[tuple[str, str], DomainProfile] = {}
_cache_lock = threading.Lock()


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _profile_path(name: str, directory: Path) -> Path:
    if not _NAME_RE.match(name):
        raise ProfileNotFoundError(f"Invalid profile name '{name}'")
    for suffix in (".yaml", ".yml"):
        path = directory / f"{name}{suffix}"
        if path.is_file():
            return path
    raise ProfileNotFoundError(f"Domain profile '{name}' not found in {directory}")


def _load_raw(name: str, directory: Path, seen: tuple[str, ...] = ()) -> tuple[dict, list[str]]:
    if name in seen:
        raise ProfileNotFoundError(f"Circular 'extends' in profile '{name}'")
    path = _profile_path(name, directory)
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ProfileNotFoundError(f"Profile '{name}' must be a YAML mapping")
    parent = data.pop("extends", None)
    hashes = [text]
    if parent:
        base, parent_hashes = _load_raw(str(parent), directory, seen + (name,))
        data = _deep_merge(base, data)
        hashes = parent_hashes + hashes
    return data, hashes


def load_profile(name: str | None = None) -> DomainProfile:
    settings = get_settings()
    profile_name = (name or settings.default_profile).strip().lower()
    directory = settings.profile_dir
    data, sources = _load_raw(profile_name, directory)
    version = hashlib.sha256("\n---\n".join(sources).encode("utf-8")).hexdigest()[:12]
    key = (profile_name, version)
    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None:
            return cached
        data["name"] = profile_name
        data["version"] = version
        profile = DomainProfile.model_validate(data)
        _cache[key] = profile
        return profile


def list_profiles() -> list[dict[str, str]]:
    directory = get_settings().profile_dir
    out: list[dict[str, str]] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.y*ml")):
        name = path.stem
        if not _NAME_RE.match(name):
            continue
        try:
            profile = load_profile(name)
        except Exception:  # noqa: BLE001
            continue
        out.append(
            {
                "name": profile.name,
                "display_name": profile.display_name or profile.name,
                "description": profile.description,
                "version": profile.version,
            }
        )
    return out


__all__ = [
    "DomainProfile",
    "ProfileNotFoundError",
    "SectionDef",
    "list_profiles",
    "load_profile",
    "slugify",
]
