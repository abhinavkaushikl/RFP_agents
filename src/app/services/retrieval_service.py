from __future__ import annotations

from app.tools.retrieval_tool import RetrievalTool


class RetrievalService:
    def __init__(self, tool: RetrievalTool | None = None) -> None:
        self.tool = tool or RetrievalTool()

    def search(
        self,
        query: str,
        candidate_chunks: list[dict],
        section_type: str | None = None,
        solution_type: str | None = None,
        industry: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        return self.tool.invoke(
            {
                "query": query,
                "section_type": section_type,
                "solution_type": solution_type,
                "industry": industry,
                "top_k": top_k,
                "candidate_chunks": candidate_chunks,
            }
        )
