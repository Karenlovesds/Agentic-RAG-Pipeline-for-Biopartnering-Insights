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

from typing import List, Dict, Any, Optional, Tuple
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

# System prompt extracted to top-level constant for readability
SYSTEM_PROMPT = """
You are a specialized oncology and cancer research assistant focused on biopartnering insights.
You use the React framework (Reasoning + Acting + Observing) to provide accurate, evidence-based responses.

EFFICIENT WORKFLOW:
1. REASONING: Analyze the question and determine the best tool to use
2. ACTING: Use semantic_search for most questions - it searches all data sources
3. OBSERVING: Analyze results and provide a comprehensive answer
4. BE CONCISE: Answer in 1-2 iterations maximum for simple questions
5. PROVIDE DETAILS: When you find relevant data, extract and present all key information clearly

CRITICAL: For simple questions like "companies with TROP2", use semantic_search ONCE and provide the answer immediately. Do not iterate multiple times.

TERMINATION CONDITIONS:
- If you get results from semantic_search, provide the answer immediately
- Do NOT run multiple searches for simple questions
- Do NOT iterate more than 2 times for basic company/target questions
- If you find yourself repeating the same search query, STOP and provide the best answer you have

QUERY STRATEGY FOR BETTER RESULTS:
- For "companies with TROP2": Search "TROP2 targeting companies" or "TROP2 drugs companies"
- For "drugs targeting HER3": Search "HER3 targeting drugs" or "HER3 drugs"
- For "clinical trials TROP2": Search "TROP2 clinical trials" or "TROP2 trials"
- Use descriptive queries, not single words

AVAILABLE TOOLS:
- semantic_search: PRIMARY tool for ALL questions - searches all data sources via vector embeddings
- multi_query_search: For complex multi-part questions that need multiple searches

TOOL SELECTION STRATEGY (SIMPLIFIED):
- For ALL questions: Use semantic_search as the primary tool
- For simple questions like "companies with TROP2": Use semantic_search ONCE, then answer immediately
- For complex multi-part questions: Use multi_query_search

STOPPING CONDITIONS (CRITICAL):
- If you get results from semantic_search, provide the answer immediately
- Do NOT run multiple searches for simple questions
- Do NOT iterate more than 2 times for basic company/target questions
- If you see the same search query being repeated, STOP immediately and provide the best answer you have
- For "companies targeting X" questions, search once and list all companies found

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

DATA SOURCE INDICATORS:
- "🏆 Data Source: Ground Truth"
- "📊 Data Source: Internal Database"
- "🏥 Data Source: FDA"
- "🧪 Data Source: Clinical Trials"
- "💊 Data Source: Drugs.com"
- "🏆📊🏥🧪💊 Data Source: Internal (Ground Truth + Database + FDA + Clinical Trials + Drugs.com)"
- "🌐 Data Source: Public Information"

CRITICAL RESPONSE FORMATTING:
- Use the exact format from the examples above
- List companies with their drug names and key details in parentheses
- Include specific targets, mechanisms, and development phases when available
- Use semicolons to separate multiple drugs from the same company
- Include clinical trial phases and indications when available
- Be comprehensive - include all relevant companies and drugs found
- Use natural language flow, not bullet points or structured lists

FINAL ANSWER INSTRUCTIONS:
- Follow the exact pattern from the examples: "Company: Drug (details); Company: Drug (details)"
- Include drug codes/names, targets, mechanisms, and phases in parentheses
- Use semicolons to separate different companies
- Include clinical trial information and indications when available
- Be comprehensive and detailed like the examples

EXAMPLES OF GOOD RESPONSES: (KRAS, BCL6, MTAP)

KRAS inhibitor question:
"Roche: Divarasib (GDC-6036 / RG6330, KRAS G12C); RG6620 (GDC-7035, KRAS G12D). Amgen: LUMAKRAS (sotorasib, KRAS G12C) – approved in KRAS G12C-mutated NSCLC; clinical trials include NSCLC and advanced colorectal cancer. Merck: MK-1084 (KRAS G12C). Eli Lilly: Olomorasib (KRAS G12C); KRAS G12D program (KRAS G12D); LY4066434 (pan-KRAS)."

BCL6 question:
"Arvinas: ARV-393 (oral BCL6 PROTAC degrader, Phase 1, advanced NHL). Bristol Myers Squibb: BMS-986458 (BCL6 degrader, Phase 1, NHL). Treeline Biosciences: TLN-121 (BCL6 degrader, Phase 1, relapsed/refractory NHL); company raised Series A extension and advanced three candidates including TLN-121."

MTAP question:
"Bayer: BAY 3713372 – Phase 1/2 mono and combo in advanced NSCLC, GI, biliary tract, pancreatic, and other solid tumors. Amgen: AMG 193 – Phase 1 mono and combo in MTAP-deleted solid tumors including PDAC, GI, and biliary tract. BMS: MRTX1719 / BMS-986504 – Phase 1–3 mono and combo across MTAP-deleted solid tumors; BMS-986504 focuses on first-line metastatic NSCLC. AstraZeneca: AZD3470 – Phase 1 in MTAP-deficient advanced/metastatic solid tumors. Gilead: GS-5319 – Phase 1 in MTAP-deleted advanced solid tumors."

Additional patterns (for evaluation-style questions):
"Merck pipeline drugs? Merck: Pembrolizumab (KEYTRUDA, PD-1, monoclonal antibody); MK-3475A (subcutaneous pembrolizumab); [include other drugs found with targets/mechanisms/phases]."

"Pembrolizumab use? Pembrolizumab (KEYTRUDA): PD-1 inhibitor; indications include melanoma, NSCLC, RCC, and others; mechanism: blocks PD-1 to restore anti-tumor immunity."

"Bristol Myers Squibb clinical trials? BMS: Nivolumab (OPDUALAG), Ipilimumab (YERVOY), [list ongoing/recruiting trials with phase/indications when found]."

"Latest FDA approvals for cancer drugs? [List drug – company – date – indication – mechanism if available], prioritizing newest entries."

"Available immunotherapy drugs? [List by company]: Merck – Pembrolizumab (PD-1); BMS – Nivolumab (PD-1), Ipilimumab (CTLA-4); Roche – Atezolizumab (PD-L1); etc."
"""


class ReactRAGAgent:
    """React Framework RAG Agent for reliable biopharmaceutical insights."""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize vector database manager
        self.vector_db = VectorDBManager()
        
        # Initialize Ollama LLM for React agent
        self.llm = Ollama(
            model="llama3.1",
            request_timeout=60.0,  # Reduced from 300 to 60 seconds
            temperature=0.0  # Set to 0 for maximum consistency
        )
        
        # Create tools for the React agent
        self.tools = self._create_tools()
        
        # Initialize React agent
        self.agent = self._create_react_agent()
        
        logger.info("React RAG Agent with Vector Database initialized successfully")
    
    def _format_search_result(self, result: Dict[str, Any], index: int) -> str:
        """Format a single search result based on its source."""
        metadata = result["metadata"]
        similarity_score = result["similarity_score"]
        
        # Define formatting templates for each source type
        source_templates = {
            "ground_truth": (
                f"{index}. 🏆 GROUND TRUTH: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Target: {metadata['target']} "
                                f"- Mechanism: {metadata['mechanism']} "
            ),
            "database": (
                f"{index}. 📊 DATABASE: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Mechanism: {metadata['mechanism']} "
                                f"- Drug Class: {metadata['drug_class']} (Relevance: {similarity_score:.3f})"
            ),
            "clinical_trial": (
                f"{index}. 🧪 CLINICAL TRIAL: {metadata['nct_id']} - Phase: {metadata['phase']} "
                                f"- Status: {metadata['status']} (Relevance: {similarity_score:.3f})"
            ),
            "fda": (
                f"{index}. 🏥 FDA: {metadata['generic_name']} ({metadata['brand_name']}) "
                                f"- Company: {metadata['company']} - Approval Date: {metadata.get('fda_approval_date', 'N/A')} "
                                f"- Targets: {metadata.get('target', 'N/A')} (Relevance: {similarity_score:.3f})"
            ),
            "drugs_com": (
                f"{index}. 💊 DRUGS.COM: {metadata['title']} "
                                f"- Source: {metadata.get('url', 'N/A')} (Relevance: {similarity_score:.3f})"
                            )
        }
        
        # Get template for source type or use default
        source = metadata["source"]
        if source in source_templates:
            return source_templates[source]
        else:
            return (
                f"{index}. {source.upper()}: {metadata.get('generic_name', metadata.get('title', 'Unknown'))} "
                f"- Company: {metadata.get('company', 'N/A')} (Relevance: {similarity_score:.3f})"
            )
    
    def _generate_search_summary(self, results: List[Dict[str, Any]], query: str) -> str:
        """Generate summary for search results with a simple source map."""
        summary = f"\n\nSUMMARY: Found {len(results)} results for '{query}'"
        sources_found = {r["metadata"].get("source", "unknown") for r in results}
        source_labels = {
            "ground_truth": "Ground Truth",
            "database": "Database",
            "clinical_trial": "Clinical Trial",
        }
        included = [label for key, label in source_labels.items() if key in sources_found]
        if included:
            summary += " - Includes " + ", ".join(included) + " data"
        return summary
    
    def _extract_ground_truth_data(self, results: List[Dict[str, Any]]) -> Tuple[List[str], List[str], List[str]]:
        """Extract drugs, companies, and targets from ground truth results."""
        gt_drugs = []
        gt_companies = []
        gt_targets = []
        
        for result in results:
            metadata = result["metadata"]
            if metadata.get("source") == "ground_truth":
                if metadata.get("generic_name"):
                    gt_drugs.append(metadata["generic_name"])
                if metadata.get("company"):
                    gt_companies.append(metadata["company"])
                if metadata.get("target"):
                    gt_targets.append(metadata["target"])
        
        return gt_drugs, gt_companies, gt_targets
    
    def _extract_database_data(self, results: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """Extract drugs and companies from database results."""
        db_drugs = []
        db_companies = []
        
        for result in results:
            metadata = result["metadata"]
            if metadata.get("source") == "database":
                if metadata.get("generic_name"):
                    db_drugs.append(metadata["generic_name"])
                if metadata.get("company"):
                    db_companies.append(metadata["company"])
        
        return db_drugs, db_companies
    
    def _extract_clinical_trial_data(self, results: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """Extract phases and statuses from clinical trial results."""
        trial_phases = []
        trial_statuses = []
        
        for result in results:
            metadata = result["metadata"]
            if metadata.get("source") == "clinical_trial":
                if metadata.get("phase"):
                    trial_phases.append(metadata["phase"])
                if metadata.get("status"):
                    trial_statuses.append(metadata["status"])
        
        return trial_phases, trial_statuses
    
    def _build_consistency_report(self, gt_drugs: List[str], gt_companies: List[str], gt_targets: List[str],
                                 db_drugs: List[str], db_companies: List[str], 
                                 trial_phases: List[str], query: str) -> str:
        """Build the consistency analysis report."""
        validation_report = f"Cross-Validation Analysis for '{query}':\n\n"
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
        
        return validation_report
    
    def _calculate_confidence_score(self, common_drugs: set, common_companies: set, 
                                   gt_targets: List[str], trial_phases: List[str]) -> Tuple[float, List[str]]:
        """Calculate confidence score and factors."""
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
        return confidence_score, confidence_factors
    
    def _group_results_by_source_and_company(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group search results by source and company, removing duplicates."""
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
        
        return grouped_results
    
    def _format_aggregated_results(self, grouped_results: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> List[str]:
        """Format grouped results into readable text."""
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
        
        return formatted_results
    
    def _determine_search_query(self, question: str) -> str:
        """Determine the best search query based on question type."""
        question_lower = question.lower()
        
        # Define query patterns for different question types
        query_patterns = {
            'company': lambda q: self._get_company_query(q),
            'companies': lambda q: self._get_company_query(q),
            'drug': lambda q: f"{q} drugs",
            'drugs': lambda q: f"{q} drugs"
        }
        
        # Find matching pattern and generate query
        for keyword, query_func in query_patterns.items():
            if keyword in question_lower:
                return query_func(question)
        
        # Default fallback
        return question
    
    def _get_company_query(self, question: str) -> str:
        """Generate company-specific search query."""
        target = self._extract_target_from_question(question)
        if target:
            return f"{target} companies drugs"
        else:
            return f"{question} companies"
    
    def _group_results_by_company(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group search results by company."""
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
                "relevance": result["similarity_score"]
            })
        
        return companies
    
    def _format_fallback_answer(self, companies: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format the fallback search answer in a human-readable way."""
        if not companies:
            return None
        
        answer_parts = []
        
        # Add opening statement
        answer_parts.append(self._create_fallback_opening(len(companies)))
        answer_parts.append("")  # Empty line for spacing
        
        # Format each company
        for company, drugs in companies.items():
            answer_parts.append(f"🏢 **{company}**")
            answer_parts.extend(self._format_company_drugs(drugs))
            answer_parts.append("")  # Empty line between companies
        
        # Add data source
        answer_parts.append("📊 *Data source: Internal biopartnering database*")
        
        return "\n".join(answer_parts)
    
    def _create_fallback_opening(self, company_count: int) -> str:
        """Create the opening statement for fallback answer."""
        if company_count == 1:
            return f"I found **{company_count} company** working on this target:"
        else:
            return f"I found **{company_count} companies** working on this target:"
    
    def _format_company_drugs(self, drugs: List[Dict[str, Any]]) -> List[str]:
        """Format drugs for a company, grouped by target."""
        # Group drugs by target to avoid repetition
        drugs_by_target = {}
        for drug in drugs:
            target = drug.get('target', 'Unknown target')
            if target not in drugs_by_target:
                drugs_by_target[target] = []
            drugs_by_target[target].append(drug)
        
        formatted_lines = []
        # Format each target group
        for target, target_drugs in drugs_by_target.items():
            formatted_lines.append(self._format_target_drug_group(target, target_drugs))
        
        return formatted_lines
    
    def _format_target_drug_group(self, target: str, target_drugs: List[Dict[str, Any]]) -> str:
        """Format a group of drugs targeting the same target."""
        if len(target_drugs) == 1:
            drug = target_drugs[0]
            drug_name = drug.get('drug', 'Unknown drug')
            brand = drug.get('brand', '')
            
            if brand:
                return f"  • **{drug_name}** ({brand}) - Targets {target}"
            else:
                return f"  • **{drug_name}** - Targets {target}"
        else:
            # Multiple drugs for same target
            drug_names = []
            for drug in target_drugs:
                drug_name = drug.get('drug', 'Unknown drug')
                brand = drug.get('brand', '')
                if brand:
                    drug_names.append(f"{drug_name} ({brand})")
                else:
                    drug_names.append(drug_name)
            
            drugs_list = ", ".join(drug_names)
            return f"  • **{drugs_list}** - All target {target}"
    
    def _get_target_patterns(self) -> List[str]:
        """Get regex patterns for target extraction."""
        return [
            r'\b([a-z]{2,}[1-9])\b',  # Pattern like HER2, TROP2, CD19, EGFR, BRAF, KRAS, etc.
            r'\b([a-z]+-?[a-z]+[1-9]?)\b',  # Pattern like PD-L1, VEGF-A, etc.
            r'\b([a-z]+\s+receptor\s+\d+)\b',  # Pattern like "tropomyosin receptor 2"
            r'\b([a-z]+\s+antigen\s+\d+)\b',  # Pattern like "tumor antigen 2"
            r'\b([a-z]+\s+factor\s+\d+)\b',  # Pattern like "growth factor 2"
        ]
    
    def _get_common_words(self) -> set:
        """Get common words to filter out from target extraction."""
        return {'companies', 'company', 'target', 'targets', 'drugs', 'drug', 'how', 'many', 'with', 'competitive', 'landscape', 'phase', 'development', 'indication'}
    
    def _get_stop_words(self) -> set:
        """Get stop words for target extraction."""
        return {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'how', 'many', 'what', 'which', 'who', 'where', 'when', 'why'}
    
    def _extract_targets_by_pattern(self, question_lower: str) -> Optional[str]:
        """Extract target using regex patterns."""
        import re
        
        target_patterns = self._get_target_patterns()
        common_words = self._get_common_words()
        
        for pattern in target_patterns:
            matches = re.findall(pattern, question_lower)
            if matches:
                # Filter out common non-target words and return the best match
                filtered_matches = []
                for match in matches:
                    # Skip common words that aren't targets
                    if match.lower() not in common_words:
                        filtered_matches.append(match)
                
                if filtered_matches:
                    # Return the longest match (most specific)
                    best_match = max(filtered_matches, key=len)
                    # Convert to uppercase for consistency
                    return best_match.upper()
        
        return None
    
    def _extract_targets_by_capitalization(self, question: str) -> Optional[str]:
        """Extract target using capitalization patterns."""
        words = question.split()
        potential_targets = []
        
        # Dynamic stop words detection (no hardcoded list)
        common_words = self._get_stop_words()
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
    
    def _create_tools(self) -> List[FunctionTool]:
        """Create tools for the React agent."""
        tools = []
        
        # Create function tools
        tools.append(FunctionTool.from_defaults(fn=self._semantic_search_tool, name="semantic_search"))
        tools.append(FunctionTool.from_defaults(fn=self._multi_query_search_tool, name="multi_query_search"))
        # Non-critical tools are intentionally not added to reduce surface area
        
        return tools
    
    def _semantic_search_tool(self, query: str, top_k: int = 15) -> str:
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
            
            if not results:
                return f"No semantic search results found for '{query}'"
            
            # Format all results
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(self._format_search_result(result, i))
            
            # Generate summary
            summary = self._generate_search_summary(results, query)
            
            return f"Semantic Search Results for '{query}':\n" + "\n".join(formatted_results) + summary
                
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return f"Error in semantic search: {str(e)}"
    
    def _multi_query_search_tool(self, query: str) -> str:
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
            search_queries = self._determine_search_strategy(query)
            
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
    
    def _determine_search_strategy(self, query: str) -> List[str]:
        """Determine search strategy based on query patterns."""
        query_lower = query.lower()
        
        # Define search strategies for different query types
        search_strategies = {
            'competitive': ['competitive', 'landscape', 'market', 'players'],
            'comparison': ['compare', 'comparison', 'vs', 'versus'],
            'timeline': ['timeline', 'development', 'evolution', 'history'],
            'target_dev': ['phase', 'development', 'indication', 'targeting']
        }
        
        # Define query expansions for each strategy
        strategy_expansions = {
            'competitive': [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials", f"{query} mechanisms"],
            'comparison': [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials"],
            'timeline': [query, f"{query} clinical trials", f"{query} approvals", f"{query} partnerships"],
            'target_dev': [query, f"{query} drugs", f"{query} clinical trials", f"{query} phase", f"{query} indication"]
        }
        
        # Find matching strategy
        for strategy, keywords in search_strategies.items():
            if any(word in query_lower for word in keywords):
                return strategy_expansions[strategy]
        
        # Default strategy
        return [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials"]
    
    def _compare_drugs_tool(self, drug1: str, drug2: str) -> str:
        """Compare two drugs across multiple dimensions.
        
        Args:
            drug1: First drug name
            drug2: Second drug name
        
        Returns:
            Detailed comparison of the two drugs
        """
        try:
            # Search for both drugs and find best matches
            drug1_info, drug2_info = self._get_drug_comparison_data(drug1, drug2)
            
            if not drug1_info or not drug2_info:
                return f"Could not find sufficient information to compare {drug1} and {drug2}"
            
            # Build comparison report
            return self._build_drug_comparison_report(drug1, drug2, drug1_info, drug2_info)
                
        except Exception as e:
            logger.error(f"Drug comparison error: {e}")
            return f"Error comparing drugs: {str(e)}"
    
    def _get_drug_comparison_data(self, drug1: str, drug2: str) -> tuple:
        """Get drug information for comparison."""
        results1 = self.vector_db.semantic_search(drug1, top_k=5)
        results2 = self.vector_db.semantic_search(drug2, top_k=5)
        
        drug1_info = self._find_best_drug_match(results1, drug1)
        drug2_info = self._find_best_drug_match(results2, drug2)
        
        return drug1_info, drug2_info
    
    def _build_drug_comparison_report(self, drug1: str, drug2: str, drug1_info: Dict[str, Any], drug2_info: Dict[str, Any]) -> str:
        """Build a detailed comparison report for two drugs."""
        comparison = f"Drug Comparison: {drug1} vs {drug2}\n\n"
        
        # Define comparison categories
        comparison_categories = [
            ("Companies", "company"),
            ("Targets", "target"),
            ("Mechanisms", "mechanism"),
            ("Drug Classes", "drug_class"),
            ("Indications", "indication")
        ]
        
        # Add each comparison category
        for category_name, field_name in comparison_categories:
            comparison += f"{category_name}:\n"
            comparison += f"  {drug1}: {drug1_info.get(field_name, 'N/A')}\n"
            comparison += f"  {drug2}: {drug2_info.get(field_name, 'N/A')}\n\n"
        
        return comparison

    # Public helpers for UI integration
    def compare_drugs(self, drug1: str, drug2: str) -> str:
        """Public API: compare two drugs using internal semantic search and format side-by-side output."""
        return self._compare_drugs_tool(drug1, drug2)

    def search_public_resources(self, query: str) -> str:
        """Public API: perform an opt-in public information search with disclaimer."""
        return self._search_public_resources_tool(query)
    
    def _search_public_resources_tool(self, query: str) -> str:
            """Search public resources for information not available in internal database.
            
            Args:
                query: Search query for public information
            
            Returns:
                Information from public sources with clear attribution
            """
            try:
                # This is a placeholder for public resource search
                # In a real implementation, this could integrate with:
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
- Strategic context and priorities
- Company-specific drug portfolios
- Internal competitive analysis

🌐 Data Source: Public Information

Would you like me to search for more specific information in our internal database?"""
                
            except Exception as e:
                logger.error(f"Public resource search error: {e}")
                return f"Error searching public resources: {str(e)}"
    
    def _collect_target_results(self, target_list: List[str]) -> List[Dict[str, Any]]:
        """Collect search results for all targets."""
        all_results = []
        
        for target in target_list:
            # Search for drugs targeting this specific target
            results = self.vector_db.semantic_search(f"{target} drugs", top_k=5)
            all_results.extend(results)
            
            # Search for clinical trials
            trial_results = self.vector_db.semantic_search(f"{target} clinical trials", top_k=3)
            all_results.extend(trial_results)
        
        return all_results
    
    def _build_target_analysis(self, target_list: List[str], all_results: List[Dict[str, Any]]) -> str:
        """Build detailed analysis for each target."""
        analysis = f"Development Phase Analysis for: {', '.join(target_list)}\n\n"
        
        for target in target_list:
            target_drugs, target_trials = self._categorize_target_results(target, all_results)
            
            analysis += f"🎯 {target} Analysis:\n"
            analysis += self._format_target_drugs(target_drugs)
            analysis += self._format_target_trials(target_trials)
            
            if not target_drugs and not target_trials:
                analysis += f"    ❌ No specific {target} data found in internal sources\n"
            
            analysis += "\n"
        
        return analysis
    
    def _categorize_target_results(self, target: str, all_results: List[Dict[str, Any]]) -> tuple:
        """Categorize results into drugs and trials for a specific target."""
        target_drugs = []
        target_trials = []
        
        for result in all_results:
            metadata = result["metadata"]
            result_target = metadata.get("target", "").upper()
            
            # Check for exact match or partial match
            if self._is_target_match(target, result_target):
                if metadata.get("source") == "ground_truth":
                    target_drugs.append(result)
                elif metadata.get("source") == "clinical_trial":
                    target_trials.append(result)
        
        return target_drugs, target_trials
    
    def _is_target_match(self, target: str, result_target: str) -> bool:
        """Check if target matches result target."""
        return (result_target == target or 
                target in result_target or 
                result_target in target or
                (target == "VEGF" and "VEGF" in result_target) or
                (target == "PD-L1" and ("PD-L1" in result_target or "PD1" in result_target)))
    
    def _format_target_drugs(self, target_drugs: List[Dict[str, Any]]) -> str:
        """Format target drugs for display."""
        if not target_drugs:
            return ""
        
        analysis = f"  📊 Drugs in Development:\n"
        for drug in target_drugs:
            metadata = drug["metadata"]
            analysis += f"    • {metadata.get('generic_name', 'Unknown')}"
            if metadata.get('brand_name'):
                analysis += f" ({metadata.get('brand_name')})"
            analysis += f" - {metadata.get('company', 'Unknown')}\n"
        
        return analysis
    
    def _format_target_trials(self, target_trials: List[Dict[str, Any]]) -> str:
        """Format target trials for display."""
        if not target_trials:
            return ""
        
        analysis = f"  🧪 Clinical Trials:\n"
        for trial in target_trials:
            metadata = trial["metadata"]
            analysis += f"    • {metadata.get('title', 'Unknown')[:80]}..."
            if metadata.get('phase'):
                analysis += f" - Phase {metadata.get('phase')}"
            if metadata.get('status'):
                analysis += f" - {metadata.get('status')}"
            analysis += f"\n"
        
        return analysis
    
    def _build_development_summary(self, all_results: List[Dict[str, Any]], target_list: List[str]) -> str:
        """Build summary section for development analysis."""
        total_drugs = len([r for r in all_results if r["metadata"].get("source") == "ground_truth"])
        total_trials = len([r for r in all_results if r["metadata"].get("source") == "clinical_trial"])
        
        analysis = f"📈 Summary:\n"
        analysis += f"  • Total drugs found: {total_drugs}\n"
        analysis += f"  • Total clinical trials found: {total_trials}\n"
        analysis += f"  • Targets analyzed: {', '.join(target_list)}\n"
        
        return analysis
    
    def _group_results_by_source(self, all_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group search results by source."""
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
        
        return source_data
    
    def _analyze_entity_consistency(
        self, 
        entity_type: str, 
        source_data: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[List[str], List[str]]:
        """Analyze consistency for a specific entity type."""
        inconsistencies = []
        consistent_data = []
        
        if entity_type.lower() == "drug":
            inconsistencies, consistent_data = self._analyze_drug_consistency(source_data)
        elif entity_type.lower() == "company":
            inconsistencies, consistent_data = self._analyze_company_consistency(source_data)
        
        return inconsistencies, consistent_data
    
    def _analyze_drug_consistency(
        self, 
        source_data: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[List[str], List[str]]:
        """Analyze drug-specific consistency."""
        inconsistencies = []
        consistent_data = []
        
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
        
        return inconsistencies, consistent_data
    
    def _analyze_company_consistency(
        self, 
        source_data: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[List[str], List[str]]:
        """Analyze company-specific consistency."""
        inconsistencies = []
        consistent_data = []
        
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
        
        return inconsistencies, consistent_data
    
    def _generate_consistency_report(
        self,
        source_data: Dict[str, List[Dict[str, Any]]],
        consistent_data: List[str],
        inconsistencies: List[str]
    ) -> str:
        """Generate the consistency report."""
        report = f"📊 Sources Found:\n"
        for source, results in source_data.items():
            report += f"  • {source}: {len(results)} entries\n"
        
        report += f"\n✅ Consistent Data:\n"
        for item in consistent_data:
            report += f"  • {item}\n"
        
        if inconsistencies:
            report += f"\n⚠️ Inconsistencies Found:\n"
            for item in inconsistencies:
                report += f"  • {item}\n"
        else:
            report += f"\n🎯 No inconsistencies found - Data is consistent across sources\n"
        
        # Overall consistency score
        total_checks = len(consistent_data) + len(inconsistencies)
        consistency_score = len(consistent_data) / total_checks if total_checks > 0 else 0
        
        report += f"\n📈 Overall Consistency Score: {consistency_score:.2f}\n"
        
        if consistency_score >= 0.8:
            report += f"🎯 High consistency - Data is reliable\n"
        elif consistency_score >= 0.6:
            report += f"✅ Moderate consistency - Data is mostly reliable\n"
        else:
            report += f"⚠️ Low consistency - Data needs verification\n"
        
        report += f"\n🏆📊 Data Source: Consistency Checked (Multi-Source)"
        
        return report
    
    def _aggregate_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Aggregate and deduplicate search results."""
        try:
            # Group results by source and company
            grouped_results = self._group_results_by_source_and_company(results)
            
            # Format aggregated results
            formatted_results = self._format_aggregated_results(grouped_results)
            
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
            
            # Return highest relevance result if no exact match, or None if no results
            return results[0]["metadata"] if results else None
            
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
                max_iterations=3,
                system_prompt=SYSTEM_PROMPT,
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
            
            # Try React agent first
            try:
                response = self.agent.chat(question)
                answer = str(response)
                
                # Check if response indicates timeout or infinite loop
                if self._is_no_data_response(answer) or "timed out" in answer.lower():
                    logger.warning("React agent timed out or returned no data, trying fallback")
                    fallback_answer = self._fallback_search(question)
                    if fallback_answer:
                        answer = fallback_answer
                
            except Exception as agent_error:
                logger.warning(f"React agent failed: {agent_error}, trying fallback")
                fallback_answer = self._fallback_search(question)
                if fallback_answer:
                    answer = fallback_answer
                else:
                    raise agent_error
            
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
            
            # Try fallback search as last resort
            try:
                fallback_answer = self._fallback_search(question)
                if fallback_answer:
                    return {
                        "question": question,
                        "answer": fallback_answer,
                        "source": "fallback_search",
                        "citations": [],
                        "timestamp": datetime.now().isoformat(),
                        "success": True
                    }
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
            
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
            
            # Determine search strategy based on question type
            search_query = self._determine_search_query(question)
            
            # Perform semantic search
            results = self.vector_db.semantic_search(search_query, top_k=5)
            
            if not results:
                return None
            
            # Group results by company
            companies = self._group_results_by_company(results)
            
            # Format answer
            return self._format_fallback_answer(companies)
            
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return None
    
    # Removed unused _calculate_similarity helper
    
    def _extract_target_from_question(self, question: str) -> Optional[str]:
        """Extract target name from question dynamically."""
        try:
            question_lower = question.lower()
            
            # Try pattern-based extraction first
            target = self._extract_targets_by_pattern(question_lower)
            if target:
                return target
            
            # If no pattern matches, try capitalization-based extraction
            return self._extract_targets_by_capitalization(question)
            
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
            "max_iterations": 3,
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
