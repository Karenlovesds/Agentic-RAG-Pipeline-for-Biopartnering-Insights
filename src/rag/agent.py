"""Minimal RAG agent over Documents using a pluggable LLM provider."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from loguru import logger

from src.models.entities import Document
from src.rag.provider import BaseLLMProvider


@dataclass
class RetrievedDoc:
    id: int
    title: Optional[str]
    url: str
    content: str
    source_type: str


def _simple_retrieve(db: Session, query: str, limit: int = 5) -> List[RetrievedDoc]:
    # Very simple retrieval: filter by substring and order by recency
    q = db.query(Document).filter(Document.content.contains(query)).order_by(Document.created_at.desc()).limit(limit)
    results: List[RetrievedDoc] = []
    for d in q.all():
        results.append(
            RetrievedDoc(
                id=d.id,
                title=d.title,
                url=d.source_url,
                content=d.content[:4000],  # cap prompt size
                source_type=d.source_type,
            )
        )
    return results


class RAGAgent:
    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def answer(self, db: Session, question: str, k: int = 5) -> Dict[str, Any]:
        retrieved = _simple_retrieve(db, question, limit=k)
        logger.info(f"RAG retrieved {len(retrieved)} docs")

        context_blocks = []
        citations = []
        for i, r in enumerate(retrieved, start=1):
            context_blocks.append(f"[Doc {i}] {r.title or 'Untitled'} | {r.source_type} | {r.url}\n{r.content}")
            citations.append({"label": f"Doc {i}", "title": r.title or "Untitled", "url": r.url, "source": r.source_type})

        system = (
            "You are a biomedical RAG assistant. Use only the provided context to answer. "
            "Always include concise bullet points and a short cited list like [Doc 1], [Doc 2]."
        )
        context = "\n\n".join(context_blocks) if context_blocks else "No context found."
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"},
        ]
        resp = self.provider.chat(messages)
        return {"answer": resp.content, "citations": citations}


