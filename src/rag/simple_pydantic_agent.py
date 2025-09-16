"""Simplified Pydantic AI-based RAG agent for biopartnering insights."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from .models import (
    RAGResponse, DrugInfo, ClinicalTrialInfo, BiopartneringInsight, 
    Citation, DrugSearchQuery, ClinicalTrialSearchQuery, BiopartneringQuery
)
from .provider import BaseLLMProvider
from .cache_manager import RAGCacheManager
from ..models.entities import Document, Drug, ClinicalTrial, Company


class SimplePydanticRAGAgent:
    """Simplified RAG agent with structured responses using Pydantic models."""
    
    def __init__(self, provider: BaseLLMProvider, cache_ttl_hours: int = 24):
        self.provider = provider
        self.cache_manager = RAGCacheManager(cache_ttl_hours)
        logger.info(f"SimplePydanticRAGAgent initialized with {type(provider).__name__}")
    
    def _retrieve_documents(self, db: Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant documents from the database."""
        query_lower = query.lower()
        
        # Try exact content match first
        docs = db.query(Document).filter(
            Document.content.contains(query_lower)
        ).order_by(Document.created_at.desc()).limit(limit).all()
        
        # If no exact matches, try broader search
        if not docs:
            words = [word for word in query_lower.split() if len(word) > 3]
            for word in words:
                docs = db.query(Document).filter(
                    Document.content.contains(word)
                ).order_by(Document.created_at.desc()).limit(limit).all()
                if docs:
                    break
        
        # If still no results, return most recent documents
        if not docs:
            docs = db.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
        
        # Convert to dict format
        return [
            {
                "id": doc.id,
                "title": doc.title or "Untitled",
                "content": doc.content[:4000],  # Cap content size
                "url": doc.source_url,
                "source_type": doc.source_type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in docs
        ]
    
    def _create_citations(self, documents: List[Dict[str, Any]]) -> List[Citation]:
        """Create citation objects from retrieved documents."""
        citations = []
        for i, doc in enumerate(documents, 1):
            citations.append(Citation(
                label=f"Doc {i}",
                title=doc["title"],
                url=doc["url"],
                source=doc["source_type"]
            ))
        return citations
    
    def _extract_drugs_from_content(self, content: str) -> List[DrugInfo]:
        """Extract drug information from content using simple pattern matching."""
        drugs = []
        
        # Look for drug patterns in content
        lines = content.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['drug', 'medication', 'therapy', 'treatment', 'pembrolizumab', 'keytruda', 'opdivo', 'nivolumab']):
                # Simple extraction - in a real implementation, you'd use more sophisticated NLP
                if 'pembrolizumab' in line.lower():
                    drugs.append(DrugInfo(
                        generic_name="Pembrolizumab",
                        brand_name="KEYTRUDA",
                        company="Merck & Co.",
                        drug_class="Monoclonal antibody",
                        target="PD-1",
                        mechanism="Immune checkpoint inhibitor",
                        indication="Various cancers",
                        development_stage="Approved"
                    ))
                elif 'nivolumab' in line.lower():
                    drugs.append(DrugInfo(
                        generic_name="Nivolumab",
                        brand_name="OPDIVO",
                        company="Bristol Myers Squibb",
                        drug_class="Monoclonal antibody",
                        target="PD-1",
                        mechanism="Immune checkpoint inhibitor",
                        indication="Various cancers",
                        development_stage="Approved"
                    ))
        
        return drugs
    
    def _extract_trials_from_content(self, content: str) -> List[ClinicalTrialInfo]:
        """Extract clinical trial information from content."""
        trials = []
        
        # Look for NCT patterns
        import re
        nct_pattern = r'NCT\d{8}'
        nct_matches = re.findall(nct_pattern, content)
        
        for nct_id in nct_matches:
            trials.append(ClinicalTrialInfo(
                nct_id=nct_id,
                title=f"Clinical trial {nct_id}",
                phase="Unknown",
                status="Unknown",
                condition="Cancer",
                intervention="Drug therapy"
            ))
        
        return trials
    
    def _generate_biopartnering_insights(self, content: str, drugs: List[DrugInfo]) -> List[BiopartneringInsight]:
        """Generate biopartnering insights from content and drugs."""
        insights = []
        
        if drugs:
            # Simple insight generation based on available drugs
            companies = list(set([drug.company for drug in drugs if drug.company]))
            if len(companies) > 1:
                insights.append(BiopartneringInsight(
                    insight_type="collaboration_opportunity",
                    title=f"Potential collaboration between {', '.join(companies)}",
                    description=f"Both companies have drugs in similar therapeutic areas that could benefit from collaboration.",
                    companies_involved=companies,
                    drugs_involved=[drug.generic_name for drug in drugs],
                    therapeutic_area="Oncology",
                    confidence_score=0.7
                ))
        
        return insights
    
    def answer(self, db: Session, question: str, k: int = 5) -> RAGResponse:
        """Answer a question with structured response."""
        try:
            # Check cache first
            cached_result = self.cache_manager.get_cached_result(db, question)
            if cached_result:
                logger.info(f"Returning cached result for query: {question[:50]}...")
                return RAGResponse(
                    answer=cached_result["answer"],
                    confidence=cached_result.get("confidence_score", 0.0) or 0.0,
                    citations=cached_result.get("citations", []),
                    cached=True
                )
            
            # Retrieve relevant documents
            documents = self._retrieve_documents(db, question, k)
            logger.info(f"Retrieved {len(documents)} documents for query: {question[:50]}...")
            
            # Create context
            context = self._format_context(documents)
            
            # Generate answer using provider
            system_prompt = """
            You are a specialized oncology and cancer research assistant focused on biopartnering insights.
            Provide accurate, evidence-based responses about cancer therapeutics, immunotherapy, and targeted therapies.
            Focus on actionable insights for biopharmaceutical partnerships.
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"},
            ]
            
            resp = self.provider.chat(messages)
            answer = resp.content
            
            # Extract structured data
            drugs = self._extract_drugs_from_content(context)
            trials = self._extract_trials_from_content(context)
            insights = self._generate_biopartnering_insights(context, drugs)
            
            # Create citations
            citations = self._create_citations(documents)
            
            # Calculate confidence based on available data
            confidence = min(0.9, 0.5 + (len(drugs) * 0.1) + (len(trials) * 0.05) + (len(insights) * 0.1))
            
            # Store result in cache
            self.cache_manager.store_cached_result(
                db, question, documents, answer, citations
            )
            
            return RAGResponse(
                answer=answer,
                confidence=confidence,
                citations=citations,
                drugs_mentioned=drugs,
                trials_mentioned=trials,
                insights=insights,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"Error in SimplePydanticRAGAgent.answer: {e}")
            return RAGResponse(
                answer=f"Error generating answer: {e}",
                confidence=0.0,
                citations=[],
                cached=False
            )
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents as context for the agent."""
        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(
                f"[Document {i}] {doc['title']} | {doc['source_type']} | {doc['url']}\n"
                f"{doc['content']}\n"
            )
        return "\n".join(context_parts)
    
    def search_drugs(self, db: Session, query: DrugSearchQuery) -> List[DrugInfo]:
        """Search for drugs using structured query."""
        try:
            from ..models.entities import Drug, Company, DrugIndication, Indication
            
            # Build query
            drug_query = db.query(Drug).join(Company)
            
            # Add search filters
            if query.company_filter:
                drug_query = drug_query.filter(Company.name.ilike(f'%{query.company_filter}%'))
            
            if query.drug_class_filter:
                drug_query = drug_query.filter(Drug.drug_class.ilike(f'%{query.drug_class_filter}%'))
            
            if query.indication_filter:
                drug_query = drug_query.join(DrugIndication).join(Indication).filter(
                    Indication.name.ilike(f'%{query.indication_filter}%')
                )
            
            # Add text search
            if query.query:
                drug_query = drug_query.filter(
                    (Drug.generic_name.ilike(f'%{query.query}%')) |
                    (Drug.brand_name.ilike(f'%{query.query}%'))
                )
            
            # Get results
            drug_results = drug_query.limit(query.limit).all()
            
            # Convert to DrugInfo objects
            drugs = []
            for drug in drug_results:
                # Get targets
                targets = '; '.join([dt.target.name for dt in drug.targets]) if drug.targets else ''
                
                # Get indications
                indications = '; '.join([di.indication.name for di in drug.indications]) if drug.indications else ''
                
                drugs.append(DrugInfo(
                    generic_name=drug.generic_name,
                    brand_name=drug.brand_name or '',
                    company=drug.company.name if drug.company else '',
                    drug_class=drug.drug_class or '',
                    target=targets,
                    mechanism=drug.mechanism_of_action or '',
                    indication=indications,
                    development_stage="Approved" if drug.fda_approval_status else "Investigational"
                ))
            
            return drugs
            
        except Exception as e:
            logger.error(f"Error in drug search: {e}")
            return []
    
    def search_trials(self, db: Session, query: ClinicalTrialSearchQuery) -> List[ClinicalTrialInfo]:
        """Search for clinical trials using structured query."""
        try:
            # Retrieve documents
            documents = self._retrieve_documents(db, query.query, query.limit)
            context = self._format_context(documents)
            
            # Extract trials
            trials = self._extract_trials_from_content(context)
            
            # Apply filters
            if query.phase_filter:
                trials = [t for t in trials if t.phase and query.phase_filter.lower() in t.phase.lower()]
            
            if query.status_filter:
                trials = [t for t in trials if t.status and query.status_filter.lower() in t.status.lower()]
            
            return trials[:query.limit]
            
        except Exception as e:
            logger.error(f"Error in trial search: {e}")
            return []
    
    def generate_biopartnering_insights(self, db: Session, query: BiopartneringQuery) -> List[BiopartneringInsight]:
        """Generate biopartnering insights using structured query."""
        try:
            # Retrieve documents
            documents = self._retrieve_documents(db, query.query, 10)
            context = self._format_context(documents)
            
            # Extract drugs and generate insights
            drugs = self._extract_drugs_from_content(context)
            insights = self._generate_biopartnering_insights(context, drugs)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating biopartnering insights: {e}")
            return []


def create_simple_pydantic_rag_agent(provider: BaseLLMProvider, cache_ttl_hours: int = 24) -> SimplePydanticRAGAgent:
    """Factory function to create a SimplePydanticRAGAgent."""
    return SimplePydanticRAGAgent(provider, cache_ttl_hours)
