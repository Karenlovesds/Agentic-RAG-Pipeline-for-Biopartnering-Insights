"""Minimal RAG agent over Documents using a pluggable LLM provider."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from loguru import logger

from src.models.entities import Document
from src.rag.provider import BaseLLMProvider
from src.rag.cache_manager import RAGCacheManager


@dataclass
class RetrievedDoc:
    id: int
    title: Optional[str]
    url: str
    content: str
    source_type: str


def _simple_retrieve(db: Session, query: str, limit: int = 5) -> List[RetrievedDoc]:
    # Simple retrieval: try exact match first, then broader search
    query_lower = query.lower()
    
    # First try: exact content match
    q = db.query(Document).filter(Document.content.contains(query_lower)).order_by(Document.created_at.desc()).limit(limit)
    results = []
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
    
    # If no exact matches, try broader search with individual words
    if not results:
        words = query_lower.split()
        for word in words:
            if len(word) > 3:  # Only search for words longer than 3 characters
                q = db.query(Document).filter(Document.content.contains(word)).order_by(Document.created_at.desc()).limit(limit)
                for d in q.all():
                    if not any(r.id == d.id for r in results):  # Avoid duplicates
                        results.append(
                            RetrievedDoc(
                                id=d.id,
                                title=d.title,
                                url=d.source_url,
                                content=d.content[:4000],
                                source_type=d.source_type,
                            )
                        )
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
    
    # If still no results, return most recent documents
    if not results:
        q = db.query(Document).order_by(Document.created_at.desc()).limit(limit)
        for d in q.all():
            results.append(
                RetrievedDoc(
                    id=d.id,
                    title=d.title,
                    url=d.source_url,
                    content=d.content[:4000],
                    source_type=d.source_type,
                )
            )
    
    return results[:limit]


class RAGAgent:
    def __init__(self, provider: BaseLLMProvider, cache_ttl_hours: int = 24):
        self.provider = provider
        self.cache_manager = RAGCacheManager(cache_ttl_hours)
        logger.info(f"RAGAgent initialized with caching (TTL: {cache_ttl_hours} hours)")

    def answer(self, db: Session, question: str, k: int = 5) -> Dict[str, Any]:
        # Check cache first
        cached_result = self.cache_manager.get_cached_result(db, question)
        if cached_result:
            logger.info(f"Returning cached result for query: {question[:50]}...")
            return cached_result
        
        # Cache miss - perform retrieval and generation
        logger.info(f"Cache miss for query: {question[:50]}...")
        retrieved = _simple_retrieve(db, question, limit=k)
        logger.info(f"RAG retrieved {len(retrieved)} docs")

        context_blocks = []
        citations = []
        for i, r in enumerate(retrieved, start=1):
            context_blocks.append(f"[Doc {i}] {r.title or 'Untitled'} | {r.source_type} | {r.url}\n{r.content}")
            citations.append({"label": f"Doc {i}", "title": r.title or "Untitled", "url": r.url, "source": r.source_type})

        system = (
            "You are a specialized oncology and cancer research RAG assistant. Focus on cancer therapeutics, "
            "immunotherapy, targeted therapies, clinical trials, and drug development in oncology. "
            "Use only the provided context to answer. Always include concise bullet points and a short cited list like [Doc 1], [Doc 2]. "
            "When discussing cancer drugs, include information about indications, mechanisms of action, side effects, "
            "and clinical trial data when available."
        )
        context = "\n\n".join(context_blocks) if context_blocks else "No context found."
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"},
        ]
        
        try:
            resp = self.provider.chat(messages)
            answer = resp.content
            
            # Store result in cache
            self.cache_manager.store_cached_result(
                db, question, retrieved, answer, citations
            )
            
            return {"answer": answer, "citations": citations, "cached": False}
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {"answer": f"Error generating answer: {e}", "citations": [], "cached": False}


