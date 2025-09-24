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
from src.rag.ground_truth_loader import ground_truth_loader


@dataclass
class RetrievedDoc:
    id: int
    title: Optional[str]
    url: str
    content: str
    source_type: str


def _simple_retrieve(db: Session, query: str, limit: int = 5) -> List[RetrievedDoc]:
    """Retrieve relevant documents from the database with improved ranking."""
    query_lower = query.lower()
    
    # Get all matching documents
    all_docs = db.query(Document).filter(Document.content.ilike(f'%{query_lower}%')).all()
    
    # If no exact matches, try broader search with individual words
    if not all_docs:
        words = query_lower.split()
        for word in words:
            if len(word) > 3:  # Only search for words longer than 3 characters
                word_docs = db.query(Document).filter(Document.content.ilike(f'%{word}%')).all()
                for d in word_docs:
                    if not any(r.id == d.id for r in all_docs):  # Avoid duplicates
                        all_docs.append(d)
    
    # Rank documents by relevance and quality
    def rank_document(doc):
        score = 0
        
        # Prioritize high-quality sources
        if doc.source_type == 'fda_drug_approval':
            score += 100
        elif doc.source_type == 'drugs_com_profile':
            score += 80
        elif doc.source_type == 'fda_comprehensive_approval':
            score += 90
        elif doc.source_type == 'clinical_trial':
            score += 60
        elif doc.source_type == 'drug_interactions':
            score += 70
        else:
            score += 30
        
        # Boost score for exact title matches
        if query_lower in doc.title.lower():
            score += 50
        
        # Boost score for multiple word matches
        word_matches = sum(1 for word in query_lower.split() if word in doc.content.lower())
        score += word_matches * 10
        
        # Boost score for longer, more comprehensive content
        if len(doc.content) > 5000:
            score += 20
        elif len(doc.content) > 1000:
            score += 10
        
        return score
    
    # Sort by relevance score (highest first)
    ranked_docs = sorted(all_docs, key=rank_document, reverse=True)
    
    # Convert to RetrievedDoc format
    results = []
    for d in ranked_docs[:limit]:
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
            'drug': trial.drug.generic_name if trial.drug else '',
            'source': 'pipeline'
        })
    
    return trials


def _search_ground_truth_drugs(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for drugs in ground truth data."""
    return ground_truth_loader.search_drugs(query, limit)


def _search_ground_truth_companies(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for companies in ground truth data."""
    return ground_truth_loader.search_companies(query, limit)


def _search_ground_truth_targets(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for targets in ground truth data."""
    return ground_truth_loader.search_targets(query, limit)


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
                    "trials": cached_result.get("trials", []),
                    "companies": cached_result.get("companies", []),
                    "targets": cached_result.get("targets", []),
                    "data_sources": cached_result.get("data_sources", {})
                }
            
            # Retrieve relevant documents
            documents = _simple_retrieve(db, question, k)
            logger.info(f"Retrieved {len(documents)} documents for query: {question[:50]}...")
            
            # Search structured data (pipeline)
            pipeline_drugs = _search_drugs(db, question, 5)
            pipeline_trials = _search_clinical_trials(db, question, 5)
            
            # Search ground truth data (prioritized)
            gt_drugs = _search_ground_truth_drugs(question, 5)
            gt_companies = _search_ground_truth_companies(question, 3)
            gt_targets = _search_ground_truth_targets(question, 3)
            
            # Combine and prioritize ground truth data
            all_drugs = gt_drugs + pipeline_drugs
            all_trials = pipeline_trials  # Ground truth trials are embedded in drug data
            
            logger.info(f"Found {len(gt_drugs)} GT drugs, {len(pipeline_drugs)} pipeline drugs, {len(gt_companies)} GT companies, {len(gt_targets)} GT targets for query: {question[:50]}...")
            
            # Create enhanced context with ground truth data
            context = self._format_enhanced_context(documents, all_drugs, all_trials, gt_companies, gt_targets)
            
            # Generate answer using provider
            system_prompt = """
            You are a specialized oncology and cancer research assistant focused on biopartnering insights.
            Provide accurate, evidence-based responses about cancer therapeutics, immunotherapy, and targeted therapies.
            Focus on actionable insights for biopharmaceutical partnerships.
            
            You have access to both validated ground truth data and real-time pipeline data:
            - Ground truth data is curated, validated, and includes business context (ticket numbers, priorities)
            - Pipeline data is real-time but may be less comprehensive
            
            Use the provided context to answer questions about:
            - Cancer drugs and their mechanisms of action
            - Clinical trials and their status
            - Company drug pipelines and business priorities
            - Biopartnering opportunities with ticket-based prioritization
            - FDA approval status and dates
            - Target analysis and competitive landscape
            
            When mentioning companies, include their business priority level and ticket numbers when available.
            Prioritize ground truth data for accuracy, but supplement with pipeline data for completeness.
            
            IMPORTANT: At the end of your response, clearly indicate your data source:
            - If you used the provided context documents/database: "📊 Data Source: Internal Database"
            - If you relied on general knowledge: "🌐 Data Source: Public Information"
            """
            
            user_prompt = f"""
            Context:
            {context}
            
            Question: {question}
            
            Please provide a comprehensive answer based on the context provided.
            If you mention specific drugs, include their company, drug class, and key details.
            If you mention clinical trials, include NCT IDs and status.
            
            DATA SOURCE GUIDANCE:
            - If the context contains relevant information about the question, use it and indicate "📊 Data Source: Internal Database"
            - If the context is empty or doesn't contain relevant information, you may use general knowledge but MUST indicate "🌐 Data Source: Public Information"
            - Always be transparent about your data source at the end of your response.
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
                "drugs": all_drugs,
                "trials": all_trials,
                "companies": gt_companies,
                "targets": gt_targets,
                "data_sources": {
                    "ground_truth_drugs": len(gt_drugs),
                    "pipeline_drugs": len(pipeline_drugs),
                    "ground_truth_companies": len(gt_companies),
                    "ground_truth_targets": len(gt_targets),
                    "documents": len(documents)
                }
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
    
    def _format_enhanced_context(self, documents: List[RetrievedDoc], drugs: List[Dict[str, Any]], 
                                trials: List[Dict[str, Any]], companies: List[Dict[str, Any]], 
                                targets: List[Dict[str, Any]]) -> str:
        """Format enhanced context with ground truth data and business context."""
        context_parts = []
        
        # Add ground truth companies (business context)
        if companies:
            context_parts.append("=== BUSINESS CONTEXT (GROUND TRUTH) ===")
            for company in companies:
                context_parts.append(
                    f"Company: {company['partner']}\n"
                    f"Business Priority: {company['business_priority']}\n"
                    f"Total Tickets: {company['total_tickets']}\n"
                    f"Drug Portfolio: {company['drug_count']} drugs\n"
                    f"FDA Approved: {company['fda_approved_count']} drugs\n"
                    f"Unique Targets: {company['unique_targets']}\n"
                    f"Data Quality: {company['data_quality']}\n"
                )
        
        # Add ground truth targets
        if targets:
            context_parts.append("=== TARGET ANALYSIS (GROUND TRUTH) ===")
            for target in targets:
                context_parts.append(
                    f"Target: {target['target']}\n"
                    f"Drugs Targeting: {target['drug_count']}\n"
                    f"Companies: {target['company_count']}\n"
                    f"FDA Approved: {target['fda_approved_count']}\n"
                    f"Business Priority: {target['business_priority']}\n"
                    f"Data Quality: {target['data_quality']}\n"
                )
        
        # Add ground truth drugs (prioritized)
        gt_drugs = [d for d in drugs if d.get('source') == 'ground_truth']
        if gt_drugs:
            context_parts.append("=== VALIDATED DRUGS (GROUND TRUTH) ===")
            for drug in gt_drugs:
                context_parts.append(
                    f"Drug: {drug['generic_name']} ({drug['brand_name']})\n"
                    f"Company: {drug['partner']}\n"
                    f"Business Priority: {drug['business_priority']}\n"
                    f"Tickets: {drug['tickets']}\n"
                    f"FDA Approval: {drug['fda_approval']}\n"
                    f"Drug Class: {drug['drug_class']}\n"
                    f"Target: {drug['target']}\n"
                    f"Mechanism: {drug['mechanism']}\n"
                    f"Indication: {drug['indication_approved']}\n"
                    f"Clinical Trials: {drug['current_clinical_trials']}\n"
                    f"Data Quality: {drug['data_quality']}\n"
                )
        
        # Add pipeline drugs (supplementary)
        pipeline_drugs = [d for d in drugs if d.get('source') != 'ground_truth']
        if pipeline_drugs:
            context_parts.append("=== PIPELINE DRUGS (REAL-TIME) ===")
            for drug in pipeline_drugs:
                context_parts.append(
                    f"Drug: {drug['generic_name']} ({drug['brand_name']})\n"
                    f"Company: {drug['company']}\n"
                    f"Class: {drug['drug_class']}\n"
                    f"Target: {drug['target']}\n"
                    f"Mechanism: {drug['mechanism']}\n"
                    f"FDA Approved: {drug['fda_approved']}\n"
                    f"Source: Pipeline\n"
                )
        
        # Add document context
        if documents:
            context_parts.append("=== DOCUMENTS ===")
            for i, doc in enumerate(documents, 1):
                context_parts.append(
                    f"[Document {i}] {doc.title} | {doc.source_type} | {doc.url}\n"
                    f"{doc.content}\n"
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
                    f"Source: {trial.get('source', 'pipeline')}\n"
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
    
    def validate_response_accuracy(self, db: Session, question: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RAG response accuracy using ground truth data."""
        validation_results = {
            'validation_status': 'completed',
            'ground_truth_matches': 0,
            'pipeline_matches': 0,
            'discrepancies': [],
            'confidence_score': 0.0,
            'recommendations': []
        }
        
        try:
            # Validate drugs
            pipeline_drugs = [d for d in response_data.get('drugs', []) if d.get('source') != 'ground_truth']
            gt_drugs = [d for d in response_data.get('drugs', []) if d.get('source') == 'ground_truth']
            
            validation_results['ground_truth_matches'] = len(gt_drugs)
            validation_results['pipeline_matches'] = len(pipeline_drugs)
            
            # Check for discrepancies between pipeline and ground truth
            for pipeline_drug in pipeline_drugs:
                drug_name = pipeline_drug.get('generic_name', '').lower()
                
                # Find matching ground truth entry
                gt_match = ground_truth_loader.search_drugs(drug_name, 1)
                
                if gt_match:
                    gt_drug = gt_match[0]
                    discrepancies = []
                    
                    # Check for discrepancies in key fields
                    if pipeline_drug.get('company', '').lower() != gt_drug.get('partner', '').lower():
                        discrepancies.append(f"Company mismatch: Pipeline={pipeline_drug.get('company')}, GT={gt_drug.get('partner')}")
                    
                    if pipeline_drug.get('drug_class', '') != gt_drug.get('drug_class', ''):
                        discrepancies.append(f"Drug class mismatch: Pipeline={pipeline_drug.get('drug_class')}, GT={gt_drug.get('drug_class')}")
                    
                    if pipeline_drug.get('target', '') != gt_drug.get('target', ''):
                        discrepancies.append(f"Target mismatch: Pipeline={pipeline_drug.get('target')}, GT={gt_drug.get('target')}")
                    
                    if discrepancies:
                        validation_results['discrepancies'].append({
                            'drug': drug_name,
                            'discrepancies': discrepancies,
                            'pipeline_data': pipeline_drug,
                            'ground_truth_data': gt_drug
                        })
            
            # Calculate confidence score
            total_drugs = len(pipeline_drugs) + len(gt_drugs)
            if total_drugs > 0:
                gt_ratio = len(gt_drugs) / total_drugs
                discrepancy_penalty = len(validation_results['discrepancies']) * 0.1
                validation_results['confidence_score'] = max(0.0, gt_ratio - discrepancy_penalty)
            
            # Generate recommendations
            if validation_results['confidence_score'] < 0.7:
                validation_results['recommendations'].append("Consider prioritizing ground truth data for higher accuracy")
            
            if validation_results['discrepancies']:
                validation_results['recommendations'].append("Review discrepancies between pipeline and ground truth data")
            
            if len(gt_drugs) == 0 and len(pipeline_drugs) > 0:
                validation_results['recommendations'].append("No ground truth matches found - consider expanding ground truth coverage")
            
        except Exception as e:
            logger.error(f"Error in response validation: {e}")
            validation_results['validation_status'] = 'error'
            validation_results['error'] = str(e)
        
        return validation_results


def create_enhanced_basic_rag_agent(provider: BaseLLMProvider, cache_ttl_hours: int = 24) -> EnhancedBasicRAGAgent:
    """Create an enhanced basic RAG agent."""
    return EnhancedBasicRAGAgent(provider, cache_ttl_hours)
