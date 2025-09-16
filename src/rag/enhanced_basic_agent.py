"""
Enhanced Basic RAG agent that can search both documents and structured drug data.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from loguru import logger

from src.models.entities import Document, Drug, Company, ClinicalTrial
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
    """Retrieve relevant documents from the database."""
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
    
    return results


def _search_drugs(db: Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for drugs in the database."""
    query_lower = query.lower()
    drugs = []
    
    # Search by generic name, brand name, or company
    drug_query = db.query(Drug).join(Company)
    
    # Add search filters
    if any(company in query_lower for company in ['merck', 'bristol', 'roche', 'pfizer', 'novartis']):
        if 'merck' in query_lower:
            drug_query = drug_query.filter(Company.name.ilike('%Merck%'))
        elif 'bristol' in query_lower or 'bms' in query_lower:
            drug_query = drug_query.filter(Company.name.ilike('%Bristol%'))
        elif 'roche' in query_lower:
            drug_query = drug_query.filter(Company.name.ilike('%Roche%'))
        elif 'pfizer' in query_lower:
            drug_query = drug_query.filter(Company.name.ilike('%Pfizer%'))
        elif 'novartis' in query_lower:
            drug_query = drug_query.filter(Company.name.ilike('%Novartis%'))
    else:
        # Search by drug name
        drug_query = drug_query.filter(
            (Drug.generic_name.ilike(f'%{query}%')) |
            (Drug.brand_name.ilike(f'%{query}%'))
        )
    
    # Get results
    drug_results = drug_query.limit(limit).all()
    
    for drug in drug_results:
        # Get targets
        targets = '; '.join([dt.target.name for dt in drug.targets]) if drug.targets else ''
        
        # Get indications
        indications = '; '.join([di.indication.name for di in drug.indications]) if drug.indications else ''
        
        drugs.append({
            'generic_name': drug.generic_name,
            'brand_name': drug.brand_name or '',
            'company': drug.company.name if drug.company else '',
            'drug_class': drug.drug_class or '',
            'target': targets,
            'mechanism': drug.mechanism_of_action or '',
            'indication': indications,
            'fda_approved': drug.fda_approval_status,
            'approval_date': drug.fda_approval_date.strftime('%Y/%m') if drug.fda_approval_date else '',
            'nct_codes': drug.nct_codes or []
        })
    
    return drugs


def _search_clinical_trials(db: Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for clinical trials in the database."""
    query_lower = query.lower()
    trials = []
    
    # Search by NCT ID, title, or drug name
    trial_query = db.query(ClinicalTrial)
    
    if query_lower.startswith('nct'):
        trial_query = trial_query.filter(ClinicalTrial.nct_id.ilike(f'%{query}%'))
    else:
        trial_query = trial_query.filter(
            (ClinicalTrial.title.ilike(f'%{query}%')) |
            (ClinicalTrial.nct_id.ilike(f'%{query}%'))
        )
    
    trial_results = trial_query.limit(limit).all()
    
    for trial in trial_results:
        trials.append({
            'nct_id': trial.nct_id,
            'title': trial.title,
            'status': trial.status or '',
            'phase': trial.phase or '',
            'sponsor': trial.sponsor.name if trial.sponsor else '',
            'drug': trial.drug.generic_name if trial.drug else ''
        })
    
    return trials


class EnhancedBasicRAGAgent:
    """Enhanced Basic RAG agent that searches both documents and structured data."""
    
    def __init__(self, provider: BaseLLMProvider, cache_ttl_hours: int = 24):
        self.provider = provider
        self.cache_manager = RAGCacheManager(cache_ttl_hours)
        logger.info(f"EnhancedBasicRAGAgent initialized with {type(provider).__name__}")
    
    def answer(self, db: Session, question: str, k: int = 5) -> Dict[str, Any]:
        """Answer a question using both document and structured data."""
        try:
            # Check cache first
            cached_result = self.cache_manager.get_cached_result(db, question)
            if cached_result:
                logger.info(f"Returning cached result for query: {question[:50]}...")
                return {
                    "answer": cached_result["answer"],
                    "citations": cached_result.get("citations", []),
                    "drugs": cached_result.get("drugs", []),
                    "trials": cached_result.get("trials", [])
                }
            
            # Retrieve relevant documents
            documents = _simple_retrieve(db, question, k)
            logger.info(f"Retrieved {len(documents)} documents for query: {question[:50]}...")
            
            # Search structured data
            drugs = _search_drugs(db, question, 5)
            trials = _search_clinical_trials(db, question, 5)
            
            logger.info(f"Found {len(drugs)} drugs and {len(trials)} trials for query: {question[:50]}...")
            
            # Create context
            context = self._format_context(documents, drugs, trials)
            
            # Generate answer using provider
            system_prompt = """
            You are a specialized oncology and cancer research assistant focused on biopartnering insights.
            Provide accurate, evidence-based responses about cancer therapeutics, immunotherapy, and targeted therapies.
            Focus on actionable insights for biopharmaceutical partnerships.
            
            Use the provided context to answer questions about:
            - Cancer drugs and their mechanisms of action
            - Clinical trials and their status
            - Company drug pipelines
            - Biopartnering opportunities
            - FDA approval status and dates
            """
            
            user_prompt = f"""
            Context:
            {context}
            
            Question: {question}
            
            Please provide a comprehensive answer based on the context provided.
            If you mention specific drugs, include their company, drug class, and key details.
            If you mention clinical trials, include NCT IDs and status.
            """
            
            # Generate response
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            llm_response = self.provider.chat(messages)
            response = llm_response.content
            
            # Create citations
            citations = self._create_citations(documents)
            
            # Store result in cache
            self.cache_manager.store_cached_result(
                db, question, documents, response, citations
            )
            
            return {
                "answer": response,
                "citations": citations,
                "drugs": drugs,
                "trials": trials
            }
            
        except Exception as e:
            logger.error(f"Error in EnhancedBasicRAGAgent.answer: {e}")
            return {
                "answer": f"Error generating response: {e}",
                "citations": [],
                "drugs": [],
                "trials": []
            }
    
    def _format_context(self, documents: List[RetrievedDoc], drugs: List[Dict[str, Any]], trials: List[Dict[str, Any]]) -> str:
        """Format documents, drugs, and trials as context."""
        context_parts = []
        
        # Add document context
        if documents:
            context_parts.append("=== DOCUMENTS ===")
            for i, doc in enumerate(documents, 1):
                context_parts.append(
                    f"[Document {i}] {doc.title} | {doc.source_type} | {doc.url}\n"
                    f"{doc.content}\n"
                )
        
        # Add drug context
        if drugs:
            context_parts.append("=== DRUGS ===")
            for drug in drugs:
                context_parts.append(
                    f"Drug: {drug['generic_name']} ({drug['brand_name']})\n"
                    f"Company: {drug['company']}\n"
                    f"Class: {drug['drug_class']}\n"
                    f"Target: {drug['target']}\n"
                    f"Mechanism: {drug['mechanism']}\n"
                    f"Indication: {drug['indication']}\n"
                    f"FDA Approved: {drug['fda_approved']}\n"
                    f"Approval Date: {drug['approval_date']}\n"
                    f"NCT Codes: {', '.join(drug['nct_codes'])}\n"
                )
        
        # Add trial context
        if trials:
            context_parts.append("=== CLINICAL TRIALS ===")
            for trial in trials:
                context_parts.append(
                    f"Trial: {trial['title']}\n"
                    f"NCT ID: {trial['nct_id']}\n"
                    f"Status: {trial['status']}\n"
                    f"Phase: {trial['phase']}\n"
                    f"Sponsor: {trial['sponsor']}\n"
                    f"Drug: {trial['drug']}\n"
                )
        
        return "\n".join(context_parts)
    
    def _create_citations(self, documents: List[RetrievedDoc]) -> List[Dict[str, str]]:
        """Create citations from retrieved documents."""
        citations = []
        for i, doc in enumerate(documents, 1):
            citations.append({
                "label": f"[Doc {i}]",
                "title": doc.title or "Document",
                "url": doc.url
            })
        return citations


def create_enhanced_basic_rag_agent(provider: BaseLLMProvider, cache_ttl_hours: int = 24) -> EnhancedBasicRAGAgent:
    """Create an enhanced basic RAG agent."""
    return EnhancedBasicRAGAgent(provider, cache_ttl_hours)
