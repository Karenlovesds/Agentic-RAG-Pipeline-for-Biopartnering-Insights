"""Synchronous wrapper for Simple Pydantic AI agent to work with Streamlit."""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from .simple_pydantic_agent import SimplePydanticRAGAgent
from .models import (
    RAGResponse, DrugInfo, ClinicalTrialInfo, BiopartneringInsight,
    DrugSearchQuery, ClinicalTrialSearchQuery, BiopartneringQuery
)
from .provider import BaseLLMProvider


class OllamaSyncRAGAgent:
    """Synchronous wrapper for SimplePydanticRAGAgent to work with Streamlit."""
    
    def __init__(self, provider: BaseLLMProvider, cache_ttl_hours: int = 24):
        self.async_agent = SimplePydanticRAGAgent(provider, cache_ttl_hours)
        self.provider = provider
        logger.info(f"OllamaSyncRAGAgent initialized with {type(provider).__name__}")
    
    def answer(self, db: Session, question: str, k: int = 5) -> RAGResponse:
        """Synchronous answer method."""
        try:
            return self.async_agent.answer(db, question, k)
        except Exception as e:
            logger.error(f"Error in OllamaSyncRAGAgent.answer: {e}")
            return RAGResponse(
                answer=f"Error generating answer: {e}",
                confidence=0.0,
                citations=[],
                cached=False
            )
    
    def search_drugs(self, db: Session, query: DrugSearchQuery) -> List[DrugInfo]:
        """Synchronous drug search method."""
        try:
            return self.async_agent.search_drugs(db, query)
        except Exception as e:
            logger.error(f"Error in OllamaSyncRAGAgent.search_drugs: {e}")
            return []
    
    def search_trials(self, db: Session, query: ClinicalTrialSearchQuery) -> List[ClinicalTrialInfo]:
        """Synchronous trial search method."""
        try:
            return self.async_agent.search_trials(db, query)
        except Exception as e:
            logger.error(f"Error in OllamaSyncRAGAgent.search_trials: {e}")
            return []
    
    def generate_biopartnering_insights(self, db: Session, query: BiopartneringQuery) -> List[BiopartneringInsight]:
        """Synchronous biopartnering insights method."""
        try:
            return self.async_agent.generate_biopartnering_insights(db, query)
        except Exception as e:
            logger.error(f"Error in OllamaSyncRAGAgent.generate_biopartnering_insights: {e}")
            return []


def create_ollama_sync_rag_agent(provider: BaseLLMProvider, cache_ttl_hours: int = 24) -> OllamaSyncRAGAgent:
    """Factory function to create an OllamaSyncRAGAgent."""
    return OllamaSyncRAGAgent(provider, cache_ttl_hours)
