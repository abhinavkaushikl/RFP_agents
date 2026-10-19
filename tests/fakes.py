"""Test doubles: a scripted Groq client, retrieval, and embeddings."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from typing import Any

from app.llm.types import ChatCompletion

SECTION_TEXT = (
    "**Understanding of Your Objectives**\n"
    "Northwind needs a cloud-hosted warehouse management system integrated with SAP ERP.\n\n"
    "**Proposed Approach**\n"
    "We will provide barcode scanning on handheld devices and real-time inventory visibility across all sites. "
    "The platform will integrate with SAP ERP through standard APIs.\n\n"
    "**Expected Outcomes**\n"
    "- Go-live for the first site within six months\n"
    "- Training for 200 warehouse staff\n"
)


def _json_for(name: str | None, messages: list[dict]) -> dict:
    user = messages[-1]["content"] if messages else ""
    if name == "rfp_brief":
        return {
            "title": "Warehouse Management System",
            "client_name": "Northwind Foods",
            "industry": "logistics",
            "request_summary": "Northwind Foods wants a cloud WMS integrated with SAP ERP across three warehouses.",
            "requirements": [
                {"id": "R1", "text": "Integrate with SAP ERP", "category": "integration", "priority": "must"},
                {"id": "R2", "text": "Barcode scanning on handheld devices", "category": "functional", "priority": "must"},
                {"id": "R3", "text": "Train 200 warehouse staff", "category": "delivery", "priority": "should"},
            ],
            "evaluation_criteria": ["Functional fit", "Price"],
            "deliverables": ["WMS platform"],
            "timeline": "Go-live within 6 months",
            "budget": "",
            "compliance_requirements": ["SOC 2"],
            "mentioned_vendors": ["SAP"],
            "solution_type": "Warehouse Management",
            "ambiguity_flags": [],
        }
    if name == "capability_inference":
        return {"capabilities": ["WMS implementation", "SAP integration"], "positioning_notes": ["Lead with SAP integration"],
                "fit_explanation": "Capabilities inferred."}
    if name == "catalog_match":
        return {
            "matches": [
                {"requirement_id": "R1", "offering_code": "digital_platforms", "coverage": "full", "rationale": "APIs"},
                {"requirement_id": "R2", "offering_code": "none", "coverage": "none", "rationale": "no catalog item"},
            ],
            "positioning_notes": ["Lead with integration accelerators"],
            "fit_explanation": "Partial fit.",
        }
    if name == "rubric":
        return {"overall_score": 7.5, "criteria": [{"criterion": "Functional fit", "score": 8, "comment": "Good."}],
                "strengths": ["Clear integration plan"], "weaknesses": ["No pricing"], "recommendations": ["Add pricing"]}
    if name == "plan":
        intent = re.search(r"Intent: (\w+)", user)
        intent = intent.group(1) if intent else "proposal_generation"
        from app.agentic.supervisor import REFERENCE_PLANS

        steps = [{"tool": t, "args": "{}"} for t in REFERENCE_PLANS[intent]]
        return {"steps": steps + [{"tool": "done", "args": json.dumps({"summary": "ok"})}]}
    if name == "intent":
        return {"intent": "proposal_generation"}
    if name == "next_action":
        return {"action": "continue", "reason": "skip"}
    if name == "done_check":
        return {"done": True, "summary": "Done."}
    if name == "opportunity_basics":
        return {"opportunity_name": "Cloud Modernization", "client_name": "Meridian Healthcare Systems",
                "existing_relationship": "Existing customer", "date_opened": "2026-05-10",
                "urgency_statement": "Board mandated migration by fiscal year end.", "primary_contact": "Sarah Chen, VP Technology"}
    if name == "problem_framing":
        return {"problem_statement": "Legacy data centers are too costly.", "success_definition": "Migrate 340 VMs.",
                "stakeholder_impact": "IT and clinical staff.", "urgency_statement": "Fiscal year deadline."}
    if name == "buyer_intelligence":
        return {
            "intent_classification": {"primary_intent": "Purchase intent", "detected_intents": ["Purchase intent"],
                                      "summary": "Buyer intends to purchase.", "confidence": 0.8},
            "buyer_readiness_score": 78, "readiness_stage": "High Intent", "confidence": 0.8,
            "reasoning": ["Budget approved"],
            "buyer_gaps": [{"gap_type": "ROI Clarity Gap", "severity": "Medium", "description": "ROI unclear",
                            "recommendation": "Share ROI model"}],
            "stakeholder_coverage": {"stakeholders": [{"name": "Sarah Chen", "role": "VP Technology",
                                                       "category": "Technical Evaluator", "influence_level": "High",
                                                       "engagement_quality": "Strong", "evidence": "Led the call"}],
                                     "identified_roles": ["Technical Evaluator"], "missing_roles": ["Procurement"],
                                     "coverage_score": 40, "engagement_summary": "One strong evaluator."},
            "conversation_highlights": ["Budget approved"], "recommended_next_actions": ["Engage procurement"],
        }
    if name == "product_fit":
        return {
            "product_fit_score": 70, "fit_stage": "Strong Fit", "confidence": 0.7, "fit_summary": "Good fit.",
            "matched_capabilities": [{"buyer_need": "Migration", "matched_capability": "Cloud migration",
                                      "capability_area": "Implementation and Services", "fit_strength": "Strong",
                                      "evidence": "340 VMs"}],
            "product_gaps": [], "integration_fit": {"score": 70, "summary": "OK", "required_integrations": [], "risks": []},
            "competitive_positioning": {"competitors_mentioned": [], "differentiators": [], "positioning_summary": ""},
            "risk_flags": [], "recommended_positioning": [], "recommended_next_actions": [],
        }
    if name == "revision":
        return {"revised_text": "**Revised**\nIncludes ISO 27001 controls and SAP ERP integration.",
                "change_summary": "Added ISO 27001.", "changed_topics": ["security"]}
    if name == "vendor_screen":
        return {"vendors": [
            {"domain": "aisera.com", "is_vendor": True, "description": "AIOps and service management platform."},
            {"domain": "monday.com", "is_vendor": False, "description": "Work management app."},
        ]}
    if name == "company_facts":
        return {"price": "unknown", "review": "unknown", "contact": "unknown", "founded_year": "unknown"}
    return {}


class FakeGroqClient:
    """Scripted replacement for GroqChatClient. Simulates provider prompt caching by prefix."""

    def __init__(self, *, fail_with: Exception | None = None, schema_error_once: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_with = fail_with
        self.schema_error_once = schema_error_once
        self._prefixes: set[str] = set()
        self._lock = threading.Lock()

    def chat(self, *, model, messages, temperature, max_completion_tokens, reasoning_effort=None,
             include_reasoning=None, response_format=None) -> ChatCompletion:
        with self._lock:
            self.calls.append({"model": model, "messages": messages, "response_format": response_format,
                               "reasoning_effort": reasoning_effort, "max_completion_tokens": max_completion_tokens})
        if self.fail_with is not None:
            raise self.fail_with
        if self.schema_error_once and response_format and response_format.get("type") == "json_schema":
            self.schema_error_once = False
            from app.llm.errors import LLMBadRequestError

            raise LLMBadRequestError("json_schema not supported")
        name = None
        if response_format and response_format.get("type") == "json_schema":
            name = response_format["json_schema"]["name"]
        elif response_format:
            for candidate in ("rfp_brief", "rubric", "plan"):
                if candidate in json.dumps(messages):
                    name = candidate
        text = json.dumps(_json_for(name, messages)) if response_format else SECTION_TEXT
        prompt_chars = sum(len(m["content"]) for m in messages)
        prompt_tokens = max(1, prompt_chars // 4)
        prefix = (messages[0]["content"] + messages[-1]["content"][:400]) if messages else ""
        with self._lock:
            cached = prompt_tokens // 2 if prefix in self._prefixes else 0
            self._prefixes.add(prefix)
        completion_tokens = max(1, len(text) // 4)
        return ChatCompletion(
            text=text,
            model=model,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=cached,
            completion_tokens=completion_tokens,
            reasoning_tokens=10,
            total_tokens=prompt_tokens + completion_tokens,
            headers={"x-ratelimit-limit-tokens": "100000", "x-ratelimit-remaining-tokens": "99000"},
        )


class FakeEmbeddingService:
    """Deterministic hashed bag-of-words vectors (L2-normalized)."""

    model_name = "fake-embeddings"
    dimensions = 64

    def encode(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


class FakeRetrievalService:
    def __init__(self) -> None:
        self.queries: list[dict] = []

    def search_relaxed(self, query, *, section_codes=None, solution_type=None, industries=None, top_k=4):
        self.queries.append({"query": query, "section_codes": section_codes, "industries": industries})
        return {
            "results": [
                {"id": f"chunk-{i}", "score": 0.8 - i * 0.1, "section_key": (section_codes or ["general"])[0],
                 "proposal_id": "hist-1", "content": "Phased rollout with SAP integration and staff training.",
                 "industry": "Transportation & Logistics", "solution_type": "general", "chunk_index": i}
                for i in range(2)
            ],
            "filters_applied": ["section"] if section_codes else [],
        }

    def search(self, query, **kwargs):
        return self.search_relaxed(query)["results"]
