from __future__ import annotations

import uuid

from app.agents.registry import build_agent_registry
from app.schemas.domain import AgentContext
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService


class ProposalWorkflowOrchestrator:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
        agent_registry: dict[str, object] | None = None,


    ) -> None:
        self.agent_registry = agent_registry or build_agent_registry(retrieval_service, llm_service)

    def run_proposal_workflow(self, payload: dict) -> dict:
        workflow_id = str(uuid.uuid4())
        context = AgentContext(workflow_id=workflow_id)
        step_summaries: list[str] = []

        request_result = self.agent_registry["request_structuring"].run(payload, context)
        step_summaries.append(request_result.summary)

        planner_result = self.agent_registry["planner"].run({**payload, **request_result.output}, context)
        step_summaries.append(planner_result.summary)

        solution_result = self.agent_registry["solution_comparison"].run(request_result.output, context)
        step_summaries.append(solution_result.summary)

        sections: list[dict] = []
        for section_key in planner_result.output["target_sections"]:
            retrieval_result = self.agent_registry["retrieval"].run(
                {
                    "query": payload["request_text"],
                    "section_type": section_key,
                    "solution_type": request_result.output["solution_type"],
                    "industry": request_result.output["industry"],
                    "top_k": 5,
                },
                context,
            )
            step_summaries.append(retrieval_result.summary)

            generation_result = self.agent_registry["generation"].run(
                {
                    "section_key": section_key,
                    "request_summary": request_result.output["request_summary"],
                    "requirements": request_result.output.get("requirements", []),
                    "vendors": request_result.output.get("vendors", []),
                    "industry": request_result.output.get("industry", ""),
                    "solution_type": request_result.output.get("solution_type", ""),
                    "client_name": payload.get("metadata", {}).get("client_name")
                    or payload.get("title", "the client"),
                    "evidence": retrieval_result.output["results"],
                    "matching_offerings": solution_result.output["matching_offerings"],
                    "fast_mode": bool(payload.get("metadata", {}).get("fast_mode")),
                },
                context,
            )
            step_summaries.append(generation_result.summary)

            validation_result = self.agent_registry["validation"].run(
                {
                    "draft_text": generation_result.output["draft_text"],
                    "requirements": request_result.output["requirements"],
                },
                context,
            )
            step_summaries.append(validation_result.summary)
            sections.append(
                {
                    "section_key": section_key,
                    "draft_text": generation_result.output["draft_text"],
                    "citations": generation_result.output["citations"],
                    "validation": validation_result.output,
                }
            )

        composite_text = "\n\n".join(section["draft_text"] for section in sections)
        scoring_result = self.agent_registry["scoring"].run(
            {
                "document_text": composite_text,
                "requirements": request_result.output["requirements"],
                "solution_type": request_result.output["solution_type"],
                "retrieval_score_hint": 0.8,
                "matched_evidence": [section["citations"] for section in sections],
            },
            context,
        )
        step_summaries.append(scoring_result.summary)
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "request": request_result.output,
            "plan": planner_result.output,
            "solution_comparison": solution_result.output,
            "sections": sections,
            "scores": scoring_result.output,
            "step_summaries": step_summaries,
        }

    def run_revision_workflow(self, payload: dict, base_section: dict) -> dict:
        workflow_id = str(uuid.uuid4())
        context = AgentContext(workflow_id=workflow_id)
        planner_result = self.agent_registry["planner"].run(
            {
                "request_text": payload.get("instruction", ""),
                "user_instruction": payload["instruction"],
                "section_key": base_section["section_key"],
                "target_sections": [base_section["section_key"]],
            },
            context,
        )
        retrieval_result = self.agent_registry["retrieval"].run(
            {
                "query": payload["instruction"],
                "section_type": base_section["section_key"],
                "solution_type": payload.get("solution_type"),
                "top_k": 5,
            },
            context,
        )
        revision_result = self.agent_registry["revision"].run(
            {
                "section_key": base_section["section_key"],
                "base_text": base_section["draft_text"],
                "instruction": payload["instruction"],
                "requirements": payload.get("requirements", []),
                "evidence": retrieval_result.output["results"],
            },
            context,
        )
        validation_result = self.agent_registry["validation"].run(
            {
                "draft_text": revision_result.output["draft_text"],
                "requirements": payload.get("requirements", []),
            },
            context,
        )
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "plan": planner_result.output,
            "retrieval": retrieval_result.output,
            "revision": revision_result.output,
            "validation": validation_result.output,
        }

    def run_intent_detection_workflow(self, payload: dict) -> dict:
        workflow_id = str(uuid.uuid4())
        context = AgentContext(workflow_id=workflow_id)
        result = self.agent_registry["intent_detection"].run(payload, context)
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "client_overview": result.output.get("client_overview", {}),
            "buyer_readiness": result.output.get("buyer_readiness", {}),
            "product_fit": result.output.get("product_fit", {}),
            "summary": result.summary,
        }

    def run_market_research_workflow(self, payload: dict) -> dict:
        workflow_id = str(uuid.uuid4())
        context = AgentContext(workflow_id=workflow_id)
        result = self.agent_registry["market_research"].run(payload, context)
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "rows": result.output.get("rows", []),
            "offerings": result.output.get("offerings", []),
            "industry": result.output.get("industry"),
            "summary": result.summary,
        }

    def run_document_match_workflow(self, payload: dict) -> dict:
        workflow_id = str(uuid.uuid4())
        context = AgentContext(workflow_id=workflow_id)
        request_result = self.agent_registry["request_structuring"].run(
            {
                "request_text": payload["request_text"],
                "solution_type": payload.get("solution_type"),
            },
            context,
        )
        retrieval_result = self.agent_registry["retrieval"].run(
            {
                "query": payload["request_text"],
                "solution_type": request_result.output["solution_type"],
                "top_k": 5,
            },
            context,
        )
        solution_result = self.agent_registry["solution_comparison"].run(request_result.output, context)
        scoring_result = self.agent_registry["scoring"].run(
            {
                "document_text": payload["document_text"],
                "requirements": request_result.output["requirements"],
                "solution_type": request_result.output["solution_type"],
                "retrieval_score_hint": 0.75,
                "matched_evidence": retrieval_result.output["results"],
            },
            context,
        )
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "request": request_result.output,
            "solution_comparison": solution_result.output,
            "retrieval": retrieval_result.output,
            "scores": scoring_result.output,
        }
