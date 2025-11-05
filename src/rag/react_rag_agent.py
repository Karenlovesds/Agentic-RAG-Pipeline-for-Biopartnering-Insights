"""
React Framework RAG Agent using LlamaIndex

This agent implements the React (Reasoning + Acting + Observing) framework
for reliable and accurate responses through iterative reasoning.

Core functionality:
- Semantic search across all data sources via vector embeddings
- Multi-query search for complex questions
- Ground Truth priority: Always lists Ground Truth items FIRST, then Database items
- Comprehensive listing: Explicitly lists ALL companies/drugs/targets (no "among others")
"""

from typing import List, Dict, Any, Optional, Set
from loguru import logger
import sys
import re
from pathlib import Path
from datetime import datetime
import os
# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from llama_index.core.memory import ChatMemoryBuffer

from src.rag.vector_db_manager import VectorDBManager

# Target normalization and synonym mapping
TARGET_SYNONYMS = {
    # PD-1 variants
    "PD-1": ["PD1", "PD 1", "CD279", "programmed death 1"],
    "PD1": ["PD-1", "PD 1", "CD279", "programmed death 1"],
    "PD 1": ["PD-1", "PD1", "CD279", "programmed death 1"],
    "CD279": ["PD-1", "PD1", "PD 1", "programmed death 1"],
    
    # PD-L1 variants
    "PD-L1": ["PDL1", "PD L1", "CD274", "B7-H1", "programmed death ligand 1"],
    "PDL1": ["PD-L1", "PD L1", "CD274", "B7-H1", "programmed death ligand 1"],
    "PD L1": ["PD-L1", "PDL1", "CD274", "B7-H1", "programmed death ligand 1"],
    "CD274": ["PD-L1", "PDL1", "PD L1", "B7-H1", "programmed death ligand 1"],
    "B7-H1": ["PD-L1", "PDL1", "PD L1", "CD274", "programmed death ligand 1"],
    
    # HER2 variants
    "HER2": ["HER-2", "ERBB2", "HER 2", "Neu", "NEU"],
    "HER-2": ["HER2", "ERBB2", "HER 2", "Neu", "NEU"],
    "HER 2": ["HER2", "HER-2", "ERBB2", "Neu", "NEU"],
    "ERBB2": ["HER2", "HER-2", "HER 2", "Neu", "NEU"],
    "Neu": ["HER2", "HER-2", "ERBB2", "HER 2"],
    
    # CTLA-4 variants
    "CTLA-4": ["CTLA4", "CTLA 4", "CD152"],
    "CTLA4": ["CTLA-4", "CTLA 4", "CD152"],
    "CTLA 4": ["CTLA-4", "CTLA4", "CD152"],
    "CD152": ["CTLA-4", "CTLA4", "CTLA 4"],
    
    # EGFR variants
    "EGFR": ["HER1", "ERBB1"],
    "HER1": ["EGFR", "ERBB1"],
    "ERBB1": ["EGFR", "HER1"],
    
    # VEGFR variants
    "VEGFR": ["VEGFR1", "VEGFR2", "VEGFR3", "FLT1", "KDR", "FLT4"],
    "VEGFR1": ["VEGFR", "FLT1"],
    "VEGFR2": ["VEGFR", "KDR"],
    "VEGFR3": ["VEGFR", "FLT4"],
    
    # CD20 variants
    "CD20": ["CD 20", "MS4A1"],
    "CD 20": ["CD20", "MS4A1"],
    
    # CD19 variants
    "CD19": ["CD 19"],
    "CD 19": ["CD19"],
    
    # KRAS variants
    "KRAS": ["K-RAS", "K RAS"],
    "K-RAS": ["KRAS", "K RAS"],
    "K RAS": ["KRAS", "K-RAS"],
    
    # TROP2 variants
    "TROP2": ["TROP-2", "TROP 2", "TACSTD2"],
    "TROP-2": ["TROP2", "TROP 2", "TACSTD2"],
    "TROP 2": ["TROP2", "TROP-2", "TACSTD2"],
    "TACSTD2": ["TROP2", "TROP-2", "TROP 2"],
    
    # BCL6 variants
    "BCL6": ["BCL-6", "BCL 6"],
    "BCL-6": ["BCL6", "BCL 6"],
    "BCL 6": ["BCL6", "BCL-6"],
    
    # MTAP variants
    "MTAP": ["MT-AP", "MT AP"],
    "MT-AP": ["MTAP", "MT AP"],
}

def normalize_target_name(target: str) -> str:
    """Normalize target name to canonical form."""
    if not target:
        return ""
    
    target = target.strip().upper()
    
    # Remove common variations
    target = target.replace(" ", "-")  # "PD 1" -> "PD-1"
    target = target.replace("_", "-")  # "PD_1" -> "PD-1"
    
    # Check if we have a synonym mapping
    for canonical, variants in TARGET_SYNONYMS.items():
        if target == canonical.upper() or target in [v.upper() for v in variants]:
            return canonical.upper()
    
    return target

def expand_target_query(target: str) -> Set[str]:
    """Expand target query with synonyms."""
    if not target:
        return set()
    
    target_normalized = normalize_target_name(target)
    expanded = {target_normalized}
    
    # Add synonyms
    if target_normalized in TARGET_SYNONYMS:
        expanded.update([s.upper() for s in TARGET_SYNONYMS[target_normalized]])
    
    # Also check if any variant maps to this target
    for canonical, variants in TARGET_SYNONYMS.items():
        if target_normalized in [v.upper() for v in variants]:
            expanded.add(canonical.upper())
            expanded.update([s.upper() for s in TARGET_SYNONYMS[canonical]])
    
    return expanded

def normalize_company_name(company: str) -> str:
    """Normalize company name for deduplication."""
    if not company:
        return ""
    
    company = company.strip()
    # Remove common suffixes
    company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation|Pharmaceuticals?|Pharma|Co\.?)\s*$', '', company, flags=re.IGNORECASE)
    # Normalize separators
    company = company.replace("&", "and").replace("/", " ").replace(",", "")
    # Normalize whitespace
    company = " ".join(company.split())
    return company.lower()

def normalize_drug_name(drug: str) -> str:
    """Normalize drug name for deduplication."""
    if not drug:
        return ""
    
    drug = drug.strip().lower()
    # Remove punctuation variations
    drug = re.sub(r'[-\s]+', '-', drug)
    return drug

# Configuration constants
DEFAULT_TOP_K = 30
MULTI_QUERY_TOP_K = 20
FALLBACK_TOP_K = 20
MAX_ITERATIONS = 3
MAX_LISTED_ITEMS = 30

# Simplified system prompt - condensed from 175 lines to ~80 lines
SYSTEM_PROMPT = """You are a specialized oncology and cancer research assistant focused on biopartnering insights.
You use the React framework (Reasoning + Acting + Observing) to provide accurate, evidence-based responses.

WORKFLOW:
1. REASONING: Analyze the question and determine the best tool to use
2. ACTING: Use semantic_search for most questions - it searches all data sources
3. OBSERVING: Analyze results and provide a comprehensive answer
4. BE CONCISE: Answer in 1-2 iterations maximum for simple questions

CRITICAL: For simple questions like "companies with TROP2", use semantic_search ONCE and provide the answer immediately.

TERMINATION CONDITIONS:
- If you get results from semantic_search, provide the answer immediately
- Do NOT run multiple searches for simple questions
- Do NOT iterate more than 2 times for basic company/target questions
- If you find yourself repeating the same search query, STOP

QUERY STRATEGY:
- For "companies with TROP2": Search "TROP2 targeting companies" or "TROP2 drugs companies"
- For "drugs targeting HER3": Search "HER3 targeting drugs" or "HER3 drugs"
- Use descriptive queries, not single words

AVAILABLE TOOLS:
- semantic_search: PRIMARY tool for ALL questions - searches all data sources via vector embeddings
- multi_query_search: For complex multi-part questions that need multiple searches

DATA SOURCE PRIORITY (CRITICAL ORDER):
1. Ground Truth (HIGHEST PRIORITY - ALWAYS list ALL items from Ground Truth FIRST)
2. Internal Database (SUPPLEMENTARY - add after listing all Ground Truth items)
3. FDA Data (external API but integrated internally)
4. Clinical Trials (external API but integrated internally)
5. Drugs.com (external API but integrated internally)

COMPREHENSIVE LISTING REQUIREMENT:
- CRITICAL: For ANY question type (companies, drugs, targets), you MUST:
  1. FIRST: List ALL items from Ground Truth (highest priority)
  2. THEN: Add items from Internal Database (supplementary information)
- Ground Truth data is the authoritative source - never skip or miss Ground Truth results
- When Ground Truth and Database have the same item, prioritize Ground Truth version

COMPREHENSIVE ENTITY INFORMATION REQUIREMENT:
- When a question asks about ANY target, drug, or company, provide COMPREHENSIVE information:
  1. If question mentions a TARGET: List ALL targets found, ALL drugs targeting them, and ALL companies working on them
  2. If question mentions a DRUG: List ALL drugs found, ALL companies developing them, and ALL targets they address
  3. If question mentions a COMPANY: List ALL companies found, ALL drugs they have, and ALL targets they work on
- Always provide complete context: targets → drugs → companies (interconnected relationships)
- Show all related entities even if not explicitly asked - provide full picture

ABSOLUTE REQUIREMENT - NO "AMONG OTHERS" OR SHORTCUTS:
- NEVER use phrases like "among others", "and others", "etc.", "and more", "including"
- You MUST explicitly list EVERY SINGLE company, drug, or target found in the search results
- Count the items in your search results, then list them ALL by name
- Example WRONG: "Companies include A, B, C, and others"
- Example CORRECT: "Companies: A (drug X), B (drug Y), C (drug Z), D (drug W), E (drug V)"

RESPONSE FORMATTING:
- Use structured formatting with bullet points (•) for clarity
- Format companies with their drugs: "🏢 Company Name:\n  • Drug 1 (details)\n  • Drug 2 (details)"
- Include drug codes/names, targets, mechanisms, and phases in parentheses
- Structure: "[Ground Truth items]; [Database items]" - always in this order

TABLE FORMATTING REQUIREMENT (CRITICAL):
- When question asks for "table", "make a table", "create a table", "format as table", or similar, you MUST:
  1. Use the search results to extract ALL companies with the target/drug
  2. Format as a Markdown table with columns: Company | Drug(s) | Target(s) | Mechanism | Phase/Status | Source
  3. ALWAYS include ALL companies from Ground Truth FIRST, then Database companies
  4. Do NOT say "I was unable to find" or "However, I was unable" - use the search results provided
  5. The search tools will provide table-ready data - USE IT to build the table
  6. One row per company with all their drugs listed in the Drug(s) column (comma-separated)
- Example table format:
  | Company | Drug(s) | Target(s) | Mechanism | Phase/Status | Source |
  |---------|---------|-----------|-----------|--------------|--------|
  | Company 1 | Drug 1, Drug 2 | HER2 | Monoclonal antibody | Approved | 🏆 Ground Truth |
  | Company 2 | Drug 3 | HER2 | ADC | Phase 3 | 📊 Database |
- If search results show companies, list them ALL in the table - do not say "unable to find"

EXAMPLES OF GOOD RESPONSES:

KRAS inhibitor question:
"Roche: Divarasib (GDC-6036 / RG6330, KRAS G12C); RG6620 (GDC-7035, KRAS G12D). Amgen: LUMAKRAS (sotorasib, KRAS G12C) – approved in KRAS G12C-mutated NSCLC; clinical trials include NSCLC and advanced colorectal cancer. Merck: MK-1084 (KRAS G12C). Eli Lilly: Olomorasib (KRAS G12C); KRAS G12D program (KRAS G12D); LY4066434 (pan-KRAS)."

BCL6 question:
"Arvinas: ARV-393 (oral BCL6 PROTAC degrader, Phase 1, advanced NHL). Bristol Myers Squibb: BMS-986458 (BCL6 degrader, Phase 1, NHL). Treeline Biosciences: TLN-121 (BCL6 degrader, Phase 1, relapsed/refractory NHL)."

If no internal data found, use this format:
"❓ I don't know - No relevant information found in our internal database or ground truth data.
Would you like me to search public resources for this information?"
"""


class ReactRAGAgent:
    """React Framework RAG Agent for reliable biopharmaceutical insights."""
    
    # do not touch this part as it is used for deployment
    def __init__(self, config):
        self.config = config
        
        # Initialize vector database manager
        self.vector_db = VectorDBManager()
        
        # Initialize Ollama LLM for React agent
        self.llm = Ollama(
            model="llama3.1",
            request_timeout=300.0,  # Reduced from 300 to 60 seconds
            temperature=0.0  # Set to 0 for maximum consistency
        )
        
        # Create tools for the React agent
        self.tools = self._create_tools()
        
        # Initialize React agent
        self.agent = self._create_react_agent()
        
        logger.info("React RAG Agent with Vector Database initialized successfully")

    # do not touch this part as it is used for deployment


    def _create_tools(self) -> List[FunctionTool]:
        """Create tools for the React agent."""
        return [
            FunctionTool.from_defaults(fn=self._semantic_search_tool, name="semantic_search"),
            FunctionTool.from_defaults(fn=self._multi_query_search_tool, name="multi_query_search")
        ]
    
    def _semantic_search_tool(self, query: str, top_k: int = DEFAULT_TOP_K) -> str:
        """Perform semantic search across all biopharmaceutical data.
        
        Args:
            query: Search query (drug name, company name, target, mechanism, etc.)
            top_k: Number of top results to return (default: 30)
        
        Returns:
            Formatted results from semantic search with relevance scores
        """
        try:
            # PRIORITY 1: Apply query expansion and normalization
            # Extract target and expand with synonyms
            original_query = query
            target = self._extract_target_from_question(query)
            expanded_targets = set()
            if target:
                expanded_targets = expand_target_query(target)
            
            # Normalize query before embedding
            normalized_query = query
            if target:
                # Replace target in query with normalized version
                normalized_query = query.replace(target, normalize_target_name(target))
            
            # PRIORITY 5: Detect "list all" queries and increase top_k
            query_lower = query.lower()
            is_list_all_query = any(phrase in query_lower for phrase in ['list all', 'all companies', 'all drugs', 'all targets', 'show all', 'give me all'])
            
            # PRIORITY 5: Increase top_k for comprehensive queries
            if is_list_all_query:
                top_k = max(top_k, 80)  # Much higher for "list all" queries
            elif any(word in query_lower for word in ['target', 'targeting', 'targets', 'companies with', 'drugs for']):
                top_k = max(top_k, 50)  # Increase for target searches
            
            # PRIORITY 1: Use expanded query for search (if target found)
            search_query = normalized_query
            if expanded_targets and len(expanded_targets) > 1:
                # Create expanded query with OR for synonyms
                target_queries = [f"{t}" for t in list(expanded_targets)[:5]]  # Limit to 5 expansions
                # For "companies with HER2" type queries, expand properly
                if 'company' in query_lower or 'companies' in query_lower:
                    expanded_queries = [f"{t} companies drugs" for t in target_queries]
                    search_query = " OR ".join(expanded_queries[:3])  # Use top 3 for search
                elif 'drug' in query_lower or 'drugs' in query_lower:
                    expanded_queries = [f"{t} drugs" for t in target_queries]
                    search_query = " OR ".join(expanded_queries[:3])
                else:
                    search_query = " OR ".join(target_queries[:3])
            
            # Perform semantic search with expanded/normalized query
            results = self.vector_db.semantic_search(search_query, top_k)
            
            if not results:
                return f"No semantic search results found for '{query}'"
            
            # Extract ALL entities: companies, drugs, and targets (comprehensive extraction with normalization)
            companies_gt = set()
            companies_db = set()
            drugs_gt = set()
            drugs_db = set()
            targets_gt = set()
            targets_db = set()
            
            # Normalize company names for deduplication
            company_normalized_map = {}  # normalized -> canonical
            
            for result in results:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "").strip()
                drug = metadata.get("generic_name", "").strip() or metadata.get("brand_name", "").strip()
                target_str = metadata.get("target", "").strip()
                
                # Normalize and deduplicate companies
                if company and company != "Unknown":
                    company_norm = normalize_company_name(company)
                    if company_norm:
                        # Use canonical form (first occurrence)
                        if company_norm not in company_normalized_map:
                            company_normalized_map[company_norm] = company
                        canonical_company = company_normalized_map[company_norm]
                        
                        if source == "ground_truth":
                            companies_gt.add(canonical_company)
                        elif source == "database":
                            companies_db.add(canonical_company)
                
                # Normalize drug names
                if drug:
                    drug_norm = normalize_drug_name(drug)
                    if drug_norm:
                        if source == "ground_truth":
                            drugs_gt.add(drug)  # Keep original for display
                        elif source == "database":
                            drugs_db.add(drug)
                
                # Normalize and expand targets
                if target_str and target_str != "N/A":
                    # Handle comma-separated targets
                    targets = [t.strip() for t in target_str.split(',')]
                    for target in targets:
                        if target:
                            target_normalized = normalize_target_name(target)
                            if target_normalized:
                                if source == "ground_truth":
                                    targets_gt.add(target_normalized)
                                elif source == "database":
                                    targets_db.add(target_normalized)
            
            # Format all results
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(self._format_search_result(result, i))
            
            # Generate comprehensive summary with ALL entities (targets, drugs, companies)
            summary = self._generate_search_summary(
                results, query, 
                companies_gt, companies_db, 
                drugs_gt, drugs_db,
                targets_gt, targets_db
            )
            
            # PRIORITY 7: Add explicit instruction in tool output
            explicit_instruction = "\n\n" + "="*80
            explicit_instruction += "\n⚠️ CRITICAL INSTRUCTION - YOU MUST FOLLOW THIS:"
            explicit_instruction += f"\nYou found {len(companies_gt) + len(companies_db)} total companies in the search results above."
            if companies_gt:
                explicit_instruction += f"\n🏆 Ground Truth companies ({len(companies_gt)}): {', '.join(sorted(companies_gt))}"
            if companies_db:
                explicit_instruction += f"\n📊 Database companies ({len(companies_db)}): {', '.join(sorted(companies_db))}"
            explicit_instruction += f"\n\nYOU MUST list ALL {len(companies_gt) + len(companies_db)} companies by name in your answer."
            explicit_instruction += "\nDO NOT use phrases like 'other companies', 'among others', 'etc.', or any vague shortcuts."
            explicit_instruction += "\nList every single company name explicitly with their drugs and details."
            explicit_instruction += "\n" + "="*80
            
            # Check if table format is requested
            query_lower = query.lower()
            is_table_request = any(word in query_lower for word in ['table', 'make a table', 'create a table', 'format as table'])
            
            if is_table_request:
                # Generate table-ready data
                table_data = self._generate_table_data(results, companies_gt, companies_db, drugs_gt, drugs_db, targets_gt, targets_db)
                return f"Semantic Search Results for '{query}':\n" + "\n".join(formatted_results) + summary + explicit_instruction + table_data
            
            return f"Semantic Search Results for '{query}':\n" + "\n".join(formatted_results) + summary + explicit_instruction
                
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return f"Error in semantic search: {str(e)}"
        
    def _multi_query_search_tool(self, query: str) -> str:
        """Perform multiple related searches for complex questions.
        
        Args:
            query: Complex search query (e.g., "TROP2 competitive landscape", "compare Merck and Gilead drugs")
        
        Returns:
            Aggregated results from multiple related searches
        """
        try:
            # PRIORITY 6: Automatically trigger multi-query for "list all" queries
            query_lower = query.lower()
            is_list_all_query = any(phrase in query_lower for phrase in ['list all', 'all companies', 'all drugs', 'all targets', 'show all', 'give me all'])
            
            if is_list_all_query:
                # Extract target and expand
                target = self._extract_target_from_question(query)
                expanded_targets = set()
                if target:
                    expanded_targets = expand_target_query(target)
                
                # Create comprehensive search queries
                search_queries = []
                if expanded_targets:
                    for t in list(expanded_targets)[:3]:
                        search_queries.append(f"{t} companies drugs")
                        search_queries.append(f"{t} targeting companies")
                        search_queries.append(f"{t} drugs companies")
                else:
                    search_queries = [query, f"{query} companies", f"{query} drugs", f"{query} targeting"]
            else:
                search_queries = self._determine_search_strategy(query)
            
            # Execute multiple searches
            all_results = []
            for search_query in search_queries[:4]:  # Limit to 4 searches
                results = self.vector_db.semantic_search(search_query, top_k=MULTI_QUERY_TOP_K)
                all_results.extend(results)
            
            # Extract ALL entities: companies, drugs, and targets (comprehensive extraction with normalization)
            companies_gt = set()
            companies_db = set()
            drugs_gt = set()
            drugs_db = set()
            targets_gt = set()
            targets_db = set()
            
            # Normalize company names for deduplication
            company_normalized_map = {}  # normalized -> canonical
            
            for result in all_results:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "").strip()
                drug = metadata.get("generic_name", "").strip() or metadata.get("brand_name", "").strip()
                target_str = metadata.get("target", "").strip()
                
                # Normalize and deduplicate companies
                if company and company != "Unknown":
                    company_norm = normalize_company_name(company)
                    if company_norm:
                        if company_norm not in company_normalized_map:
                            company_normalized_map[company_norm] = company
                        canonical_company = company_normalized_map[company_norm]
                        
                        if source == "ground_truth":
                            companies_gt.add(canonical_company)
                        elif source == "database":
                            companies_db.add(canonical_company)
                
                # Normalize drug names
                if drug:
                    drug_norm = normalize_drug_name(drug)
                    if drug_norm:
                        if source == "ground_truth":
                            drugs_gt.add(drug)  # Keep original for display
                        elif source == "database":
                            drugs_db.add(drug)
                
                # Normalize and expand targets
                if target_str and target_str != "N/A":
                    targets = [t.strip() for t in target_str.split(',')]
                    for target in targets:
                        if target:
                            target_normalized = normalize_target_name(target)
                            if target_normalized:
                                if source == "ground_truth":
                                    targets_gt.add(target_normalized)
                                elif source == "database":
                                    targets_db.add(target_normalized)
            
            # Aggregate and deduplicate results
            aggregated_results = self._aggregate_search_results(all_results)
            
            # Add comprehensive entity lists (Ground Truth first)
            if companies_gt or companies_db:
                aggregated_results += f"\n\n{'='*60}"
                aggregated_results += f"\n🏢 COMPANIES FOUND:"
                if companies_gt:
                    aggregated_results += f"\n   🏆 Ground Truth ({len(companies_gt)} companies) - You MUST list ALL:"
                    for i, company in enumerate(sorted(companies_gt), 1):
                        aggregated_results += f"\n      {i}. {company}"
                if companies_db:
                    aggregated_results += f"\n   📊 Database ({len(companies_db)} companies - supplementary):"
                    for i, company in enumerate(sorted(companies_db), 1):
                        aggregated_results += f"\n      {i}. {company}"
                aggregated_results += f"\n{'='*60}"
            
            if drugs_gt or drugs_db:
                aggregated_results += f"\n\n{'='*60}"
                aggregated_results += f"\n💊 DRUGS FOUND:"
                if drugs_gt:
                    aggregated_results += f"\n   🏆 Ground Truth ({len(drugs_gt)} drugs) - You MUST list ALL:"
                    for i, drug in enumerate(sorted(drugs_gt), 1):
                        aggregated_results += f"\n      {i}. {drug}"
                if drugs_db:
                    aggregated_results += f"\n   📊 Database ({len(drugs_db)} drugs - supplementary):"
                    for i, drug in enumerate(sorted(drugs_db), 1):
                        aggregated_results += f"\n      {i}. {drug}"
                aggregated_results += f"\n{'='*60}"
            
            if targets_gt or targets_db:
                aggregated_results += f"\n\n{'='*60}"
                aggregated_results += f"\n🎯 TARGETS FOUND:"
                if targets_gt:
                    aggregated_results += f"\n   🏆 Ground Truth ({len(targets_gt)} targets) - You MUST list ALL:"
                    for i, target in enumerate(sorted(targets_gt), 1):
                        aggregated_results += f"\n      {i}. {target}"
                if targets_db:
                    aggregated_results += f"\n   📊 Database ({len(targets_db)} targets - supplementary):"
                    for i, target in enumerate(sorted(targets_db), 1):
                        aggregated_results += f"\n      {i}. {target}"
                aggregated_results += f"\n{'='*60}"
            
            # Check if table format is requested
            query_lower = query.lower()
            is_table_request = any(word in query_lower for word in ['table', 'make a table', 'create a table', 'format as table'])
            
            if is_table_request:
                # Generate table-ready data
                table_data = self._generate_table_data(all_results, companies_gt, companies_db, drugs_gt, drugs_db, targets_gt, targets_db)
                if aggregated_results:
                    return f"Multi-Query Analysis for '{query}':\n" + aggregated_results + table_data
                else:
                    return f"Multi-Query Analysis for '{query}':\n{table_data}"
            
            if aggregated_results:
                return f"Multi-Query Analysis for '{query}':\n" + aggregated_results
            else:
                return f"No comprehensive results found for '{query}'"
                
        except Exception as e:
            logger.error(f"Multi-query search error: {e}")
            return f"Error in multi-query search: {str(e)}"
    
    def _format_search_result(self, result: Dict[str, Any], index: int) -> str:
        """Format a single search result based on its source."""
        metadata = result.get("metadata", {})
        similarity_score = result.get("similarity_score", 0)
        source = metadata.get("source", "unknown")
        
        # Formatting templates for each source type
        templates = {
            "ground_truth": (
                f"{index}. 🏆 GROUND TRUTH: {metadata.get('generic_name', 'N/A')} ({metadata.get('brand_name', 'N/A')}) "
                f"- Company: {metadata.get('company', 'N/A')} - Target: {metadata.get('target', 'N/A')} "
                f"- Mechanism: {metadata.get('mechanism', 'N/A')}"
            ),
            "database": (
                f"{index}. 📊 DATABASE: {metadata.get('generic_name', 'N/A')} ({metadata.get('brand_name', 'N/A')}) "
                f"- Company: {metadata.get('company', 'N/A')} - Mechanism: {metadata.get('mechanism', 'N/A')} "
                f"- Drug Class: {metadata.get('drug_class', 'N/A')} (Relevance: {similarity_score:.3f})"
            ),
            "clinical_trial": (
                f"{index}. 🧪 CLINICAL TRIAL: {metadata.get('nct_id', 'N/A')} - Phase: {metadata.get('phase', 'N/A')} "
                f"- Status: {metadata.get('status', 'N/A')} (Relevance: {similarity_score:.3f})"
            ),
            "fda": (
                f"{index}. 🏥 FDA: {metadata.get('generic_name', 'N/A')} ({metadata.get('brand_name', 'N/A')}) "
                f"- Company: {metadata.get('company', 'N/A')} - Approval Date: {metadata.get('fda_approval_date', 'N/A')} "
                f"- Targets: {metadata.get('target', 'N/A')} (Relevance: {similarity_score:.3f})"
            ),
            "drugs_com": (
                f"{index}. 💊 DRUGS.COM: {metadata.get('title', 'N/A')} "
                f"- Source: {metadata.get('url', 'N/A')} (Relevance: {similarity_score:.3f})"
            )
        }
        
        return templates.get(source, 
            f"{index}. {source.upper()}: {metadata.get('generic_name', metadata.get('title', 'Unknown'))} "
            f"- Company: {metadata.get('company', 'N/A')} (Relevance: {similarity_score:.3f})"
        )
    
    def _generate_search_summary(self, results: List[Dict[str, Any]], query: str, 
                                 companies_gt: set = None, companies_db: set = None,
                                 drugs_gt: set = None, drugs_db: set = None,
                                 targets_gt: set = None, targets_db: set = None) -> str:
        """Generate concise summary with key entities found."""
        # Deduplicate and normalize all sets
        all_companies = sorted(set((companies_gt or set()) | (companies_db or set())))
        all_targets = sorted(set((targets_gt or set()) | (targets_db or set())))
        all_drugs = sorted(set((drugs_gt or set()) | (drugs_db or set())))
        
        summary = f"\n📊 Summary for '{query}' - Total results: {len(results)}"
        
        # Concise entity counts (limit display to prevent huge responses)
        if all_companies:
            summary += f"\n\n🏢 Companies ({len(all_companies)}):"
            if len(all_companies) > 15:
                summary += f" {', '.join(all_companies[:15])}... and {len(all_companies)-15} more"
            else:
                summary += f" {', '.join(all_companies)}"
        
        if all_targets:
            summary += f"\n\n🎯 Targets ({len(all_targets)}):"
            if len(all_targets) > 15:
                summary += f" {', '.join(all_targets[:15])}... and {len(all_targets)-15} more"
            else:
                summary += f" {', '.join(all_targets)}"
        
        if all_drugs:
            summary += f"\n\n💊 Drugs ({len(all_drugs)}):"
            if len(all_drugs) > 15:
                summary += f" {', '.join(all_drugs[:15])}... and {len(all_drugs)-15} more"
            else:
                summary += f" {', '.join(all_drugs)}"
        
        # Sources found
        sources_found = {r.get("metadata", {}).get("source", "unknown") for r in results}
        source_labels = {
            "ground_truth": "Ground Truth",
            "database": "Database",
            "clinical_trial": "Clinical Trial",
        }
        included = [label for key, label in source_labels.items() if key in sources_found]
        if included:
            summary += f"\n\nSources: {', '.join(included)}"
        
        # Concise reminder
        if companies_gt or companies_db:
            total_companies = len(companies_gt or set()) + len(companies_db or set())
            summary += f"\n\n⚠️ List ALL {total_companies} companies found above. DO NOT use 'among others', 'etc.', or shortcuts."
        
        return summary
    
    def _generate_table_data(self, results: List[Dict[str, Any]], 
                            companies_gt: set, companies_db: set,
                            drugs_gt: set, drugs_db: set,
                            targets_gt: set, targets_db: set) -> str:
        """Generate table-ready data structure for companies with targets/drugs."""
        # Build company -> (drugs, targets, mechanisms) mapping
        company_data = {}
        
        # Process all results to build comprehensive company data
        for result in results:
            metadata = result.get("metadata", {})
            source = metadata.get("source", "unknown")
            company = metadata.get("company", "").strip()
            drug = metadata.get("generic_name", "").strip() or metadata.get("brand_name", "").strip()
            target = metadata.get("target", "").strip()
            mechanism = metadata.get("mechanism", "").strip()
            phase = metadata.get("phase", "").strip() or metadata.get("status", "").strip()
            
            if not company or company == "Unknown":
                continue
            
            # Prioritize Ground Truth over Database
            if company not in company_data:
                company_data[company] = {
                    "source": "ground_truth" if source == "ground_truth" else "database",
                    "drugs": set(),
                    "targets": set(),
                    "mechanisms": set(),
                    "phases": set()
                }
            elif source == "ground_truth" and company_data[company]["source"] == "database":
                # Upgrade to Ground Truth if found
                company_data[company]["source"] = "ground_truth"
            
            if drug:
                company_data[company]["drugs"].add(drug)
            if target and target != "N/A":
                company_data[company]["targets"].add(target)
            if mechanism:
                company_data[company]["mechanisms"].add(mechanism)
            if phase:
                company_data[company]["phases"].add(phase)
        
        if not company_data:
            return "\n\n📊 TABLE FORMAT:\nNo company data found to create table."
        
        # Build table markdown
        table_lines = []
        table_lines.append("\n\n" + "="*80)
        table_lines.append("📊 TABLE FORMAT (Markdown):")
        table_lines.append("="*80)
        table_lines.append("\n| Company | Drug(s) | Target(s) | Mechanism | Phase/Status | Source |")
        table_lines.append("|---------|---------|-----------|-----------|--------------|--------|")
        
        # Sort companies: Ground Truth first, then Database
        companies_gt_list = sorted([c for c, data in company_data.items() if data["source"] == "ground_truth"])
        companies_db_list = sorted([c for c, data in company_data.items() if data["source"] == "database"])
        all_companies = companies_gt_list + companies_db_list
        
        for company in all_companies:
            data = company_data[company]
            drugs_str = ", ".join(sorted(data["drugs"])) if data["drugs"] else "N/A"
            targets_str = ", ".join(sorted(data["targets"])) if data["targets"] else "N/A"
            mechanisms_str = ", ".join(sorted(data["mechanisms"])) if data["mechanisms"] else "N/A"
            phases_str = ", ".join(sorted(data["phases"])) if data["phases"] else "N/A"
            source_str = "🏆 Ground Truth" if data["source"] == "ground_truth" else "📊 Database"
            
            table_lines.append(f"| {company} | {drugs_str} | {targets_str} | {mechanisms_str} | {phases_str} | {source_str} |")
        
        table_lines.append("\n" + "="*80)
        table_lines.append(f"\n⚠️ CRITICAL: Use the above table data to create a Markdown table in your answer.")
        table_lines.append(f"Total companies found: {len(all_companies)} ({len(companies_gt_list)} from Ground Truth, {len(companies_db_list)} from Database)")
        table_lines.append("="*80)
        
        return "\n".join(table_lines)
    
    def _group_results_by_source_and_company(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group search results by source and company with normalization for deduplication."""
        grouped_results = {}
        seen_gt_drugs = set()  # Track Ground Truth drugs to prevent duplicates (normalized)
        company_normalized_map = {}  # normalized -> canonical
        
        # First pass: Collect all Ground Truth results
        for result in results:
            try:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "Unknown")
                drug_name = metadata.get("generic_name", "")
                
                if source == "ground_truth" and company and company != "Unknown" and company.strip():
                    # Normalize company name
                    company_norm = normalize_company_name(company)
                    if company_norm:
                        if company_norm not in company_normalized_map:
                            company_normalized_map[company_norm] = company
                        canonical_company = company_normalized_map[company_norm]
                        
                        if source not in grouped_results:
                            grouped_results[source] = {}
                        if canonical_company not in grouped_results[source]:
                            grouped_results[source][canonical_company] = []
                        
                        grouped_results[source][canonical_company].append(result)
                        # Use normalized key for deduplication
                        drug_norm = normalize_drug_name(drug_name)
                        drug_key = f"{drug_norm}_{company_norm}"
                        seen_gt_drugs.add(drug_key)
            except Exception as e:
                logger.debug(f"Error processing Ground Truth result: {e}")
                continue
        
        # Second pass: Add Database results (skip if already in Ground Truth)
        for result in results:
            try:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "Unknown")
                drug_name = metadata.get("generic_name", "")
                
                if source == "database" and company and company != "Unknown" and company.strip():
                    # Normalize for deduplication
                    company_norm = normalize_company_name(company)
                    drug_norm = normalize_drug_name(drug_name)
                    drug_key = f"{drug_norm}_{company_norm}"
                    
                    if drug_key in seen_gt_drugs:
                        continue  # Skip duplicate - Ground Truth takes priority
                    
                    if company_norm:
                        if company_norm not in company_normalized_map:
                            company_normalized_map[company_norm] = company
                        canonical_company = company_normalized_map[company_norm]
                        
                        if source not in grouped_results:
                            grouped_results[source] = {}
                        if canonical_company not in grouped_results[source]:
                            grouped_results[source][canonical_company] = []
                        
                        grouped_results[source][canonical_company].append(result)
            except Exception as e:
                logger.debug(f"Error processing Database result: {e}")
                continue
        
        # Third pass: Add other sources (clinical_trial, fda, drugs_com) without deduplication
        for result in results:
            try:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "unknown")
                company = metadata.get("company", "Unknown")
                
                if source not in ["ground_truth", "database"] and company and company != "Unknown" and company.strip():
                    if source not in grouped_results:
                        grouped_results[source] = {}
                    if company not in grouped_results[source]:
                        grouped_results[source][company] = []
                    
                    grouped_results[source][company].append(result)
            except Exception as e:
                logger.debug(f"Error processing other source result: {e}")
                continue
            
        return grouped_results
    
    def _format_aggregated_results(self, grouped_results: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> List[str]:
        """Format grouped results with comprehensive entity information (targets, drugs, companies)."""
        formatted_results = []
        
        # CRITICAL: Prioritize Ground Truth results FIRST
        source_order = ["ground_truth", "database", "clinical_trial", "fda", "drugs_com"]
        source_labels = {
            "ground_truth": "🏆 Ground Truth (Primary Data)",
            "database": "📊 Internal Database (Supplementary Data)",
            "clinical_trial": "🧪 Clinical Trials",
            "fda": "🏥 FDA Data",
            "drugs_com": "💊 Drugs.com"
        }
        
        # Extract all entities for comprehensive summary
        all_targets = set()
        all_drugs = set()
        all_companies = set()
        
        for source in source_order:
            if source not in grouped_results:
                continue
            
            companies = grouped_results[source]
            if not companies:
                continue
            
            formatted_results.append(f"\n{source_labels.get(source, source.upper())}:")
                
            for company, drugs in companies.items():
                all_companies.add(company)
                formatted_results.append(f"\n🏢 **{company}**:")
                for drug in drugs:
                    try:
                        metadata = drug.get("metadata", {})
                        generic_name = metadata.get('generic_name', '').strip()
                        brand_name = metadata.get('brand_name', '').strip()
                        target = metadata.get('target', '').strip()
                        
                        # Track all entities (normalize to avoid duplicates)
                        if generic_name:
                            all_drugs.add(generic_name)
                        elif brand_name:
                            all_drugs.add(brand_name)
                        if target and target != "N/A":
                            # Handle comma-separated targets and normalize
                            targets = [t.strip() for t in target.split(',')]
                            for t in targets:
                                if t:
                                    normalized = normalize_target_name(t)
                                    if normalized:
                                        all_targets.add(normalized)
                        
                        # Format drug with comprehensive info
                        if generic_name:
                            drug_text = f"  • {generic_name}"
                            if brand_name:
                                drug_text += f" ({brand_name})"
                        elif brand_name:
                            drug_text = f"  • {brand_name}"
                        else:
                            drug_text = "  • Unknown drug"
                        
                        if target:
                            drug_text += f" - Target: {target}"
                        if metadata.get('mechanism'):
                            drug_text += f" - Mechanism: {metadata.get('mechanism')}"
                        if metadata.get('drug_class'):
                            drug_text += f" - Class: {metadata.get('drug_class')}"
                        if metadata.get('phase'):
                            drug_text += f" - Phase: {metadata.get('phase')}"
                        
                        formatted_results.append(drug_text)
                    except Exception as e:
                        logger.debug(f"Error formatting drug result: {e}")
                        continue
        
        # Add concise entity summary at the end (limit to prevent huge responses)
        if all_targets or all_drugs or all_companies:
            formatted_results.append(f"\n📊 **Summary:**")
            # Deduplicate and limit display
            if all_targets:
                unique_targets = sorted(set(all_targets))
                if len(unique_targets) > 15:
                    formatted_results.append(f"   🎯 Targets ({len(unique_targets)}): {', '.join(unique_targets[:15])}... and {len(unique_targets)-15} more")
                else:
                    formatted_results.append(f"   🎯 Targets ({len(unique_targets)}): {', '.join(unique_targets)}")
            if all_drugs:
                unique_drugs = sorted(set(all_drugs))
                if len(unique_drugs) > 15:
                    formatted_results.append(f"   💊 Drugs ({len(unique_drugs)}): {', '.join(unique_drugs[:15])}... and {len(unique_drugs)-15} more")
                else:
                    formatted_results.append(f"   💊 Drugs ({len(unique_drugs)}): {', '.join(unique_drugs)}")
            if all_companies:
                unique_companies = sorted(set(all_companies))
                if len(unique_companies) > 15:
                    formatted_results.append(f"   🏢 Companies ({len(unique_companies)}): {', '.join(unique_companies[:15])}... and {len(unique_companies)-15} more")
                else:
                    formatted_results.append(f"   🏢 Companies ({len(unique_companies)}): {', '.join(unique_companies)}")
        
        return formatted_results
    
    def _aggregate_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Aggregate and deduplicate search results."""
        try:
            grouped_results = self._group_results_by_source_and_company(results)
            formatted_results = self._format_aggregated_results(grouped_results)
            return "\n".join(formatted_results) if formatted_results else "No results found"
        except Exception as e:
            logger.error(f"Error aggregating search results: {e}")
            return f"Error aggregating results: {str(e)}"
    
    def _determine_search_strategy(self, query: str) -> List[str]:
        """Determine search strategy based on query patterns."""
        query_lower = query.lower()
        
        # Define search strategies for different query types
        strategy_expansions = {
            'competitive': [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials", f"{query} mechanisms"],
            'comparison': [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials"],
            'timeline': [query, f"{query} clinical trials", f"{query} approvals", f"{query} partnerships"],
            'target_dev': [query, f"{query} drugs", f"{query} clinical trials", f"{query} phase", f"{query} indication"]
        }
        
        # Check for strategy keywords
        if any(word in query_lower for word in ['competitive', 'landscape', 'market', 'players']):
            return strategy_expansions['competitive']
        elif any(word in query_lower for word in ['compare', 'comparison', 'vs', 'versus']):
            return strategy_expansions['comparison']
        elif any(word in query_lower for word in ['timeline', 'development', 'evolution', 'history']):
            return strategy_expansions['timeline']
        elif any(word in query_lower for word in ['phase', 'development', 'indication', 'targeting']):
            return strategy_expansions['target_dev']
        
        # Default strategy
        return [query, f"{query} drugs", f"{query} companies", f"{query} clinical trials"]
    
    def _extract_target_from_question(self, question: str) -> Optional[str]:
        """Extract target name from question with normalization."""
        question_lower = question.lower()
        
        # Regex patterns for target extraction
        target_patterns = [
            r'\b([A-Z]{2,}-[0-9]{1,3}[A-Z]?)\b',  # PD-1, CD-19, PD-L1
            r'\b([A-Z]{2,}[0-9]{1,3}[A-Z]?)\b',   # HER2, EGFR, CD20, KRAS
            r'\b([A-Z]{3,}[0-9]?)\b',              # TROP2, BCL6, MTAP
            r'\b([A-Z]{2,}\s+[0-9]{1,3})\b',       # PD 1, CD 19 (space-separated)
        ]
        
        common_words = {'companies', 'company', 'target', 'targets', 'drugs', 'drug', 
                       'how', 'many', 'with', 'competitive', 'landscape', 'phase', 
                       'development', 'indication'}
        
        # Try pattern-based extraction first
        for pattern in target_patterns:
            matches = re.findall(pattern, question)
            if matches:
                filtered = [m for m in matches if isinstance(m, str) and m.lower() not in common_words]
                if filtered:
                    target = max(filtered, key=len)
                    return normalize_target_name(target)
        
        # Try capitalization-based extraction
        words = question.split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
                     'for', 'of', 'with', 'by', 'how', 'many', 'what', 'which', 
                     'who', 'where', 'when', 'why'}
        
        for word in words:
            if ((word.isupper() and len(word) >= 2) or 
                (word[0].isupper() and len(word) >= 3)):
                if word.lower() not in stop_words:
                    normalized = normalize_target_name(word)
                    if normalized:
                        return normalized
        
        return None
    
    def _determine_search_query(self, question: str) -> str:
        """Determine the best search query with target synonym expansion."""
        question_lower = question.lower()
        
        # Extract target and expand with synonyms
        target = self._extract_target_from_question(question)
        expanded_targets = set()
        if target:
            expanded_targets = expand_target_query(target)
        
        # If question asks about companies, extract target and enhance query
        if 'company' in question_lower or 'companies' in question_lower:
            if expanded_targets:
                # Create query with expanded targets
                target_queries = [f"{t} companies drugs" for t in expanded_targets]
                return " OR ".join(target_queries[:3])  # Limit to top 3 expansions
            return f"{question} companies"
        
        # If question asks about drugs, enhance query with target expansion
        if 'drug' in question_lower or 'drugs' in question_lower:
            if expanded_targets:
                target_queries = [f"{t} drugs" for t in expanded_targets]
                return " OR ".join(target_queries[:3])
            return f"{question} drugs"
        
        # If target found, expand query
        if expanded_targets:
            target_queries = [f"{t}" for t in expanded_targets]
            return " OR ".join(target_queries[:3])
        
        # Default: use question as-is
        return question
    
    def _group_results_by_company(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group search results by company, separated by source (Ground Truth first, then Database)."""
        grouped = self._group_results_by_source_and_company(results)
        
        companies_gt = {}
        companies_db = {}
        
        # Extract Ground Truth companies
        if "ground_truth" in grouped:
            for company, drug_results in grouped["ground_truth"].items():
                companies_gt[company] = []
                for result in drug_results:
                    metadata = result.get("metadata", {})
                    generic_name = metadata.get("generic_name", "").strip()
                    brand_name = metadata.get("brand_name", "").strip()
                    drug_name = generic_name if generic_name else brand_name
                    
                    companies_gt[company].append({
                        "drug": drug_name,
                        "brand": brand_name if generic_name else "",
                        "target": metadata.get("target", ""),
                        "indication": metadata.get("indication", ""),
                        "clinical_trials": metadata.get("clinical_trials", ""),
                        "relevance": result.get("similarity_score", 0),
                        "source": "ground_truth"
                    })
        
        # Extract Database companies
        if "database" in grouped:
            for company, drug_results in grouped["database"].items():
                companies_db[company] = []
                for result in drug_results:
                    metadata = result.get("metadata", {})
                    generic_name = metadata.get("generic_name", "").strip()
                    brand_name = metadata.get("brand_name", "").strip()
                    drug_name = generic_name if generic_name else brand_name
                    
                    companies_db[company].append({
                        "drug": drug_name,
                        "brand": brand_name if generic_name else "",
                        "target": metadata.get("target", ""),
                        "indication": metadata.get("indication", ""),
                        "clinical_trials": metadata.get("clinical_trials", ""),  # Clinical trials from drug relationships
                        "relevance": result.get("similarity_score", 0),
                        "source": "database"
                    })
        
        return {
            "ground_truth": companies_gt,
            "database": companies_db
        }
    
    def _format_fallback_answer(self, companies_data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Optional[str]:
        """Format the fallback search answer with comprehensive entity information (targets, drugs, companies)."""
        if not companies_data:
            return None
        
        companies_gt = companies_data.get("ground_truth", {})
        companies_db = companies_data.get("database", {})
        
        if not companies_gt and not companies_db:
            return None
        
        answer_parts = []
        total_companies = len(companies_gt) + len(companies_db)
        
        # Extract all entities for comprehensive summary
        all_targets = set()
        all_drugs = set()
        
        # Opening statement
        if total_companies == 1:
            answer_parts.append(f"I found **{total_companies} company** working on this:")
        else:
            answer_parts.append(f"I found **{total_companies} companies** working on this:")
        answer_parts.append("")
        
        # Format Ground Truth companies FIRST
        if companies_gt:
            answer_parts.append("🏆 **Ground Truth (Primary Data):**")
            answer_parts.append("")
            for company, drugs in companies_gt.items():
                if company:
                    # Collect all drugs for this company
                    drug_list = []
                    all_company_targets = set()
                    all_company_indications = []
                    all_company_trials = []
                    
                    for drug in drugs:
                        drug_name = drug.get('drug') or 'Unknown drug'
                        brand = drug.get('brand') or ''
                        target = drug.get('target') or 'Unknown target'
                        indication = drug.get('indication', '').strip()
                        clinical_trials = drug.get('clinical_trials', '').strip()
                        
                        # Track entities (normalize to avoid duplicates)
                        if drug_name:
                            all_drugs.add(drug_name)
                        if target and target != 'Unknown target':
                            # Handle comma-separated targets and normalize
                            targets = [t.strip() for t in target.split(',')]
                            for t in targets:
                                if t:
                                    normalized = normalize_target_name(t)
                                    if normalized:
                                        all_targets.add(normalized)
                                        all_company_targets.add(normalized)
                        
                        # Format drug name with brand if available
                        if brand:
                            drug_display = f"{drug_name} ({brand})"
                        else:
                            drug_display = drug_name
                        
                        drug_list.append(f"**{drug_display}**")
                        
                        if indication and indication not in all_company_indications:
                            all_company_indications.append(indication)
                        
                        if clinical_trials and clinical_trials not in all_company_trials:
                            all_company_trials.append(clinical_trials)
                    
                    # Format one row per company
                    company_targets = ", ".join(sorted(all_company_targets)) if all_company_targets else "Unknown target"
                    drugs_str = ", ".join(drug_list)
                    
                    parts = [f"🏢 **{company}** • {drugs_str} - Target: {company_targets}"]
                    
                    if all_company_indications:
                        parts.append(f"**Indication Approved**: {', '.join(all_company_indications)}")
                    
                    if all_company_trials:
                        parts.append(f"**Current Clinical Trials**: {', '.join(all_company_trials)}")
                    
                    answer_parts.append("  " + ", ".join(parts))
            answer_parts.append("")
        
        # Then format Database companies (supplementary)
        if companies_db:
            answer_parts.append("📊 **Internal Database (Supplementary Data):**")
            answer_parts.append("")
            for company, drugs in companies_db.items():
                if company:
                    # Collect all drugs for this company
                    drug_list = []
                    all_company_targets = set()
                    all_company_indications = []
                    all_company_trials = []
                    
                    for drug in drugs:
                        drug_name = drug.get('drug') or 'Unknown drug'
                        brand = drug.get('brand') or ''
                        target = drug.get('target') or 'Unknown target'
                        indication = drug.get('indication', '').strip()
                        clinical_trials = drug.get('clinical_trials', '').strip()
                        
                        # Track entities (normalize to avoid duplicates)
                        if drug_name:
                            all_drugs.add(drug_name)
                        if target and target != 'Unknown target':
                            # Handle comma-separated targets and normalize
                            targets = [t.strip() for t in target.split(',')]
                            for t in targets:
                                if t:
                                    normalized = normalize_target_name(t)
                                    if normalized:
                                        all_targets.add(normalized)
                                        all_company_targets.add(normalized)
                        
                        # Format drug name with brand if available
                        if brand:
                            drug_display = f"{drug_name} ({brand})"
                        else:
                            drug_display = drug_name
                        
                        drug_list.append(f"**{drug_display}**")
                        
                        if indication and indication not in all_company_indications:
                            all_company_indications.append(indication)
                        
                        if clinical_trials and clinical_trials not in all_company_trials:
                            all_company_trials.append(clinical_trials)
                    
                    # Format one row per company
                    company_targets = ", ".join(sorted(all_company_targets)) if all_company_targets else "Unknown target"
                    drugs_str = ", ".join(drug_list)
                    
                    parts = [f"🏢 **{company}** • {drugs_str} - Target: {company_targets}"]
                    
                    if all_company_indications:
                        parts.append(f"**Indication Approved**: {', '.join(all_company_indications)}")
                    
                    if all_company_trials:
                        parts.append(f"**Current Clinical Trials**: {', '.join(all_company_trials)}")
                    
                    answer_parts.append("  " + ", ".join(parts))
            answer_parts.append("")
        
        # Add concise entity summary (limit to prevent huge responses)
        if all_targets or all_drugs:
            answer_parts.append(f"\n📊 **Summary:**")
            # Deduplicate and limit display
            if all_targets:
                unique_targets = sorted(set(all_targets))
                if len(unique_targets) > 15:
                    answer_parts.append(f"   🎯 Targets ({len(unique_targets)}): {', '.join(unique_targets[:15])}... and {len(unique_targets)-15} more")
                else:
                    answer_parts.append(f"   🎯 Targets ({len(unique_targets)}): {', '.join(unique_targets)}")
            if all_drugs:
                unique_drugs = sorted(set(all_drugs))
                if len(unique_drugs) > 15:
                    answer_parts.append(f"   💊 Drugs ({len(unique_drugs)}): {', '.join(unique_drugs[:15])}... and {len(unique_drugs)-15} more")
                else:
                    answer_parts.append(f"   💊 Drugs ({len(unique_drugs)}): {', '.join(unique_drugs)}")
        
        # Add data source indicator
        if companies_gt and companies_db:
            answer_parts.append("\n📊 *Data source: Ground Truth (primary) + Internal Database (supplementary)*")
        elif companies_gt:
            answer_parts.append("\n📊 *Data source: Ground Truth*")
        else:
            answer_parts.append("\n📊 *Data source: Internal Database*")
        
        # Filter out None values and join
        answer_parts = [str(part) for part in answer_parts if part is not None]
        return "\n".join(answer_parts) if answer_parts else None
    
    def _fallback_search(self, question: str) -> Optional[str]:
        """Fallback search using direct semantic search when React agent fails."""
        try:
            logger.info(f"Running fallback search for: {question}")
            
            search_query = self._determine_search_query(question)
            results = self.vector_db.semantic_search(search_query, top_k=FALLBACK_TOP_K)
            
            if not results:
                return None
            
            # Group results by company (separated by Ground Truth and Database)
            companies_data = self._group_results_by_company(results)
            
            # Format answer (Ground Truth first, then Database)
            return self._format_fallback_answer(companies_data)
            
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return None
    
    def _is_no_data_response(self, answer: str) -> bool:
        """Check if the response indicates no data was found."""
        no_data_indicators = [
            "unable to find", "no information found", "no relevant information",
            "no data found", "cannot determine", "don't know",
            "no companies", "no drugs", "no targets"
        ]
        answer_lower = answer.lower()
        return any(indicator in answer_lower for indicator in no_data_indicators)
    
    def _create_react_agent(self) -> ReActAgent:
        """Create the React agent with tools and memory."""
        try:
            memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
            
            agent = ReActAgent.from_tools(
                tools=self.tools,
                llm=self.llm,
                memory=memory,
                verbose=True,
                max_iterations=MAX_ITERATIONS,
                system_prompt=SYSTEM_PROMPT,
            )
            
            return agent
            
        except Exception as e:
            logger.error(f"Error creating React agent: {e}")
            raise
    
    def generate_response(self, question: str) -> Dict[str, Any]:
        """Generate response using React framework with semantic search."""
        try:
            logger.info(f"Generating React response for: {question}")
            
            # Try React agent first
            try:
                response = self.agent.chat(question)
                answer = str(response)
                
                # Check if response indicates timeout or no data
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

    # do not touch this part as it is used for deployment
    def get_agent_status(self) -> Dict[str, Any]:
        """Get agent status and configuration."""
        return {
            "agent_type": "enhanced_react_framework",
            "llm_model": "llama3.1",
            "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "tools_count": len(self.tools),
            "tools": [tool.metadata.name for tool in self.tools],
            "memory_enabled": True,
            "max_iterations": MAX_ITERATIONS,
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
    # do not touch this part as it is used for deployment
