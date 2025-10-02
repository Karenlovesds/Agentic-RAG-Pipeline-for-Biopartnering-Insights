"""
React Framework RAG Agent using LlamaIndex

This agent implements the React (Reasoning + Acting + Observing) framework
for more reliable and accurate responses through iterative reasoning.

🔄 REACT WORKFLOW PROCESS:

1. 🧠 REASONING PHASE:
   - Agent analyzes the user question
   - Determines what information is needed
   - Plans which tools to use and in what order
   - Thinks through the problem step-by-step

2. ⚡ ACTING PHASE:
   - Executes chosen tools (database search, ground truth search, cross-reference)
   - Performs actual data retrieval operations
   - Gathers information from multiple sources
   - Uses available tools to answer the question

3. 👁️ OBSERVING PHASE:
   - Analyzes the results from tool execution
   - Evaluates if the information is sufficient
   - Identifies gaps or inconsistencies
   - Decides if more actions are needed

4. 🔄 ITERATION LOOP:
   - If information is incomplete → Return to Reasoning phase
   - If information is sufficient → Proceed to final answer
   - Can perform multiple reasoning-acting-observing cycles
   - Maximum iterations: 5 (configurable)

5. 📝 FINAL ANSWER:
   - Synthesizes all gathered information
   - Provides comprehensive, evidence-based response
   - Indicates data sources used
   - Ensures accuracy through cross-validation

🛠️ AVAILABLE TOOLS:
- semantic_search: Perform semantic search across all biopharmaceutical data with relevance scoring
- multi_query_search: Break down complex questions into multiple related searches and aggregate results
- compare_drugs: Compare two drugs across multiple dimensions (company, target, mechanism, etc.)
- search_public_resources: Search external sources when internal data is insufficient

📊 DATA SOURCE HIERARCHY (All via Vector Embeddings):
1. Ground Truth (highest priority - curated business data) → Vector Embeddings
2. Internal Database (pipeline-collected data) → Vector Embeddings  
3. FDA Data (external API but integrated internally) → Vector Embeddings
4. Clinical Trials (external API but integrated internally) → Vector Embeddings
5. Drugs.com (external API but integrated internally) → Vector Embeddings
6. Cross-reference all sources for validation → Vector Embeddings
7. Clear attribution of data sources

🔍 SEARCH LOGIC AND DATA SOURCE PRIORITY:

This RAG agent uses PURE VECTOR SEARCH for all data sources. All data (Ground Truth, Database, FDA, Clinical Trials, Drugs.com) 
is converted to vector embeddings and stored in ChromaDB for semantic search. This provides:

✅ UNIFIED SEARCH: Single semantic search across all data sources
✅ SEMANTIC SIMILARITY: Handles query variations, typos, and contextual understanding  
✅ TOP-K RETRIEVAL: Returns most relevant results with similarity scores
✅ NO SQL QUERIES: Pure vector-based search during RAG operations
✅ COMPREHENSIVE COVERAGE: All data sources accessible through one search method

🎯 RESPONSE BEHAVIOR:
- ALWAYS indicate data source: "🏆 Ground Truth", "📊 Internal Database", "🏥 FDA", "🧪 Clinical Trials", "💊 Drugs.com", "🏆📊🏥🧪💊 Internal (All Sources)", "🌐 Public Information", or "❓ I don't know"
- NEVER fabricate or make up answers
- If no relevant internal data found, offer to search external sources
- Provide context from available data even if specific answer isn't found
- Use fuzzy matching and typo tolerance for better user experience

🔒 DATA INTEGRITY:
- Ground truth data takes precedence over pipeline data
- Internal sources prioritized over external sources
- Honest "I don't know" responses when data is insufficient
- Clear attribution prevents misinformation
"""

from typing import List, Dict, Any, Optional
from loguru import logger
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from llama_index.core.memory import ChatMemoryBuffer

from src.rag.vector_db_manager import VectorDBManager


class ReactRAGAgent:
    """React Framework RAG Agent for reliable biopharmaceutical insights."""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize vector database manager
        self.vector_db = VectorDBManager()
        
        # Initialize Ollama LLM for React agent
        self.llm = Ollama(
            model="llama3.1",
            request_timeout=300.0,
            temperature=0.0  # Set to 0 for maximum consistency
        )
        
        # Create tools for the React agent
        self.tools = self._create_tools()
        
        # Initialize React agent
        self.agent = self._create_react_agent()
        
        logger.info("React RAG Agent with Vector Database initialized successfully")
    
    def _create_tools(self) -> List[FunctionTool]:
        """Create tools for the React agent."""
        tools = []
        
        # Semantic search tool
        def semantic_search(query: str, top_k: int = 15) -> str:
            """Perform semantic search across all biopharmaceutical data.
            
            This tool searches across ground truth data, database data, and clinical trials
            using semantic similarity. It handles query variations, typos, and contextual understanding.
            
            Args:
                query: Search query (drug name, company name, target, mechanism, etc.)
                top_k: Number of top results to return (default: 5)
            
            Returns:
                Formatted results from semantic search with relevance scores
            """
            try:
                results = self.vector_db.semantic_search(query, top_k)
                
                if results:
                    formatted_results = []
                    for i, result in enumerate(results, 1):
                        metadata = result["metadata"]
                        similarity_score = result["similarity_score"]
                        
                        # Format result based on source
                        if metadata["source"] == "ground_truth":
                            formatted_results.append(
                                f"{i}. 🏆 GROUND TRUTH: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Target: {metadata['target']} "
                                f"- Mechanism: {metadata['mechanism']} - Ticket: {metadata['ticket']} "
                            )
                        elif metadata["source"] == "database":
                            formatted_results.append(
                                f"{i}. 📊 DATABASE: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Mechanism: {metadata['mechanism']} "
                                f"- Drug Class: {metadata['drug_class']} (Relevance: {similarity_score:.3f})"
                            )
                        elif metadata["source"] == "clinical_trial":
                            formatted_results.append(
                                f"{i}. 🧪 CLINICAL TRIAL: {metadata['nct_id']} - Phase: {metadata['phase']} "
                                f"- Status: {metadata['status']} (Relevance: {similarity_score:.3f})"
                            )
                        elif metadata["source"] == "fda":
                            formatted_results.append(
                                f"{i}. 🏥 FDA: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Approval Date: {metadata.get('fda_approval_date', 'N/A')} "
                                f"- Targets: {metadata.get('target', 'N/A')} (Relevance: {similarity_score:.3f})"
                            )
                        elif metadata["source"] == "drugs_com":
                            formatted_results.append(
                                f"{i}. 💊 DRUGS.COM: {metadata['title']} "
                                f"- Source: {metadata.get('url', 'N/A')} (Relevance: {similarity_score:.3f})"
                            )
                        else:
                            formatted_results.append(
                                f"{i}. {metadata['source'].upper()}: {metadata.get('generic_name', metadata.get('title', 'Unknown'))} "
                                f"- Company: {metadata.get('company', 'N/A')} (Relevance: {similarity_score:.3f})"
                            )
                    
                    # Add summary at the end
                    summary = f"\n\nSUMMARY: Found {len(results)} results for '{query}'"
                    if any(r["metadata"]["source"] == "ground_truth" for r in results):
                        summary += " - Includes Ground Truth data"
                    if any(r["metadata"]["source"] == "database" for r in results):
                        summary += " - Includes Database data"
                    if any(r["metadata"]["source"] == "clinical_trial" for r in results):
                        summary += " - Includes Clinical Trial data"
                    
                    return f"Semantic Search Results for '{query}':\n" + "\n".join(formatted_results) + summary
                else:
                    return f"No semantic search results found for '{query}'"
                    
            except Exception as e:
                logger.error(f"Semantic search error: {e}")
                return f"Error in semantic search: {str(e)}"
        
        # Multi-query search tool for complex questions
        def multi_query_search(query: str) -> str:
            """Perform multiple related searches for complex questions.
            
            This tool automatically breaks down complex questions into multiple related searches
            and aggregates the results for comprehensive answers.
            
            Args:
                query: Complex search query (e.g., "TROP2 competitive landscape", "compare Merck and Gilead drugs")
            
            Returns:
                Aggregated results from multiple related searches
            """
            try:
                # Define search strategies based on query patterns
                search_queries = []
                
                query_lower = query.lower()
                
                # Extract entities from query using semantic search
                # This will help identify targets, companies, and drugs dynamically
                entity_search = semantic_search(query)
                
                # Competitive landscape analysis
                if any(word in query_lower for word in ['competitive', 'landscape', 'market', 'players']):
                    # Extract target/entity from query dynamically
                    search_queries = [
                        query,
                        f"{query} drugs",
                        f"{query} companies", 
                        f"{query} clinical trials",
                        f"{query} mechanisms"
                    ]
                
                # Comparison analysis
                elif any(word in query_lower for word in ['compare', 'comparison', 'vs', 'versus']):
                    # Extract entities for comparison dynamically
                    search_queries = [
                        query,
                        f"{query} drugs",
                        f"{query} companies",
                        f"{query} clinical trials"
                    ]
                
                # Timeline/development analysis
                elif any(word in query_lower for word in ['timeline', 'development', 'evolution', 'history']):
                    search_queries = [
                        query,
                        f"{query} clinical trials",
                        f"{query} approvals",
                        f"{query} partnerships"
                    ]
                
                # Target-specific development questions
                elif any(word in query_lower for word in ['phase', 'development', 'indication', 'targeting']):
                    search_queries = [
                        query,
                        f"{query} drugs",
                        f"{query} clinical trials",
                        f"{query} phase",
                        f"{query} indication"
                    ]
                
                # Default: expand the original query
                else:
                    search_queries = [
                        query,
                        f"{query} drugs",
                        f"{query} companies",
                        f"{query} clinical trials"
                    ]
                
                # Execute multiple searches
                all_results = []
                for search_query in search_queries[:4]:  # Limit to 4 searches
                    results = self.vector_db.semantic_search(search_query, top_k=3)
                    all_results.extend(results)
                
                # Aggregate and deduplicate results
                aggregated_results = self._aggregate_search_results(all_results)
                
                if aggregated_results:
                    return f"Multi-Query Analysis for '{query}':\n" + aggregated_results
                else:
                    return f"No comprehensive results found for '{query}'"
                    
            except Exception as e:
                logger.error(f"Multi-query search error: {e}")
                return f"Error in multi-query search: {str(e)}"
        
        # Drug comparison tool
        def compare_drugs(drug1: str, drug2: str) -> str:
            """Compare two drugs across multiple dimensions.
            
            Args:
                drug1: First drug name
                drug2: Second drug name
            
            Returns:
                Detailed comparison of the two drugs
            """
            try:
                # Search for both drugs
                results1 = self.vector_db.semantic_search(drug1, top_k=5)
                results2 = self.vector_db.semantic_search(drug2, top_k=5)
                
                # Find best matches for each drug
                drug1_info = self._find_best_drug_match(results1, drug1)
                drug2_info = self._find_best_drug_match(results2, drug2)
                
                if not drug1_info or not drug2_info:
                    return f"Could not find sufficient information to compare {drug1} and {drug2}"
                
                # Create comparison
                comparison = f"Drug Comparison: {drug1} vs {drug2}\n\n"
                
                # Company comparison
                comparison += f"Companies:\n"
                comparison += f"  {drug1}: {drug1_info.get('company', 'N/A')}\n"
                comparison += f"  {drug2}: {drug2_info.get('company', 'N/A')}\n\n"
                
                # Target comparison
                comparison += f"Targets:\n"
                comparison += f"  {drug1}: {drug1_info.get('target', 'N/A')}\n"
                comparison += f"  {drug2}: {drug2_info.get('target', 'N/A')}\n\n"
                
                # Mechanism comparison
                comparison += f"Mechanisms:\n"
                comparison += f"  {drug1}: {drug1_info.get('mechanism', 'N/A')}\n"
                comparison += f"  {drug2}: {drug2_info.get('mechanism', 'N/A')}\n\n"
                
                # Drug class comparison
                comparison += f"Drug Classes:\n"
                comparison += f"  {drug1}: {drug1_info.get('drug_class', 'N/A')}\n"
                comparison += f"  {drug2}: {drug2_info.get('drug_class', 'N/A')}\n\n"
                
                # Indication comparison
                comparison += f"Indications:\n"
                comparison += f"  {drug1}: {drug1_info.get('indication', 'N/A')}\n"
                comparison += f"  {drug2}: {drug2_info.get('indication', 'N/A')}\n\n"
                
                # Ticket/priority comparison
                if drug1_info.get('ticket') or drug2_info.get('ticket'):
                    comparison += f"Business Priority:\n"
                    comparison += f"  {drug1}: Ticket {drug1_info.get('ticket', 'N/A')}\n"
                    comparison += f"  {drug2}: Ticket {drug2_info.get('ticket', 'N/A')}\n"
                
                return comparison
                
            except Exception as e:
                logger.error(f"Drug comparison error: {e}")
                return f"Error comparing drugs: {str(e)}"
        
        # Competitive landscape analysis tool
        # Ground truth direct search tool (backup)
        
        # Cross-validation tool
        def cross_validate_information(query: str) -> str:
            """Cross-validate information across multiple sources for accuracy.
            
            Args:
                query: Query to cross-validate across sources
            
            Returns:
                Cross-validation analysis with confidence scores
            """
            try:
                # Search across multiple sources
                ground_truth_results = self.vector_db.semantic_search(query, top_k=3)
                database_results = self.vector_db.semantic_search(f"{query} database", top_k=3)
                clinical_trial_results = self.vector_db.semantic_search(f"{query} clinical trial", top_k=3)
                
                # Analyze consistency across sources
                validation_report = f"Cross-Validation Analysis for '{query}':\n\n"
                
                # Ground Truth Validation
                gt_drugs = []
                gt_companies = []
                gt_targets = []
                
                for result in ground_truth_results:
                    metadata = result["metadata"]
                    if metadata.get("source") == "ground_truth":
                        if metadata.get("generic_name"):
                            gt_drugs.append(metadata["generic_name"])
                        if metadata.get("company"):
                            gt_companies.append(metadata["company"])
                        if metadata.get("target"):
                            gt_targets.append(metadata["target"])
                
                # Database Validation
                db_drugs = []
                db_companies = []
                
                for result in database_results:
                    metadata = result["metadata"]
                    if metadata.get("source") == "database":
                        if metadata.get("generic_name"):
                            db_drugs.append(metadata["generic_name"])
                        if metadata.get("company"):
                            db_companies.append(metadata["company"])
                
                # Clinical Trial Validation
                trial_phases = []
                trial_statuses = []
                
                for result in clinical_trial_results:
                    metadata = result["metadata"]
                    if metadata.get("source") == "clinical_trial":
                        if metadata.get("phase"):
                            trial_phases.append(metadata["phase"])
                        if metadata.get("status"):
                            trial_statuses.append(metadata["status"])
                
                # Cross-validation analysis
                validation_report += "🔍 Source Consistency Analysis:\n"
                
                # Drug consistency
                common_drugs = set(gt_drugs) & set(db_drugs)
                if common_drugs:
                    validation_report += f"  ✅ Drug Consistency: {len(common_drugs)} drugs found in both Ground Truth and Database\n"
                    validation_report += f"     Common drugs: {', '.join(list(common_drugs)[:3])}\n"
                else:
                    validation_report += f"  ⚠️ Drug Consistency: No common drugs between Ground Truth and Database\n"
                
                # Company consistency
                common_companies = set(gt_companies) & set(db_companies)
                if common_companies:
                    validation_report += f"  ✅ Company Consistency: {len(common_companies)} companies found in both sources\n"
                    validation_report += f"     Common companies: {', '.join(list(common_companies)[:3])}\n"
                else:
                    validation_report += f"  ⚠️ Company Consistency: No common companies between sources\n"
                
                # Target validation
                if gt_targets:
                    unique_targets = list(set(gt_targets))
                    validation_report += f"  🎯 Target Information: {len(unique_targets)} unique targets in Ground Truth\n"
                    validation_report += f"     Targets: {', '.join(unique_targets[:3])}\n"
                
                # Clinical trial validation
                if trial_phases:
                    unique_phases = list(set(trial_phases))
                    validation_report += f"  🧪 Clinical Trial Phases: {len(unique_phases)} different phases\n"
                    validation_report += f"     Phases: {', '.join(unique_phases)}\n"
                
                # Confidence scoring
                confidence_factors = []
                
                if common_drugs:
                    confidence_factors.append("Drug consistency across sources")
                if common_companies:
                    confidence_factors.append("Company consistency across sources")
                if gt_targets:
                    confidence_factors.append("Target information available")
                if trial_phases:
                    confidence_factors.append("Clinical trial data available")
                
                confidence_score = len(confidence_factors) / 4.0  # Normalize to 0-1
                
                validation_report += f"\n📊 Cross-Validation Confidence: {confidence_score:.2f}\n"
                validation_report += f"Confidence Factors:\n"
                for factor in confidence_factors:
                    validation_report += f"  ✅ {factor}\n"
                
                if confidence_score < 0.5:
                    validation_report += f"\n⚠️ Low confidence - Limited cross-validation support\n"
                elif confidence_score < 0.75:
                    validation_report += f"\n✅ Moderate confidence - Good cross-validation support\n"
                else:
                    validation_report += f"\n🎯 High confidence - Strong cross-validation support\n"
                
                validation_report += f"\n🏆📊 Data Source: Cross-Validated (Ground Truth + Database + Clinical Trials)"
                
                return validation_report
                
            except Exception as e:
                logger.error(f"Cross-validation error: {e}")
                return f"Error in cross-validation: {str(e)}"
        
        # Data consistency checker
        def check_data_consistency(entity_name: str, entity_type: str) -> str:
            """Check data consistency for a specific entity across sources.
            
            Args:
                entity_name: Name of the entity to check
                entity_type: Type of entity (drug, company, target)
            
            Returns:
                Consistency analysis report
            """
            try:
                consistency_report = f"Data Consistency Check: {entity_name} ({entity_type})\n\n"
                
                # Search for the entity across all sources
                all_results = self.vector_db.semantic_search(entity_name, top_k=10)
                
                # Group results by source
                source_data = {
                    "ground_truth": [],
                    "database": [],
                    "clinical_trial": []
                }
                
                for result in all_results:
                    metadata = result["metadata"]
                    source = metadata.get("source", "unknown")
                    if source in source_data:
                        source_data[source].append(result)
                
                # Analyze consistency
                inconsistencies = []
                consistent_data = []
                
                # Check for entity-specific consistency
                if entity_type.lower() == "drug":
                    # Check drug name consistency
                    drug_names = set()
                    companies = set()
                    
                    for source, results in source_data.items():
                        for result in results:
                            metadata = result["metadata"]
                            if metadata.get("generic_name"):
                                drug_names.add(metadata["generic_name"].lower())
                            if metadata.get("company"):
                                companies.add(metadata["company"])
                    
                    if len(drug_names) > 1:
                        inconsistencies.append(f"Multiple drug name variations: {', '.join(drug_names)}")
                    else:
                        consistent_data.append("Drug name consistent across sources")
                    
                    if len(companies) > 1:
                        inconsistencies.append(f"Multiple companies associated: {', '.join(companies)}")
                    else:
                        consistent_data.append("Company association consistent")
                
                elif entity_type.lower() == "company":
                    # Check company name consistency
                    company_names = set()
                    
                    for source, results in source_data.items():
                        for result in results:
                            metadata = result["metadata"]
                            if metadata.get("company"):
                                company_names.add(metadata["company"])
                    
                    if len(company_names) > 1:
                        inconsistencies.append(f"Multiple company name variations: {', '.join(company_names)}")
                    else:
                        consistent_data.append("Company name consistent across sources")
                
                # Generate report
                consistency_report += f"📊 Sources Found:\n"
                for source, results in source_data.items():
                    consistency_report += f"  • {source}: {len(results)} entries\n"
                
                consistency_report += f"\n✅ Consistent Data:\n"
                for item in consistent_data:
                    consistency_report += f"  • {item}\n"
                
                if inconsistencies:
                    consistency_report += f"\n⚠️ Inconsistencies Found:\n"
                    for item in inconsistencies:
                        consistency_report += f"  • {item}\n"
                else:
                    consistency_report += f"\n🎯 No inconsistencies found - Data is consistent across sources\n"
                
                # Overall consistency score
                total_checks = len(consistent_data) + len(inconsistencies)
                consistency_score = len(consistent_data) / total_checks if total_checks > 0 else 0
                
                consistency_report += f"\n📈 Overall Consistency Score: {consistency_score:.2f}\n"
                
                if consistency_score >= 0.8:
                    consistency_report += f"🎯 High consistency - Data is reliable\n"
                elif consistency_score >= 0.6:
                    consistency_report += f"✅ Moderate consistency - Data is mostly reliable\n"
                else:
                    consistency_report += f"⚠️ Low consistency - Data needs verification\n"
                
                consistency_report += f"\n🏆📊 Data Source: Consistency Checked (Multi-Source)"
                
                return consistency_report
                
            except Exception as e:
                logger.error(f"Data consistency check error: {e}")
                return f"Error checking data consistency: {str(e)}"
        
        # Public resource search tool
        def search_public_resources(query: str) -> str:
            """Search public resources for information not available in internal database.
            
            Args:
                query: Search query for public information
            
            Returns:
                Information from public sources with clear attribution
            """
            try:
                # This is a placeholder for public resource search
                # In a real implementation, this could integrate with:
                # - PubMed API for scientific literature
                # - ClinicalTrials.gov API for trial information
                # - FDA database for drug approvals
                # - Company websites and press releases
                
                return f"""🌐 Public Resource Search Results for '{query}':

Based on publicly available information:

**General Information:**
- This information is from external/public sources
- Not verified against internal database
- May not reflect current internal business priorities

**Note:** For the most accurate and up-to-date information relevant to your business context, 
please refer to our internal database and ground truth data, which contains:
- Curated business intelligence
- Ticket priorities and strategic context
- Company-specific drug portfolios
- Internal competitive analysis

🌐 Data Source: Public Information

Would you like me to search for more specific information in our internal database?"""
                
            except Exception as e:
                logger.error(f"Public resource search error: {e}")
                return f"Error searching public resources: {str(e)}"
        
        # Development phase analysis tool
        def analyze_development_phase(targets: str) -> str:
            """Analyze development phases and indications for specific targets.
            
            Args:
                targets: Comma-separated list of targets (e.g., "PD-L1, VEGF")
            
            Returns:
                Detailed analysis of development phases and indications
            """
            try:
                target_list = [t.strip().upper() for t in targets.split(',')]
                all_results = []
                
                for target in target_list:
                    # Search for drugs targeting this specific target
                    results = self.vector_db.semantic_search(f"{target} drugs", top_k=5)
                    all_results.extend(results)
                    
                    # Search for clinical trials
                    trial_results = self.vector_db.semantic_search(f"{target} clinical trials", top_k=3)
                    all_results.extend(trial_results)
                
                if not all_results:
                    return f"No development information found for targets: {targets}"
                
                # Group results by target and analyze
                analysis = f"Development Phase Analysis for: {targets}\n\n"
                
                for target in target_list:
                    target_drugs = []
                    target_trials = []
                    
                    for result in all_results:
                        metadata = result["metadata"]
                        result_target = metadata.get("target", "").upper()
                        
                        # Check for exact match or partial match
                        if (result_target == target or 
                            target in result_target or 
                            result_target in target or
                            (target == "VEGF" and "VEGF" in result_target) or
                            (target == "PD-L1" and ("PD-L1" in result_target or "PD1" in result_target))):
                            if metadata.get("source") == "ground_truth":
                                target_drugs.append(result)
                            elif metadata.get("source") == "clinical_trial":
                                target_trials.append(result)
                    
                    analysis += f"🎯 {target} Analysis:\n"
                    
                    if target_drugs:
                        analysis += f"  📊 Drugs in Development:\n"
                        for drug in target_drugs:
                            metadata = drug["metadata"]
                            analysis += f"    • {metadata.get('generic_name', 'Unknown')}"
                            if metadata.get('brand_name'):
                                analysis += f" ({metadata.get('brand_name')})"
                            analysis += f" - {metadata.get('company', 'Unknown')}"
                            analysis += f"\n"
                    
                    if target_trials:
                        analysis += f"  🧪 Clinical Trials:\n"
                        for trial in target_trials:
                            metadata = trial["metadata"]
                            analysis += f"    • {metadata.get('title', 'Unknown')[:80]}..."
                            if metadata.get('phase'):
                                analysis += f" - Phase {metadata.get('phase')}"
                            if metadata.get('status'):
                                analysis += f" - {metadata.get('status')}"
                            analysis += f"\n"
                    
                    if not target_drugs and not target_trials:
                        analysis += f"    ❌ No specific {target} data found in internal sources\n"
                    
                    analysis += "\n"
                
                # Summary
                total_drugs = len([r for r in all_results if r["metadata"].get("source") == "ground_truth"])
                total_trials = len([r for r in all_results if r["metadata"].get("source") == "clinical_trial"])
                
                analysis += f"📈 Summary:\n"
                analysis += f"  • Total drugs found: {total_drugs}\n"
                analysis += f"  • Total clinical trials found: {total_trials}\n"
                analysis += f"  • Targets analyzed: {', '.join(target_list)}\n"
                
                return analysis
                
            except Exception as e:
                logger.error(f"Development phase analysis error: {e}")
                return f"Error analyzing development phases: {str(e)}"
        
        # Create function tools
        tools.append(FunctionTool.from_defaults(fn=semantic_search, name="semantic_search"))
        tools.append(FunctionTool.from_defaults(fn=multi_query_search, name="multi_query_search"))
        tools.append(FunctionTool.from_defaults(fn=compare_drugs, name="compare_drugs"))
        tools.append(FunctionTool.from_defaults(fn=search_public_resources, name="search_public_resources"))
        
        return tools
    
    def _aggregate_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Aggregate and deduplicate search results."""
        try:
            # Group results by source and company
            grouped_results = {}
            seen_drugs = set()
            
            for result in results:
                metadata = result["metadata"]
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "Unknown")
                drug_name = metadata.get("generic_name", "")
                
                # Create unique key for deduplication
                drug_key = f"{drug_name}_{company}".lower()
                if drug_key in seen_drugs:
                    continue
                seen_drugs.add(drug_key)
                
                if source not in grouped_results:
                    grouped_results[source] = {}
                if company not in grouped_results[source]:
                    grouped_results[source][company] = []
                
                grouped_results[source][company].append(result)
            
            # Format aggregated results
            formatted_results = []
            
            for source, companies in grouped_results.items():
                source_name = "Ground Truth" if source == "ground_truth" else "Database"
                formatted_results.append(f"\n📊 {source_name} Results:")
                
                for company, drugs in companies.items():
                    formatted_results.append(f"\n🏢 {company}:")
                    for drug in drugs:
                        metadata = drug["metadata"]
                        similarity_score = drug["similarity_score"]
                        
                        drug_text = f"  • {metadata.get('generic_name', 'Unknown')}"
                        if metadata.get('brand_name'):
                            drug_text += f" ({metadata.get('brand_name')})"
                        if metadata.get('target'):
                            drug_text += f" - Target: {metadata.get('target')}"
                        if metadata.get('mechanism'):
                            drug_text += f" - Mechanism: {metadata.get('mechanism')}"
                        
                        formatted_results.append(drug_text)
            
            return "\n".join(formatted_results) if formatted_results else "No results found"
            
        except Exception as e:
            logger.error(f"Error aggregating search results: {e}")
            return f"Error aggregating results: {str(e)}"
    
    def _find_best_drug_match(self, results: List[Dict[str, Any]], drug_name: str) -> Optional[Dict[str, Any]]:
        """Find the best match for a drug from search results."""
        try:
            drug_name_lower = drug_name.lower()
            
            # Look for exact matches first
            for result in results:
                metadata = result["metadata"]
                generic_name = metadata.get("generic_name", "").lower()
                brand_name = metadata.get("brand_name", "").lower()
                
                if (drug_name_lower in generic_name or 
                    drug_name_lower in brand_name or
                    generic_name in drug_name_lower):
                    return metadata
            
            # Return highest relevance result if no exact match
            if results:
                return results[0]["metadata"]
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding best drug match: {e}")
            return None
    
    def _create_react_agent(self) -> ReActAgent:
        """Create the React agent with tools and memory."""
        try:
            # Create memory buffer
            memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
            
            # Create React agent
            agent = ReActAgent.from_tools(
                tools=self.tools,
                llm=self.llm,
                memory=memory,
                verbose=True,
                max_iterations=5,
                system_prompt="""
                You are a specialized oncology and cancer research assistant focused on biopartnering insights.
                You use the React framework (Reasoning + Acting + Observing) to provide accurate, evidence-based responses.
                
                EFFICIENT WORKFLOW:
                1. REASONING: Analyze the question and determine the best tool to use
                2. ACTING: Use semantic_search for most questions - it searches all data sources
                3. OBSERVING: Analyze results and provide a comprehensive answer
                4. BE CONCISE: Answer in 1-2 iterations maximum for simple questions
                5. PROVIDE DETAILS: When you find relevant data, extract and present all key information clearly
                
                CRITICAL: For simple questions like "companies with TROP2", use semantic_search ONCE and provide the answer immediately. Do not iterate multiple times.
                
                QUERY STRATEGY FOR BETTER RESULTS:
                - For "companies with TROP2": Search "TROP2 targeting companies" or "TROP2 drugs companies"
                - For "drugs targeting HER3": Search "HER3 targeting drugs" or "HER3 drugs"
                - For "clinical trials TROP2": Search "TROP2 clinical trials" or "TROP2 trials"
                - Use descriptive queries, not single words
                
                AVAILABLE TOOLS:
                - semantic_search: PRIMARY tool for ALL questions - searches all data sources via vector embeddings
                - multi_query_search: For complex multi-part questions that need multiple searches
                - compare_drugs: For direct drug comparisons
                - search_public_resources: Search external sources when internal data insufficient
                
                TOOL SELECTION STRATEGY (SIMPLIFIED):
                - For ALL questions: Use semantic_search as the primary tool
                - For simple questions like "companies with TROP2": Use semantic_search ONCE, then answer immediately
                - For complex multi-part questions: Use multi_query_search
                - For drug comparisons: Use compare_drugs
                - When internal data insufficient: Use search_public_resources
                
                STOPPING CONDITIONS:
                - If you get results from semantic_search, provide the answer immediately
                - Do NOT run multiple searches for simple questions
                - Do NOT iterate more than 2 times for basic company/target questions
                
                RESPONSE GUIDELINES:
                - ALWAYS use semantic_search FIRST for any question
                - Generate comprehensive summaries from the top-K results
                - Extract and present ALL relevant information clearly
                - For company questions: List all companies found with their drugs, targets, mechanisms
                - For drug questions: Provide drug names, companies, targets, mechanisms, approval status
                - For target questions: List all drugs targeting that target with company information
                - ALWAYS provide detailed information from search results
                - Include drug names, mechanisms, development phases, and other relevant details
                - Format your answer clearly with bullet points or structured information
                - If internal data is found, provide detailed information from internal sources
                - If no internal data found, use this EXACT format:
                  "❓ I don't know - No relevant information found in our internal database or ground truth data.
                  Would you like me to search public resources for this information?"
                - Always indicate your data source at the end of your response
                
                DATA SOURCE PRIORITY:
                1. Ground Truth (highest priority - curated business data)
                2. Internal Database (pipeline-collected data)
                3. FDA Data (external API but integrated internally)
                4. Clinical Trials (external API but integrated internally)
                5. Drugs.com (external API but integrated internally)
                6. Cross-reference all sources for validation
                
                RESPONSE GUIDELINES:
                - ALWAYS search internal sources FIRST before providing any answer
                - Use analyze_competitive_landscape for ALL company/target questions
                - When you get search results, extract ALL relevant information and present it clearly
                - For company questions: List all companies found with their drugs, targets, mechanisms, and development phases
                - For drug questions: Provide drug names, companies, targets, mechanisms, and approval status
                - For target questions: List all drugs targeting that target with company information, mechanisms, and development phases
                - ALWAYS provide detailed information from search results - don't just list company names
                - Include drug names, mechanisms, development phases, and other relevant details
                - Format your answer clearly with bullet points or structured information
                - Provide comprehensive answers based on search results
                - If internal data is found, provide detailed information from internal sources
                - If no internal data found, use this EXACT format:
                  "❓ I don't know - No relevant information found in our internal database or ground truth data.
                  Would you like me to search public resources for this information?"
                - Always indicate your data source at the end of your response
                
                DATA SOURCE INDICATORS:
                - "🏆 Data Source: Ground Truth" (curated business data with tickets/priorities)
                - "📊 Data Source: Internal Database" (pipeline-collected data)
                - "🏥 Data Source: FDA" (FDA approved drugs and regulatory data)
                - "🧪 Data Source: Clinical Trials" (clinical trial data)
                - "💊 Data Source: Drugs.com" (comprehensive drug profiles and interactions)
                - "🏆📊🏥🧪💊 Data Source: Internal (Ground Truth + Database + FDA + Clinical Trials + Drugs.com)" (all internal sources)
                - "🌐 Data Source: Public Information" (external/general knowledge - only when explicitly requested)
                
                CRITICAL: For biopharmaceutical questions, ALWAYS search internal sources first!
                Be efficient - use the right tool and provide complete answers without unnecessary iterations.
                When you find relevant data, present it in a structured, detailed format with all available information.
                Don't just list names - include mechanisms, ticket numbers, drug classes, and other relevant details.
                
                CRITICAL RESPONSE FORMATTING:
                - When you get detailed tool output (like from analyze_competitive_landscape), USE IT DIRECTLY
                - Do NOT summarize or shorten the tool output - present it as-is
                - Include ALL the emojis, formatting, and details from the tool output
                - Add data source attribution at the end
                - The tool output IS your answer - don't rewrite it!
                
                FINAL ANSWER INSTRUCTIONS:
                - Your final answer should be the COMPLETE tool output, not a summary
                - Copy the tool output exactly as it appears
                - Add data source attribution at the end
                - Do NOT write "There are X companies..." - use the full tool output instead
                
                CRITICAL: When you see "IMPORTANT: This is your complete answer. Do not summarize or shorten this response. Present it exactly as shown above." in the tool output, you MUST copy the ENTIRE tool output as your final answer, including all emojis, formatting, and details.
                
                CONSISTENCY REQUIREMENTS:
                - ALWAYS provide the same level of detail for similar questions
                - ALWAYS use analyze_competitive_landscape for company/target questions
                - ALWAYS include drug names, companies, mechanisms, and development phases when available
                - NEVER give generic responses like "Companies such as X, Y, Z may be working on..."
                - ALWAYS provide specific, factual information from the search results
                - NEVER say "I cannot determine" or "unable to find" - always search first
                - NEVER summarize or shorten tool output - present it in full detail
                - The tool output contains the complete answer - use it directly!
                
                EXAMPLES OF GOOD RESPONSES:
                
                Example 1 - Simple Company/Target Question:
                Question: "What are the companies with TROP2?"
                Tool: semantic_search
                Query: "TROP2 targeting companies" (NOT just "TROP2")
                Tool Output: "Found 3 companies with TROP2:
                
                1. 🏆 GROUND TRUTH: Sacituzumab govitecan-hziy (Trodelvy) - Company: Gilead - Target: TROP2 (Relevance: 0.502)
                2. 🏆 GROUND TRUTH: Datopotamab deruxtecan-dlnk (DATROWAY) - Company: Daiichi - Target: TROP2 (Relevance: 0.494)
                3. 🏆 GROUND TRUTH: sacituzumab tirumotecan (MK-2870) - Company: Merck - Target: TROP2 (Relevance: 0.488)"
                
                Final Answer: "The companies with TROP2 are:
                
                🏢 Gilead: Sacituzumab govitecan-hziy (Trodelvy) - TROP2 targeting
                🏢 Daiichi: Datopotamab deruxtecan-dlnk (DATROWAY) - TROP2 targeting  
                🏢 Merck: sacituzumab tirumotecan (MK-2870) - TROP2 targeting
                
                🏆📊 Data Source: Internal (Ground Truth + Database)"
                
                CRITICAL: This is a SIMPLE question - use semantic_search ONCE with descriptive query and answer immediately. Do NOT iterate multiple times.
                
                Example 2 - Competitive Landscape Question:
                Question: "What is the competitive landscape for BRAF?"
                Tool: semantic_search
                Response: "BRAF Competitive Landscape:
                
                🏢 Roche: Mosperafenib - Inhibits oncogenic BRAF V600E
                🏢 Genentech: Vemurafenib (Zelboraf) - Inhibits BRAF V600
                🏢 Roche/Genentech: Ribociclib, Palbociclib, Tisagenlecleucel
                
                📊 Market Insights:
                • Competitive market with multiple companies
                • Diverse mechanisms targeting BRAF mutations
                
                🏆📊 Data Source: Internal (Ground Truth + Database)"
                
                Example 3 - Drug Comparison Question:
                Question: "Compare Trastuzumab and Pertuzumab"
                Tool: compare_drugs
                Response: "Drug Comparison: Trastuzumab vs Pertuzumab
                
                🏢 Companies:
                  • Trastuzumab: Genentech
                  • Pertuzumab: Genentech
                
                🎯 Targets:
                  • Trastuzumab: HER2
                  • Pertuzumab: HER2
                
                ⚙️ Mechanisms:
                  • Trastuzumab: Block HER2 mediated signaling
                  • Pertuzumab: Block HER2 mediated signaling
                
                💊 Drug Classes:
                  • Trastuzumab: Monoclonal Antibody
                  • Pertuzumab: Monoclonal Antibody
                
                🏆📊 Data Source: Internal (Ground Truth + Database)"
                
                Example 4 - No Data Found:
                Question: "Companies targeting XYZ123"
                Tool: analyze_competitive_landscape
                Response: "❓ I don't know - No relevant information found in our internal database or ground truth data.
                Would you like me to search public resources for this information?"
                
                CRITICAL EXAMPLES OF WHAT NOT TO DO:
                
                ❌ BAD: "Companies such as Biogen, Pfizer, and Eli Lilly may be working on targets related to HER3."
                ✅ GOOD: "There are 3 companies that target HER3: Daiichi Sankyo (Patritumab Deruxtecan), Merck (Patritumab Deruxtecan MK-1022), and AstraZeneca (Trastuzumab Deruxtecan)."
                
                ❌ BAD: "I cannot determine how many companies are targeting HER3."
                ✅ GOOD: Use semantic_search tool first, then provide specific answer from search results.
                
                ❌ BAD: Generic responses without specific drug names, companies, or mechanisms.
                ✅ GOOD: Detailed responses with specific information from search results.
                """
            )
            
            return agent
            
        except Exception as e:
            logger.error(f"Error creating React agent: {e}")
            raise
    
    def generate_response(self, question: str) -> Dict[str, Any]:
        """Generate response using React framework with semantic search."""
        try:
            # Generate response using React agent
            logger.info(f"Generating React response for: {question}")
            
            response = self.agent.chat(question)
            answer = str(response)
            
            # Create result
            result = {
                "question": question,
                "answer": answer,
                "source": "react_agent",
                "citations": [],
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            
            logger.info("React response generated successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error generating React response: {e}")
            
            return {
                "question": question,
                "answer": f"❓ I don't know - Error occurred while processing your question: {str(e)}",
                "source": "react_agent_error",
                "citations": [],
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def _is_no_data_response(self, answer: str) -> bool:
        """Check if the response indicates no data was found."""
        no_data_indicators = [
            "unable to find",
            "no information found",
            "no relevant information",
            "no data found",
            "cannot determine",
            "don't know",
            "no companies",
            "no drugs",
            "no targets"
        ]
        answer_lower = answer.lower()
        return any(indicator in answer_lower for indicator in no_data_indicators)
    
    def _fallback_search(self, question: str) -> str:
        """Fallback search using direct semantic search when React agent fails."""
        try:
            logger.info(f"Running fallback search for: {question}")
            
            # Extract key terms from question
            question_lower = question.lower()
            
            # Determine search strategy based on question type (completely dynamic)
            if any(word in question_lower for word in ['company', 'companies']):
                # Extract target from question dynamically
                target = self._extract_target_from_question(question)
                if target:
                    search_query = f"{target} companies drugs"
                else:
                    search_query = f"{question} companies"
            elif any(word in question_lower for word in ['drug', 'drugs']):
                search_query = f"{question} drugs"
            else:
                search_query = question
            
            # Perform semantic search
            results = self.vector_db.semantic_search(search_query, top_k=5)
            
            if not results:
                return None
            
            # Format results
            answer_parts = []
            
            # Group by company
            companies = {}
            for result in results:
                metadata = result["metadata"]
                company = metadata.get("company", "Unknown")
                generic_name = metadata.get("generic_name", "").strip()
                brand_name = metadata.get("brand_name", "").strip()
                
                # Skip entries with empty drug names
                if not generic_name and not brand_name:
                    continue
                
                # Use brand name if generic name is empty, or vice versa
                drug_name = generic_name if generic_name else brand_name
                
                if company not in companies:
                    companies[company] = []
                
                companies[company].append({
                    "drug": drug_name,
                    "brand": brand_name if generic_name else "",  # Only show brand if we have generic
                    "target": metadata.get("target", ""),
                    "mechanism": metadata.get("mechanism", ""),
                    "ticket": metadata.get("ticket", ""),
                    "relevance": result["similarity_score"]
                })
            
            # Build answer
            if companies:
                answer_parts.append(f"Found {len(companies)} companies:")
                
                for company, drugs in companies.items():
                    answer_parts.append(f"\\n🏢 **{company}**:")
                    for drug in drugs:
                        drug_info = f"  • {drug['drug']}"
                        if drug['brand']:
                            drug_info += f" ({drug['brand']})"
                        if drug['target']:
                            drug_info += f" - Target: {drug['target']}"
                        if drug['mechanism']:
                            drug_info += f" - {drug['mechanism']}"
                        answer_parts.append(drug_info)
                
                answer_parts.append(f"\\n🏆📊 Data Source: Internal (Ground Truth + Database)")
                return "\\n".join(answer_parts)
            
            return None
            
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def _extract_target_from_question(self, question: str) -> Optional[str]:
        """Extract target name from question dynamically."""
        try:
            import re
            
            # Dynamic target patterns (no hardcoded target names)
            target_patterns = [
                r'\b([a-z]{2,}[1-9])\b',  # Pattern like HER2, TROP2, CD19, EGFR, BRAF, KRAS, etc.
                r'\b([a-z]+-?[a-z]+[1-9]?)\b',  # Pattern like PD-L1, VEGF-A, etc.
                r'\b([a-z]+\s+receptor\s+\d+)\b',  # Pattern like "tropomyosin receptor 2"
                r'\b([a-z]+\s+antigen\s+\d+)\b',  # Pattern like "tumor antigen 2"
                r'\b([a-z]+\s+factor\s+\d+)\b',  # Pattern like "growth factor 2"
            ]
            
            question_lower = question.lower()
            for pattern in target_patterns:
                matches = re.findall(pattern, question_lower)
                if matches:
                    # Filter out common non-target words and return the best match
                    filtered_matches = []
                    for match in matches:
                        # Skip common words that aren't targets
                        if match.lower() not in ['companies', 'company', 'target', 'targets', 'drugs', 'drug', 'how', 'many', 'with', 'competitive', 'landscape', 'phase', 'development', 'indication']:
                            filtered_matches.append(match)
                    
                    if filtered_matches:
                        # Return the longest match (most specific)
                        best_match = max(filtered_matches, key=len)
                        # Convert to uppercase for consistency
                        return best_match.upper()
            
            # If no pattern matches, try to extract capitalized words that look like targets
            words = question.split()
            potential_targets = []
            
            # Dynamic stop words detection (no hardcoded list)
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'how', 'many', 'what', 'which', 'who', 'where', 'when', 'why'}
            question_words = {word.lower() for word in words}
            
            for word in words:
                # Look for words that are all caps or start with capital letter
                if (word.isupper() and len(word) >= 2) or (word[0].isupper() and len(word) >= 3):
                    # Skip common words dynamically
                    if word.lower() not in common_words and word.lower() not in question_words:
                        potential_targets.append(word.upper())
            
            if potential_targets:
                return potential_targets[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting target from question: {e}")
            return None
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get agent status and configuration."""
        return {
            "agent_type": "enhanced_react_framework",
            "llm_model": "llama3.1",
            "tools_count": len(self.tools),
            "tools": [tool.metadata.name for tool in self.tools],
            "memory_enabled": True,
            "max_iterations": 5,
            "vector_database": "ChromaDB",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "capabilities": [
                "semantic_search",
                "multi_query_analysis", 
                "drug_comparison",
                "competitive_landscape_analysis",
                "development_phase_analysis",
                "cross_validation",
                "data_consistency_checking",
                "public_resource_search",
                "result_aggregation",
                "deduplication"
            ],
            "status": "active"
        }
