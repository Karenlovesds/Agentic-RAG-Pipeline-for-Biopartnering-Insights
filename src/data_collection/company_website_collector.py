"""Enhanced company website data collector for pipeline and development information."""

import asyncio
import re
from typing import List, Dict, Any, Optional
from loguru import logger
from crawl4ai import AsyncWebCrawler
from .base_collector import BaseCollector, CollectedData
from config.config import get_target_companies


class CompanyWebsiteCollector(BaseCollector):
    """Collector for company website data using crawl4AI."""
    
    def __init__(self):
        super().__init__("company_websites", "")
    
    async def collect_data(self, max_companies: int = 5) -> List[CollectedData]:
        """Collect comprehensive data from company websites using crawl4ai for deep website crawling."""
        collected_data = []
        
        # Get company list from CSV
        companies = get_target_companies()[:max_companies]
        
        logger.info(f"Starting comprehensive company website collection for {len(companies)} companies")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company in companies:
                try:
                    logger.info(f"Collecting comprehensive data for {company}...")
                    
                    # Get company website
                    website_url = self._get_company_website(company)
                    if not website_url:
                        logger.warning(f"No website found for {company}, skipping...")
                        continue
                    
                    # 1. Deep crawl the main website
                    main_website_data = await self._deep_crawl_website(crawler, company, website_url)
                    collected_data.extend(main_website_data)
                    
                    # 2. Collect data from specific page types
                    specific_pages_data = await self._collect_company_comprehensive_data(crawler, company, website_url)
                    collected_data.extend(specific_pages_data)
                    
                    # 3. Crawl sitemap for additional pages
                    sitemap_data = await self._crawl_sitemap_pages(crawler, company, website_url)
                    collected_data.extend(sitemap_data)
                    
                    # 4. Crawl news and press releases
                    news_data = await self._crawl_news_pages(crawler, company)
                    collected_data.extend(news_data)
                    
                    logger.info(f"✅ Completed comprehensive collection for {company}")
                        
                except Exception as e:
                    logger.error(f"Error collecting data for {company}: {e}")
                    continue
        
        return collected_data

    async def _deep_crawl_website(self, crawler, company: str, base_url: str) -> List[CollectedData]:
        """Deep crawl the main company website using crawl4ai's comprehensive crawling capabilities."""
        collected_data = []
        
        try:
            logger.info(f"🌐 Deep crawling main website for {company}: {base_url}")
            
            # Try LLM extraction first, fallback to regular crawling if not available
            extraction_strategy = None
            try:
                from crawl4ai.extraction_strategy import LLMExtractionStrategy
                from crawl4ai.extraction_strategy import LLMConfig
                
                # Define extraction strategy for biopharma content
                extraction_strategy = LLMExtractionStrategy(
                    llm_config=LLMConfig(provider="ollama/llama3.1", api_token=""),  # Use local Ollama for extraction
                    instruction="""
                    Extract comprehensive information about this biopharmaceutical company including:
                    1. Company overview and mission
                    2. Drug development pipeline and programs
                    3. Clinical trials and research activities
                    4. Approved products and therapeutics
                    5. Oncology and cancer-focused programs
                    6. Partnerships and collaborations
                    7. Recent news and developments
                    8. Technology platforms and capabilities
                    9. Regulatory milestones and approvals
                    10. Financial and business information
                    
                    CRITICAL: Extract ALL drug names mentioned anywhere on the website, including:
                    - Generic names (e.g., pembrolizumab, trastuzumab)
                    - Brand names (e.g., Keytruda, Herceptin)
                    - Internal codes (e.g., RG1234, MK-1234)
                    - Development candidates
                    - Pipeline drugs
                    - Approved drugs
                    - Partnership drugs
                    - Clinical trial drugs
                    - Technology platform drugs
                    
                    Focus on extracting drug names, clinical trial information, indications, 
                    partnerships, and any biopartnering opportunities.
                    """,
                    schema={
                        "type": "object",
                        "properties": {
                            "company_overview": {"type": "string"},
                            "drug_pipeline": {"type": "array", "items": {"type": "string"}},
                            "clinical_trials": {"type": "array", "items": {"type": "string"}},
                            "approved_products": {"type": "array", "items": {"type": "string"}},
                            "oncology_programs": {"type": "array", "items": {"type": "string"}},
                            "partnerships": {"type": "array", "items": {"type": "string"}},
                            "recent_news": {"type": "array", "items": {"type": "string"}},
                            "technology_platforms": {"type": "array", "items": {"type": "string"}},
                            "regulatory_milestones": {"type": "array", "items": {"type": "string"}},
                            "biopartnering_opportunities": {"type": "array", "items": {"type": "string"}},
                            "all_drug_names": {"type": "array", "items": {"type": "string"}, "description": "ALL drug names found anywhere on the website"},
                            "generic_names": {"type": "array", "items": {"type": "string"}, "description": "Generic drug names (e.g., pembrolizumab)"},
                            "brand_names": {"type": "array", "items": {"type": "string"}, "description": "Brand drug names (e.g., Keytruda)"},
                            "internal_codes": {"type": "array", "items": {"type": "string"}, "description": "Internal company codes (e.g., RG1234, MK-1234)"},
                            "development_candidates": {"type": "array", "items": {"type": "string"}, "description": "Drugs in development"},
                            "partnership_drugs": {"type": "array", "items": {"type": "string"}, "description": "Drugs mentioned in partnerships"},
                            "clinical_trial_drugs": {"type": "array", "items": {"type": "string"}, "description": "Drugs mentioned in clinical trials"}
                        }
                    }
                )
                logger.info(f"Using LLM extraction for {company}")
            except ImportError:
                logger.warning(f"LLM extraction not available, using regular crawling for {company}")
                extraction_strategy = "NoExtractionStrategy"
            
            # Crawl the main website with comprehensive extraction
            result = await crawler.arun(
                url=base_url,
                word_count_threshold=50,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                max_pages=10,  # Crawl up to 10 pages from the main site
                max_depth=2,   # Go 2 levels deep from the main page
                delay_between_requests=1.0  # Be respectful to the server
            )
            
            if result.success:
                if result.extracted_content and isinstance(result.extracted_content, dict):
                    # Process the extracted structured data from LLM
                    extracted_data = result.extracted_content
                    
                    # Create comprehensive content from extracted data
                    content_parts = [
                        f"Company: {company}",
                        f"Source: Main Website Deep Crawl (LLM Extracted)",
                        f"URL: {base_url}",
                        f"Collection Date: {asyncio.get_event_loop().time()}",
                        "",
                        "=== COMPANY OVERVIEW ===",
                        extracted_data.get("company_overview", "No overview available"),
                        "",
                        "=== DRUG PIPELINE ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("drug_pipeline", [])]),
                        "",
                        "=== CLINICAL TRIALS ===",
                        "\n".join([f"- {trial}" for trial in extracted_data.get("clinical_trials", [])]),
                        "",
                        "=== APPROVED PRODUCTS ===",
                        "\n".join([f"- {product}" for product in extracted_data.get("approved_products", [])]),
                        "",
                        "=== ONCOLOGY PROGRAMS ===",
                        "\n".join([f"- {program}" for program in extracted_data.get("oncology_programs", [])]),
                        "",
                        "=== PARTNERSHIPS ===",
                        "\n".join([f"- {partnership}" for partnership in extracted_data.get("partnerships", [])]),
                        "",
                        "=== RECENT NEWS ===",
                        "\n".join([f"- {news}" for news in extracted_data.get("recent_news", [])]),
                        "",
                        "=== TECHNOLOGY PLATFORMS ===",
                        "\n".join([f"- {platform}" for platform in extracted_data.get("technology_platforms", [])]),
                        "",
                        "=== REGULATORY MILESTONES ===",
                        "\n".join([f"- {milestone}" for milestone in extracted_data.get("regulatory_milestones", [])]),
                        "",
                        "=== BIOPARTNERING OPPORTUNITIES ===",
                        "\n".join([f"- {opportunity}" for opportunity in extracted_data.get("biopartnering_opportunities", [])]),
                        "",
                        "=== ALL DRUG NAMES FOUND ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("all_drug_names", [])]),
                        "",
                        "=== GENERIC NAMES ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("generic_names", [])]),
                        "",
                        "=== BRAND NAMES ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("brand_names", [])]),
                        "",
                        "=== INTERNAL CODES ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("internal_codes", [])]),
                        "",
                        "=== DEVELOPMENT CANDIDATES ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("development_candidates", [])]),
                        "",
                        "=== PARTNERSHIP DRUGS ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("partnership_drugs", [])]),
                        "",
                        "=== CLINICAL TRIAL DRUGS ===",
                        "\n".join([f"- {drug}" for drug in extracted_data.get("clinical_trial_drugs", [])])
                    ]
                    
                    content = "\n".join(content_parts)
                    
                    # Extract additional drug names from LLM data
                    llm_drugs = self._extract_drugs_from_llm_data(extracted_data)
                    if llm_drugs:
                        logger.info(f"✅ LLM extracted {len(llm_drugs)} additional drug names for {company}")
                        # Add to metadata for tracking
                        data.metadata["llm_extracted_drugs"] = llm_drugs
                        data.metadata["total_drugs_found"] = len(llm_drugs)
                    
                elif result.cleaned_html:
                    # Fallback: Use regular HTML extraction
                    content = self._extract_comprehensive_content_from_html(result.cleaned_html, company, base_url)
                else:
                    logger.warning(f"No content extracted from {company} website")
                    return collected_data
                
                if content and len(content) > 100:  # Only save if we got meaningful content
                    data = CollectedData(
                        title=f"{company} - Comprehensive Website Data",
                        content=content,
                        source_url=base_url,
                        source_type="company_website_deep_crawl",
                        metadata={
                            "company": company,
                            "crawl_type": "deep_website_crawl",
                            "pages_crawled": result.pages_crawled if hasattr(result, 'pages_crawled') else 1,
                            "content_length": len(content),
                            "extraction_method": "llm_structured_extraction"
                        }
                    )
                    collected_data.append(data)
                    logger.info(f"✅ Deep crawled {company} website: {len(content)} characters")
                else:
                    logger.warning(f"⚠️ Insufficient content extracted from {company} website")
            
            else:
                logger.warning(f"⚠️ Deep crawl failed for {company}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                
        except Exception as e:
            logger.error(f"❌ Error deep crawling {company}: {e}")
        
        return collected_data

    async def _crawl_sitemap_pages(self, crawler, company: str, base_url: str) -> List[CollectedData]:
        """Crawl additional pages found in sitemap for comprehensive coverage."""
        collected_data = []
        
        try:
            logger.info(f"🗺️ Crawling sitemap pages for {company}")
            
            # Find sitemap and extract relevant URLs
            sitemap_urls = await self._find_sitemap_urls(base_url)
            
            if not sitemap_urls:
                logger.info(f"No sitemap URLs found for {company}")
                return collected_data
            
            # Filter URLs for biopharma-relevant content
            relevant_urls = self._filter_biopharma_urls(sitemap_urls)
            logger.info(f"Found {len(relevant_urls)} relevant URLs for {company}")
            
            # Crawl each relevant URL
            for url in relevant_urls[:15]:  # Limit to 15 additional pages
                try:
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=30,
                        extraction_strategy="NoExtractionStrategy",
                        bypass_cache=True
                    )
                    
                    if result.success and result.cleaned_html:
                        content = self._extract_general_content(result.cleaned_html, company, ["biopharma", "drug", "clinical", "pipeline"])
                        
                        if content and len(content) > 200:
                            data = CollectedData(
                                title=f"{company} - {self._extract_page_title(result.cleaned_html)}",
                                content=content,
                                source_url=url,
                                source_type="company_website_sitemap",
                                metadata={
                                    "company": company,
                                    "crawl_type": "sitemap_crawl",
                                    "content_length": len(content),
                                    "source_page": url
                                }
                            )
                            collected_data.append(data)
                            logger.info(f"✅ Crawled sitemap page: {url}")
                    
                    # Small delay between requests
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error crawling sitemap page {url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error crawling sitemap for {company}: {e}")
        
        return collected_data

    async def _find_sitemap_urls(self, base_url: str) -> List[str]:
        """Find and extract URLs from sitemap."""
        urls = []
        
        try:
            # Common sitemap locations
            sitemap_locations = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/robots.txt"
            ]
            
            async with AsyncWebCrawler(verbose=False) as crawler:
                for sitemap_url in sitemap_locations:
                    try:
                        result = await crawler.arun(url=sitemap_url, bypass_cache=True)
                        if result.success and result.cleaned_html:
                            extracted_urls = self._extract_urls_from_sitemap(result.cleaned_html)
                            urls.extend(extracted_urls)
                    except:
                        continue
                        
        except Exception as e:
            logger.warning(f"Error finding sitemap URLs: {e}")
        
        return list(set(urls))  # Remove duplicates

    def _filter_biopharma_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs for biopharma-relevant content."""
        biopharma_keywords = [
            'pipeline', 'development', 'research', 'clinical', 'trial', 'study',
            'product', 'therapeutic', 'medicine', 'drug', 'oncology', 'cancer',
            'immunotherapy', 'biomarker', 'partnership', 'collaboration',
            'news', 'press', 'milestone', 'approval', 'fda', 'regulatory',
            'technology', 'platform', 'capability', 'about', 'company'
        ]
        
        filtered_urls = []
        for url in urls:
            url_lower = url.lower()
            if any(keyword in url_lower for keyword in biopharma_keywords):
                filtered_urls.append(url)
        
        return filtered_urls

    def _extract_page_title(self, html_content: str) -> str:
        """Extract page title from HTML content."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                return title_tag.get_text().strip()
            return "Untitled Page"
        except:
            return "Untitled Page"

    def _extract_comprehensive_content_from_html(self, html_content: str, company: str, base_url: str) -> str:
        """Extract comprehensive content from HTML when LLM extraction is not available."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'form', 'aside']):
                element.decompose()
            
            # Extract text content
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Extract specific sections
            content_parts = [
                f"Company: {company}",
                f"Source: Main Website Deep Crawl (HTML Extracted)",
                f"URL: {base_url}",
                f"Collection Date: {asyncio.get_event_loop().time()}",
                "",
                "=== WEBSITE CONTENT ===",
                text_content[:5000] + "..." if len(text_content) > 5000 else text_content,
                "",
                "=== EXTRACTED DRUG NAMES ===",
                "\n".join([f"- {drug}" for drug in self._extract_drug_names_from_html(html_content, company)]),
                "",
                "=== EXTRACTED NCT CODES ===",
                "\n".join([f"- {nct}" for nct in self._extract_nct_codes_from_text(text_content)])
            ]
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error extracting content from HTML: {e}")
            return f"Company: {company}\nSource: {base_url}\nError: Could not extract content from HTML"

    def _extract_drugs_from_llm_data(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Extract and consolidate all drug names from LLM-extracted data."""
        all_drugs = set()
        
        # Extract from all drug-related fields
        drug_fields = [
            "all_drug_names", "generic_names", "brand_names", "internal_codes",
            "development_candidates", "partnership_drugs", "clinical_trial_drugs",
            "drug_pipeline", "approved_products"
        ]
        
        for field in drug_fields:
            drugs = extracted_data.get(field, [])
            if isinstance(drugs, list):
                for drug in drugs:
                    if isinstance(drug, str) and drug.strip():
                        cleaned_drug = self._clean_drug_name(drug.strip())
                        if cleaned_drug and self._validate_drug_name(cleaned_drug):
                            all_drugs.add(cleaned_drug)
        
        # Also extract from text fields that might contain drug names
        text_fields = [
            "company_overview", "clinical_trials", "oncology_programs",
            "partnerships", "recent_news", "technology_platforms",
            "regulatory_milestones", "biopartnering_opportunities"
        ]
        
        for field in text_fields:
            text = extracted_data.get(field, "")
            if isinstance(text, str) and text.strip():
                # Extract drug names from text using existing patterns
                text_drugs = self._extract_drug_names_from_text(text)
                for drug in text_drugs:
                    cleaned_drug = self._clean_drug_name(drug)
                    if cleaned_drug and self._validate_drug_name(cleaned_drug):
                        all_drugs.add(cleaned_drug)
        
        return list(all_drugs)

    def _extract_drug_names_from_text(self, text: str) -> List[str]:
        """Extract drug names from plain text using regex patterns."""
        drug_names = set()
        
        # Use the same patterns as HTML extraction but on plain text
        drug_patterns = [
            # Monoclonal antibodies
            r'\b[A-Z][a-z]+mab\b',
            r'\b[A-Z][a-z]+zumab\b',
            r'\b[A-Z][a-z]+ximab\b',
            r'\b[A-Z][a-z]+tumab\b',
            r'\b[A-Z][a-z]+lamab\b',
            
            # Kinase inhibitors
            r'\b[A-Z][a-z]+nib\b',
            r'\b[A-Z][a-z]+tinib\b',
            r'\b[A-Z][a-z]+inib\b',
            r'\b[A-Z][a-z]+sib\b',
            r'\b[A-Z][a-z]+lisib\b',
            r'\b[A-Z][a-z]+ciclib\b',
            r'\b[A-Z][a-z]+fetinib\b',
            
            # Other patterns
            r'\b[A-Z][a-z]+cept\b',
            r'\b[A-Z][a-z]+mig\b',
            
            # Company codes
            r'\bRG\d{3,5}\b', r'\bGDC-\d{3,5}\b', r'\bRGT-\d{3,5}\b',
            r'\bABBV-\d{2,4}\b', r'\bDS-\d{3,5}\b', r'\bAMG ?\d{2,4}\b',
            r'\bBAY ?\d{3,7}\b', r'\bJNJ-\d{3,5}\b', r'\bREGN\d{3,5}\b',
            r'\bMK-\d{3,5}[A-Z]?\b', r'\bGS-\d{3,5}\b', r'\bAAA\d{3}\b',
            
            # ADC patterns
            r'\b[A-Z][a-z]+\s+vedotin\b',
            r'\b[A-Z][a-z]+\s+deruxtecan\b',
            r'\b[A-Z][a-z]+\s+emtansine\b',
            
            # CAR-T patterns
            r'\b[A-Z][a-z]+\s+cabtagene\s+autoleucel\b',
            r'\b[A-Z][a-z]+\s+autoleucel\b',
            
            # mRNA patterns
            r'\bmRNA-\d{3,5}\b',
        ]
        
        for pattern in drug_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                drug_names.add(match)
        
        return list(drug_names)

    async def collect_pipeline_drugs(self, max_companies: int = 10) -> List[str]:
        """Collect drug names specifically from company pipeline pages."""
        drug_names = set()
        
        # Get company list from CSV
        companies = get_target_companies()[:max_companies]
        
        logger.info(f"Starting pipeline drug collection for {len(companies)} companies")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company in companies:
                try:
                    logger.info(f"Collecting pipeline drugs for {company}...")
                    
                    # Get company pipeline URL
                    pipeline_url = self._get_company_pipeline_url(company)
                    if not pipeline_url:
                        logger.warning(f"No pipeline URL found for {company}, skipping...")
                        continue
                    
                    # Find and scrape pipeline pages
                    drug_nct_mapping = await self._extract_pipeline_drugs(crawler, company, pipeline_url)
                    pipeline_drugs = list(drug_nct_mapping.keys())
                    drug_names.update(pipeline_drugs)
                    
                    logger.info(f"✅ Found {len(pipeline_drugs)} drugs in {company} pipeline")
                        
                except Exception as e:
                    logger.error(f"Error collecting pipeline drugs for {company}: {e}")
                    continue
            
            unique_drugs = list(drug_names)
            logger.info(f"🎉 Total unique pipeline drugs found: {len(unique_drugs)}")
            return unique_drugs

    async def collect_pipeline_drugs_with_companies(self, max_companies: int = 10) -> Dict[str, List[str]]:
        """Collect drug names with company associations from company pipeline pages."""
        company_drug_mapping = {}
        
        # Get company list from CSV
        companies = get_target_companies()[:max_companies]
        
        logger.info(f"Starting pipeline drug collection with company associations for {len(companies)} companies")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company in companies:
                try:
                    logger.info(f"Collecting pipeline drugs for {company}...")
                    
                    # Get company pipeline URL
                    pipeline_url = self._get_company_pipeline_url(company)
                    if not pipeline_url:
                        logger.warning(f"No pipeline URL found for {company}, skipping...")
                        continue
                    
                    # Find and scrape pipeline pages
                    drug_nct_mapping = await self._extract_pipeline_drugs(crawler, company, pipeline_url)
                    pipeline_drugs = list(drug_nct_mapping.keys())
                    
                    if pipeline_drugs:
                        company_drug_mapping[company] = pipeline_drugs
                        logger.info(f"✅ Found {len(pipeline_drugs)} drugs in {company} pipeline")
                    else:
                        logger.info(f"ℹ️ No drugs found in {company} pipeline")
                        
                except Exception as e:
                    logger.error(f"Error collecting pipeline drugs for {company}: {e}")
                    continue
            
            total_drugs = sum(len(drugs) for drugs in company_drug_mapping.values())
            logger.info(f"🎉 Total pipeline drugs found: {total_drugs} across {len(company_drug_mapping)} companies")
            return company_drug_mapping

    async def _extract_pipeline_drugs(self, crawler, company: str, base_url: str) -> Dict[str, List[str]]:
        """Extract drug names and associated NCT codes from company pipeline pages."""
        drug_names = set()
        all_text_content = ""
        
        # Common pipeline page patterns
        pipeline_patterns = [
                f"{base_url.rstrip('/')}/pipeline",
                f"{base_url.rstrip('/')}/research",
                f"{base_url.rstrip('/')}/development",
                f"{base_url.rstrip('/')}/programs",
                f"{base_url.rstrip('/')}/therapeutics",
                f"{base_url.rstrip('/')}/medicines",
                f"{base_url.rstrip('/')}/products",
                f"{base_url.rstrip('/')}/oncology",
                f"{base_url.rstrip('/')}/cancer",
                f"{base_url.rstrip('/')}/immunotherapy",
                f"{base_url.rstrip('/')}/pipeline/oncology",
                f"{base_url.rstrip('/')}/pipeline/immuno-oncology",
                f"{base_url.rstrip('/')}/pipeline/early-stage",
                f"{base_url.rstrip('/')}/pipeline/late-stage"
            ]
        
        for pattern in pipeline_patterns:
            try:
                result = await crawler.arun(
                    url=pattern,
                    word_count_threshold=20,
                    extraction_strategy="NoExtractionStrategy",
                    bypass_cache=True
                )
                
                if result.success and result.cleaned_html:
                    # Extract drug names from this page
                    page_drugs = self._extract_drug_names_from_html(result.cleaned_html, company)
                    drug_names.update(page_drugs)
                    
                    # Also collect text content for NCT code association
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
                    page_text = soup.get_text(separator=' ', strip=True)
                    all_text_content += " " + page_text
                    
                    logger.info(f"Found {len(page_drugs)} drugs on {pattern}")
                
            except Exception as e:
                logger.warning(f"Error scraping {pattern}: {e}")
                continue
        
        # Associate NCT codes with drugs
        drug_list = list(drug_names)
        drug_nct_mapping = self._associate_nct_codes_with_drugs(all_text_content, drug_list)
        
        return drug_nct_mapping

    def _extract_drug_names_from_html(self, html_content: str, company: str) -> List[str]:
        """Extract drug names from HTML content using comprehensive patterns based on ground truth analysis."""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'form']):
            element.decompose()
        
        text_content = soup.get_text(separator=' ', strip=True)
        text_lower = text_content.lower()
        
        drug_names = set()
        
        # Company-style internal codes
        company_code_patterns = {
            "Roche/Genentech": [
                r"\bRG\d{3,5}\b", r"\bGDC-\d{3,5}\b", r"\bRGT-\d{3,5}\b", r"\bRO[A-Z]*\d*\b"
            ],
            "AbbVie": [
                r"\bABBV-\d{2,4}\b", r"\bABBV-CLS-\d{2,4}\b"
            ],
            "Daiichi Sankyo": [
                r"\bDS-\d{3,5}\b"
            ],
            "Amgen": [
                r"\bAMG ?\d{2,4}\b", r"\bABP ?\d{2,4}\b", r"\bXALURITAMIG\b"
            ],
            "Bayer/Vividion": [
                r"\bBAY ?\d{3,7}\b", r"\bVVD-\d{3,6}\b"
            ],
            "Janssen/J&J": [
                r"\bJNJ-\d{3,5}\b", r"\bTAR-\d{3}\b"
            ],
            "Regeneron": [
                r"\bREGN\d{3,5}\b"
            ],
            "Merck (MK-)": [
                r"\bMK-\d{3,5}[A-Z]?\b"
            ],
            "Gilead (GS-)": [
                r"\bGS-\d{3,5}\b"
            ],
            "Novartis/AAA/NVL": [
                r"\bAAA\d{3}\b", r"\bNVL-\d{3}\b", r"\bS\d{5}\b"  # S95031/S95032 style
            ],
        }
        
        # Modality / suffix patterns (generic names)
        modality_suffix_patterns = {
            "ADC_deruxtecan": [r"\b[a-z][a-z\-]*deruxtecan(?:-[a-z0-9]+)?\b"],
            "ADC_vedotin":    [r"\b[a-z][a-z\-]*vedotin(?:-[a-z0-9]+)?\b", r"\bpevedotin\b"],
            "MonoclonalAb":   [r"\b[a-z][a-z\-]*mab(?:-[a-z0-9]+)?\b"],  # -mab, -zumab, -tumab, -lamab, etc.
            "TCE_Bispecific": [r"\b[a-z][a-z\-]*mig\b"],                  # e.g., nezastomig, vonsetamig
            "CAR_T":          [r"\b[a-z][a-z\-]*cabtagene autoleucel\b"],
            "CellGene":       [r"\bautogene [a-z][a-z\-]*\b"],
            "mRNA":           [r"\bmRNA-\d{3,5}\b"],
            "SmallMol":       [r"\b[a-z][a-z\-]*nib\b", r"\b[a-z][a-z\-]*sib\b", r"\b[a-z][a-z\-]*tinib\b", r"\b[a-z][a-z\-]*lisib\b", r"\b[a-z][a-z\-]*ciclib\b", r"\b[a-z][a-z\-]*fetinib\b"],
        }
        
        # Specific "known brand/generic" catch-alls (case-insensitive)
        known_free_text = [
            # Common Roche/Genentech marketed
            "Atezolizumab","Giredestrant","Codrituzumab","Inavolisib","Polatuzumab vedotin piiq",
            "Mosunetuzumab","Trastuzumab emtansine","Cevostamab","Clesitamig","Divarasib",
            "Glofitamab","Mosperafenib","Alectinib","Autogene cevumeran","Cobimetinib",
            "Entrectinib","Pertuzumab","Tiragolumab","Trastuzumab","Vemurafenib","Venclexta",
            "Vismodegib","Bevacizumab","Obinutuzumab","Rituximab",
            # AbbVie/Gilead/etc.
            "Teliso-V","Epcoritamab","Mirvetuximab soravtansine",
            # Daiichi ADCs
            "Trastuzumab deruxtecan","Datopotamab deruxtecan-dlnk","Patrituzumab deruxtecan","Ifinatamab deruxtecan","Raludotatug deruxtecan",
            # AZ/JNJ/MSD/etc. (selected)
            "Durvalumab","Osimertinib","Olaparib","Tremelimumab","Gefitinib","Moxetumomab pasudotox",
            "Bemarituzumab","Blinatumomab","Tarlatamab-dlle","Sotorasib",
            "Carfilzomib","Enfortumab vedotin","Gilteritinib","Zolbetuximab","Fezolinetant",
            "Darolutamide","Sevabertinib",
            # Merck MK names
            "Pembrolizumab","Belzutifan","Zilovertamab vedotin","Bomedemstat",
            # FDA-approved brand names (alphabetical)
            "Alecensa","Akeega","Avastin","Blincyto","Carvykti","Columvi","Cotellic",
            "Darzalex","Datroway","Elahere","Enhertu","Epkinly","Erivedge","Erleada",
            "Gazyva","Herceptin","Imbruvica","Imdelltra","Imfinzi","Imjudo","Kadcyla",
            "Keytruda","Kyprolis","Libitayo","Lumakras","Lumoxiti","Lunsumio","Lutathera",
            "Lynparza","Nubeqa","Padcev","Perjeta","Phesgo","Pluvicto","Polivy","Rituxan",
            "Rozlytrek","Rybrevant","Tagrisso","Talvey","Tecentriq","Tecvayli","Trodelvy",
            "Vijoyce","Welireg","Zelboraf"
        ]
        
        # Build comprehensive drug patterns
        drug_patterns = []
        
        # 1. Add company-specific internal codes
        for company_name, patterns in company_code_patterns.items():
            if any(comp in company.lower() for comp in company_name.lower().split('/')):
                drug_patterns.extend(patterns)
        
        # 2. Add modality/suffix patterns
        for modality, patterns in modality_suffix_patterns.items():
            drug_patterns.extend(patterns)
        
        # 3. Add known free text patterns (case-insensitive)
        for drug in known_free_text:
            drug_patterns.append(r'\b' + re.escape(drug) + r'\b')
        
        # 4. Add generic patterns for common drug suffixes
        drug_patterns.extend([
            # Monoclonal antibodies (improved patterns)
            r'\b[A-Z][a-z]+mab\b',  # pembrolizumab, nivolumab, etc.
            r'\b[A-Z][a-z]+zumab\b',  # bevacizumab, trastuzumab, etc.
            r'\b[A-Z][a-z]+ximab\b',  # rituximab, infliximab, etc.
            r'\b[A-Z][a-z]+tumab\b',  # trastuzumab, etc.
            r'\b[A-Z][a-z]+lamab\b',  # alemtuzumab, etc.
            
            # Kinase inhibitors
            r'\b[A-Z][a-z]+nib\b',  # sorafenib, erlotinib, etc.
            r'\b[A-Z][a-z]+tinib\b',  # sunitinib, lapatinib, etc.
            r'\b[A-Z][a-z]+inib\b',  # crizotinib, ceritinib, etc.
            r'\b[A-Z][a-z]+sib\b',  # osimertinib, etc.
            r'\b[A-Z][a-z]+lisib\b',  # alpelisib, etc.
            r'\b[A-Z][a-z]+ciclib\b',  # palbociclib, etc.
            r'\b[A-Z][a-z]+fetinib\b',  # gefitinib, etc.
            
            # Other drug patterns
            r'\b[A-Z][a-z]+cept\b',  # etanercept, abatacept, etc.
            r'\b[A-Z][a-z]+mig\b',  # bispecific TCEs
            
            # Brand name patterns (capitalized, often ending in specific suffixes)
            r'\b[A-Z][a-z]+(?:sa|ta|na|ma|ga|ka|la|ra|va|ya|za)\b',  # common brand name endings
            r'\b[A-Z][a-z]{5,12}\b',  # general capitalized brand names (5-12 chars)
            
            # Complex drug names with spaces and special characters
            r'\b[A-Z][a-z]+\s+[a-z]+\s+[a-z]+\b',  # multi-word drug names
            r'\b[A-Z][a-z]+\s+[a-z]+\b',  # two-word drug names
            
            # Generic patterns for capitalized drug names
            r'\b[A-Z][a-z]{4,}(?:mab|nib|tinib|cept|zumab|ximab|tumab|lamab|sib|lisib|ciclib|fetinib|mig)\b',
            
            # ADC patterns
            r'\b[A-Z][a-z]+\s+vedotin\b',  # polatuzumab vedotin, etc.
            r'\b[A-Z][a-z]+\s+deruxtecan\b',  # trastuzumab deruxtecan, etc.
            r'\b[A-Z][a-z]+\s+emtansine\b',  # trastuzumab emtansine, etc.
            
            # CAR-T patterns
            r'\b[A-Z][a-z]+\s+cabtagene\s+autoleucel\b',  # tisagenlecleucel, etc.
            r'\b[A-Z][a-z]+\s+autoleucel\b',  # CAR-T therapies
            
            # Cell and gene therapy patterns
            r'\bautogene\s+[a-z][a-z\-]*\b',  # autogene cevumeran, etc.
            
            # mRNA patterns
            r'\bmRNA-\d{3,5}\b',  # mRNA-1234, etc.
        ])
        
        for pattern in drug_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Clean and validate drug name
                cleaned_name = self._clean_drug_name(match)
                if cleaned_name and self._validate_drug_name(cleaned_name):
                    drug_names.add(cleaned_name)
        
        # Also look for drug names in specific HTML elements
        drug_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'span', 'div'], 
                                    class_=re.compile(r'(?:drug|product|therapeutic|candidate|program)', re.I))
        
        for element in drug_elements:
            element_text = element.get_text(strip=True)
            if len(element_text) > 3 and len(element_text) < 50:
                # Check if it looks like a drug name
                if any(suffix in element_text.lower() for suffix in ['mab', 'nib', 'tinib', 'cept', 'zumab']):
                    cleaned_name = self._clean_drug_name(element_text)
                    if cleaned_name and self._validate_drug_name(cleaned_name):
                        drug_names.add(cleaned_name)
        
        logger.info(f"Extracted {len(drug_names)} potential drug names from {company}")
        return list(drug_names)
    
    def _extract_nct_codes_from_text(self, text: str) -> List[str]:
        """Extract NCT codes (8 digits) from text."""
        nct_pattern = r'\bNCT\d{8}\b'
        nct_codes = re.findall(nct_pattern, text)
        return list(set(nct_codes))  # Remove duplicates
    
    def _associate_nct_codes_with_drugs(self, text: str, drug_names: List[str]) -> Dict[str, List[str]]:
        """Associate NCT codes with nearby drug names in the text."""
        drug_nct_mapping = {drug: [] for drug in drug_names}
        
        # Extract all NCT codes
        nct_codes = self._extract_nct_codes_from_text(text)
        
        # For each drug, find nearby NCT codes (within 200 characters)
        for drug in drug_names:
            drug_positions = []
            for match in re.finditer(re.escape(drug), text, re.IGNORECASE):
                drug_positions.append(match.start())
            
            for drug_pos in drug_positions:
                # Look for NCT codes within 200 characters before or after the drug
                context_start = max(0, drug_pos - 200)
                context_end = min(len(text), drug_pos + len(drug) + 200)
                context = text[context_start:context_end]
                
                # Find NCT codes in this context
                context_nct_codes = self._extract_nct_codes_from_text(context)
                drug_nct_mapping[drug].extend(context_nct_codes)
        
        # Remove duplicates and empty lists
        for drug in drug_nct_mapping:
            drug_nct_mapping[drug] = list(set(drug_nct_mapping[drug]))
        
        return drug_nct_mapping

    def _clean_drug_name(self, name: str) -> str:
        """Clean and normalize drug name."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^(the|a|an)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+(injection|tablet|capsule|solution|oral|iv|im)\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)  # Remove parenthetical info
        name = re.sub(r'\s*\[[^\]]*\]\s*$', '', name)  # Remove bracketed info
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        return name

    def _validate_drug_name(self, name: str) -> bool:
        """Validate if a name is likely a drug name using intelligent pattern matching."""
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Check if it contains only letters, numbers, and common drug characters
        if not re.match(r'^[A-Za-z0-9\-\s\/\(\)]+$', name):
            return False
        
        # 1. Filter out clinical trial IDs (NCT followed by 8 digits)
        if re.match(r'^NCT\d{8}$', name):
            return False
        
        # 2. Filter out study codes (pattern: letters followed by numbers) - but allow company codes
        if re.match(r'^[A-Z]{2,}\d+$', name) and not any(pattern in name.upper() for pattern in ['RG', 'GDC', 'RGT', 'ABBV', 'DS', 'AMG', 'ABP', 'BAY', 'VVD', 'JNJ', 'TAR', 'REGN', 'MK', 'GS', 'AAA', 'NVL']):
            return False
        
        # 3. Filter out generic terms that are not drug names
        generic_terms = [
            'study', 'phase', 'trial', 'code', 'compound', 'molecule', 'agent',
            'treatment', 'therapy', 'drug', 'medication', 'product', 'candidate', 'program',
            'development', 'research', 'clinical', 'investigational', 'pipeline',
            'oncology', 'cancer', 'tumor', 'therapeutic', 'biomarker', 'target',
            'injection', 'tablet', 'capsule', 'solution', 'oral', 'iv', 'im'
        ]
        
        if name.lower() in generic_terms:
            return False
        
        # 4. Filter out very short or very long names that are unlikely to be drugs
        if len(name) < 4 and not any(suffix in name.lower() for suffix in ['mab', 'nib', 'tinib', 'cept', 'zumab', 'ximab', 'tumab', 'lamab', 'sib', 'lisib', 'ciclib', 'fetinib', 'mig']):
            return False
        
        # 5. Allow company internal codes (RG, GDC, ABBV, etc.)
        company_code_patterns = [
            r'^RG\d{3,5}$', r'^GDC-\d{3,5}$', r'^RGT-\d{3,5}$', r'^RO[A-Z]*\d*$',
            r'^ABBV-\d{2,4}$', r'^ABBV-CLS-\d{2,4}$', r'^DS-\d{3,5}$',
            r'^AMG ?\d{2,4}$', r'^ABP ?\d{2,4}$', r'^XALURITAMIG$',
            r'^BAY ?\d{3,7}$', r'^VVD-\d{3,6}$', r'^JNJ-\d{3,5}$', r'^TAR-\d{3}$',
            r'^REGN\d{3,5}$', r'^MK-\d{3,5}[A-Z]?$', r'^GS-\d{3,5}$',
            r'^AAA\d{3}$', r'^NVL-\d{3}$', r'^S\d{5}$'
        ]
        
        if any(re.match(pattern, name, re.IGNORECASE) for pattern in company_code_patterns):
            return True
        
        # 6. Allow drug names with common suffixes
        drug_suffixes = ['mab', 'nib', 'tinib', 'cept', 'zumab', 'ximab', 'tumab', 'lamab', 'sib', 'lisib', 'ciclib', 'fetinib', 'mig', 'vedotin', 'deruxtecan', 'emtansine', 'autoleucel']
        if any(name.lower().endswith(suffix) for suffix in drug_suffixes):
            return True
        
        # 6b. Allow brand names with common endings
        brand_suffixes = ['sa', 'ta', 'na', 'ma', 'ga', 'ka', 'la', 'ra', 'va', 'ya', 'za']
        if any(name.lower().endswith(suffix) for suffix in brand_suffixes) and len(name) >= 5:
            return True
        
        # 7. Allow multi-word drug names (common in ADCs and complex therapies)
        if ' ' in name and len(name.split()) <= 4:
            return True
        
        # 8. Allow mRNA patterns
        if re.match(r'^mRNA-\d{3,5}$', name, re.IGNORECASE):
            return True
        
        # 9. Default to False for anything else
        return False
        incomplete_patterns = [
            r'\bis\b$', r'\bwas\b$', r'\bis\s+a\b', r'\bis\s+an\b', 
            r'\bwas\s+acquired\b', r'\bis\s+being\b', r'\bexcept\s+as\b',
            r'\bdecline\s+accept\b', r'\baccept\b$'
        ]
        if any(re.search(pattern, name.lower()) for pattern in incomplete_patterns):
            return False
        
        # 5. Filter out descriptive phrases (contains drug class descriptions)
        descriptive_patterns = [
            r'\bdrug\s+conjugate\b', r'\bsmall\s+molecule\b', r'\btherapeutic\s+protein\b',
            r'\bbispecific\s+antibody\b', r'\bpeptide\b', r'\bdose\s+combination\b',
            r'\bmonoclonal\s+antibody\b', r'\bantibody\s+drug\s+conjugate\b'
        ]
        if any(re.search(pattern, name.lower()) for pattern in descriptive_patterns):
            return False
        
        # 6. Filter out common English words and generic terms
        common_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'into', 'during', 'including', 'until', 'against', 'among', 'throughout',
            'despite', 'towards', 'upon', 'concerning', 'up', 'about', 'through', 'before', 
            'after', 'above', 'below', 'down', 'out', 'off', 'over', 'under', 'again', 
            'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 
            'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 
            'can', 'will', 'just', 'should', 'now', 'accept', 'except', 'igG1', 'igG'
        }
        
        if name.lower() in common_words:
            return False
        
        # 7. Positive indicators for drug names (more permissive)
        drug_indicators = [
            # Drug suffixes (monoclonal antibodies, kinase inhibitors, etc.)
            name.lower().endswith(('mab', 'nib', 'tinib', 'cept', 'zumab', 'ximab', 'mab')),
            
            # RG codes (Roche/Genentech internal codes)
            re.match(r'^rg\d+', name.lower()),
            
            # MK codes (Merck internal codes)
            re.match(r'^mk-\d+', name.lower()),
            
            # Complex multi-word names with drug suffixes
            len(name.split()) > 1 and any(word.endswith(('mab', 'nib', 'tinib', 'cept')) for word in name.split()),
            
            # Names with common drug prefixes/suffixes
            re.search(r'(pembrolizumab|nivolumab|sotatercept|patritumab|sacituzumab|zilovertamab|nemtabrutinib|quavonlimab|clesrovimab|ifinatamab|bezlotoxumab)', name.lower()),
            
            # Allow names that look like drug names (capitalized, reasonable length)
            len(name) >= 4 and name[0].isupper() and not re.match(r'^[A-Z]{2,4}\d*$', name) and not re.match(r'^NCT\d+', name)
        ]
        
        return any(drug_indicators)
    
    async def _collect_company_comprehensive_data(self, crawler, company: str, base_url: str) -> List[CollectedData]:
        """Collect comprehensive data from multiple company website sections."""
        collected_data = []
        
        # Define page types to collect - expanded for comprehensive coverage
        page_types = [
            ("pipeline", ["pipeline", "development", "research", "programs", "candidates"]),
            ("clinical_trials", ["clinical", "trials", "studies", "research", "nct"]),
            ("products", ["products", "therapeutics", "medicines", "drugs", "approved"]),
            ("oncology", ["oncology", "cancer", "tumor", "immunotherapy", "onco"]),
            ("partnerships", ["partnership", "collaboration", "alliance", "license", "deal"]),
            ("news", ["news", "press", "release", "announcement", "milestone"]),
            ("technology", ["technology", "platform", "capability", "innovation", "science"]),
            ("regulatory", ["regulatory", "fda", "approval", "milestone", "submission"]),
            ("about", ["about", "company", "overview", "mission", "leadership"]),
            ("investor", ["investor", "financial", "earnings", "presentation", "report"])
        ]
        
        for page_type, keywords in page_types:
            try:
                # Find relevant pages
                pages = await self._find_company_pages(crawler, base_url, keywords)
                
                for page_url in pages[:2]:  # Limit to 2 pages per type
                    try:
                        result = await crawler.arun(
                            url=page_url,
                            word_count_threshold=20,
                            extraction_strategy="NoExtractionStrategy",
                            bypass_cache=True
                        )
                        
                        if result.success and result.cleaned_html:
                            content = self._extract_specialized_content(
                                result.cleaned_html, company, page_type, keywords
                            )
                            
                            if content:
                                data = CollectedData(
                                    title=f"{company} - {page_type.title()} Information",
                                    content=content,
                                    source_url=page_url,
                                    source_type=f"company_{page_type}",
                                    metadata={
                                        "company": company,
                                        "page_type": page_type,
                                        "keywords": keywords,
                                        "content_length": len(content)
                                    }
                                )
                                collected_data.append(data)
                                logger.info(f"✅ Collected {page_type} data for {company}")
                    
                    except Exception as e:
                        logger.warning(f"Error collecting {page_type} data for {company}: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Error finding {page_type} pages for {company}: {e}")
                continue
        
        return collected_data
    
    async def _find_company_pages(self, crawler, base_url: str, keywords: List[str]) -> List[str]:
        """Find relevant pages on company website based on keywords."""
        found_pages = []
        
        try:
            # First, try to find sitemap or navigation
            sitemap_urls = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/robots.txt"
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    result = await crawler.arun(url=sitemap_url, bypass_cache=True)
                    if result.success:
                        # Extract URLs from sitemap
                        urls = self._extract_urls_from_sitemap(result.cleaned_html, keywords)
                        found_pages.extend(urls)
                except:
                    continue
            
            # If no sitemap found, try common page patterns
            if not found_pages:
                common_patterns = [
                    f"{base_url}/pipeline",
                    f"{base_url}/research",
                    f"{base_url}/development",
                    f"{base_url}/clinical-trials",
                    f"{base_url}/products",
                    f"{base_url}/oncology",
                    f"{base_url}/about",
                    f"{base_url}/company"
                ]
                found_pages.extend(common_patterns)
            
        except Exception as e:
            logger.warning(f"Error finding pages: {e}")
        
        return found_pages[:5]  # Limit to 5 pages per company
    
    def _extract_urls_from_sitemap(self, sitemap_content: str, keywords: List[str]) -> List[str]:
        """Extract relevant URLs from sitemap content."""
        urls = []
        
        # Simple URL extraction from sitemap XML
        url_pattern = r'<loc>(.*?)</loc>'
        matches = re.findall(url_pattern, sitemap_content)
        
        for url in matches:
            url_lower = url.lower()
            if any(keyword in url_lower for keyword in keywords):
                urls.append(url)
        
        return urls
    
    def _get_company_website(self, company: str) -> Optional[str]:
        """Get company official website URL from CSV."""
        # Read from CSV if available
        try:
            import pandas as pd
            df = pd.read_csv("data/companies.csv")
            company_row = df[df["Company"] == company]
            if not company_row.empty:
                # Try OfficialWebsite first, fallback to PipelineURL if not available
                official_website = company_row.iloc[0].get("OfficialWebsite")
                if official_website and pd.notna(official_website):
                    return official_website
                else:
                    # Fallback to PipelineURL if OfficialWebsite is not available
                    return company_row.iloc[0].get("PipelineURL")
        except Exception as e:
            logger.warning(f"Could not read company CSV: {e}")
        
        # Fallback: construct URL based on company name
        company_lower = company.lower().replace(" ", "").replace("&", "").replace("(", "").replace(")", "")
        return f"https://www.{company_lower}.com"
    
    def _get_company_pipeline_url(self, company: str) -> Optional[str]:
        """Get company pipeline URL from CSV for specific pipeline drug collection."""
        try:
            import pandas as pd
            df = pd.read_csv("data/companies.csv")
            company_row = df[df["Company"] == company]
            if not company_row.empty:
                return company_row.iloc[0].get("PipelineURL")
        except Exception as e:
            logger.warning(f"Could not read company CSV: {e}")
        
        # Fallback: construct URL based on company name
        company_lower = company.lower().replace(" ", "").replace("&", "").replace("(", "").replace(")", "")
        return f"https://www.{company_lower}.com/pipeline"
    
    def _get_company_news_url(self, company: str) -> Optional[str]:
        """Get company news/press release URL from CSV."""
        try:
            import pandas as pd
            df = pd.read_csv("data/companies.csv")
            company_row = df[df["Company"] == company]
            if not company_row.empty:
                return company_row.iloc[0].get("NewsURL")
        except Exception as e:
            logger.warning(f"Could not read company CSV: {e}")
        
        # Fallback: construct URL based on company name
        company_lower = company.lower().replace(" ", "").replace("&", "").replace("(", "").replace(")", "")
        return f"https://www.{company_lower}.com/news"
    
    async def _crawl_news_pages(self, crawler, company: str) -> List[CollectedData]:
        """Crawl news and press release pages for the latest biopharma developments."""
        collected_data = []
        
        try:
            logger.info(f"📰 Crawling news pages for {company}")
            
            # Get news URL from CSV
            news_url = self._get_company_news_url(company)
            if not news_url:
                logger.warning(f"No news URL found for {company}, skipping...")
                return collected_data
            
            # Use regular HTML extraction for news content (more reliable)
            extraction_strategy = "NoExtractionStrategy"
            logger.info(f"Using HTML extraction for {company} news")
            
            # Crawl news pages with comprehensive extraction
            result = await crawler.arun(
                url=news_url,
                word_count_threshold=30,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                max_pages=5,  # Crawl up to 5 news pages
                max_depth=1,  # Stay within news section
                delay_between_requests=1.0
            )
            
            if result.success:
                if result.cleaned_html:
                    # Use HTML extraction for news content
                    content = self._extract_news_content_from_html(result.cleaned_html, company, news_url)
                else:
                    logger.warning(f"No content extracted from {company} news")
                    return collected_data
                
                if content and len(content) > 200:  # Only save if we got meaningful content
                    data = CollectedData(
                        title=f"{company} - News & Press Releases",
                        content=content,
                        source_url=news_url,
                        source_type="company_news",
                        metadata={
                            "company": company,
                            "crawl_type": "news_crawl",
                            "content_length": len(content),
                            "extraction_method": "html_extraction",
                            "news_drugs_found": 0  # Will be calculated in HTML extraction
                        }
                    )
                    collected_data.append(data)
                    logger.info(f"✅ Crawled {company} news: {len(content)} characters")
                else:
                    logger.warning(f"⚠️ Insufficient content extracted from {company} news")
            
            else:
                logger.warning(f"⚠️ News crawl failed for {company}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                
        except Exception as e:
            logger.error(f"❌ Error crawling news for {company}: {e}")
        
        return collected_data

    def _extract_news_content_from_html(self, html_content: str, company: str, news_url: str) -> str:
        """Extract news content from HTML when LLM extraction is not available."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'form', 'aside']):
                element.decompose()
            
            # Extract text content
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Extract news-specific content
            content_parts = [
                f"Company: {company}",
                f"Source: News & Press Releases (HTML Extracted)",
                f"URL: {news_url}",
                f"Collection Date: {asyncio.get_event_loop().time()}",
                "",
                "=== NEWS CONTENT ===",
                text_content[:8000] + "..." if len(text_content) > 8000 else text_content,
                "",
                "=== EXTRACTED DRUG NAMES ===",
                "\n".join([f"- {drug}" for drug in self._extract_drug_names_from_html(html_content, company)]),
                "",
                "=== EXTRACTED NCT CODES ===",
                "\n".join([f"- {nct}" for nct in self._extract_nct_codes_from_text(text_content)])
            ]
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error extracting news content from HTML: {e}")
            return f"Company: {company}\nSource: {news_url}\nError: Could not extract news content from HTML"
    
    async def collect_news_data(self, max_companies: int = 10) -> List[CollectedData]:
        """Collect news and press release data from all companies."""
        collected_data = []
        
        # Get company list from CSV
        companies = get_target_companies()[:max_companies]
        
        logger.info(f"Starting news collection for {len(companies)} companies")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company in companies:
                try:
                    logger.info(f"📰 Collecting news for {company}...")
                    
                    # Crawl news pages
                    news_data = await self._crawl_news_pages(crawler, company)
                    collected_data.extend(news_data)
                    
                    logger.info(f"✅ Collected {len(news_data)} news documents for {company}")
                        
                except Exception as e:
                    logger.error(f"Error collecting news for {company}: {e}")
            
            logger.info(f"🎉 Total news documents collected: {len(collected_data)}")
            return collected_data

    def _extract_specialized_content(self, html_content: str, company: str, page_type: str, keywords: List[str]) -> str:
        """Extract specialized content based on page type and keywords."""
        content_parts = [
            f"Company: {company}",
            f"Page Type: {page_type.title()}",
            f"Source: Company Website",
            f"Collection Date: {asyncio.get_event_loop().time()}",
            ""
        ]
        
        # Extract content based on page type
        if page_type == "pipeline":
            content_parts.extend(self._extract_pipeline_content(html_content, keywords))
        elif page_type == "clinical_trials":
            content_parts.extend(self._extract_clinical_trials_content(html_content, keywords))
        elif page_type == "products":
            content_parts.extend(self._extract_products_content(html_content, keywords))
        elif page_type == "oncology":
            content_parts.extend(self._extract_oncology_content(html_content, keywords))
        else:
            content_parts.extend(self._extract_general_content(html_content, keywords))
        
        return "\n".join(content_parts)
    
    def _extract_pipeline_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract pipeline-specific content."""
        content = [
            "Pipeline Information:",
            "This section contains information about the company's drug development pipeline,",
            "including investigational drugs, development stages, and therapeutic areas.",
            ""
        ]
        
        # Look for pipeline-specific patterns
        pipeline_patterns = [
            r"phase\s+[i1-3]", r"preclinical", r"clinical\s+trial", r"fda\s+approval",
            r"ind\s+\(investigational\s+new\s+drug\)", r"nda\s+\(new\s+drug\s+application\)",
            r"bla\s+\(biologics\s+license\s+application\)", r"orphan\s+drug",
            r"breakthrough\s+therapy", r"fast\s+track", r"priority\s+review"
        ]
        
        paragraphs = html_content.split('\n')
        relevant_paragraphs = []
        
        for para in paragraphs:
            para_lower = para.lower()
            if (any(keyword in para_lower for keyword in keywords) or 
                any(re.search(pattern, para_lower) for pattern in pipeline_patterns)):
                if len(para.strip()) > 30:
                    relevant_paragraphs.append(para.strip())
        
        if relevant_paragraphs:
            content.extend(relevant_paragraphs[:8])
        else:
            content.extend([
                "Pipeline data extraction placeholder.",
                "In a full implementation, this would contain:",
                "- Drug names and development stages",
                "- Therapeutic areas and indications",
                "- Clinical trial phases and status",
                "- Regulatory milestones and timelines",
                "- Partnership and collaboration information"
            ])
        
        return content
    
    def _extract_clinical_trials_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract clinical trials-specific content."""
        content = [
            "Clinical Trials Information:",
            "This section contains information about ongoing and completed clinical trials,",
            "including study designs, patient populations, and outcomes.",
            ""
        ]
        
        # Look for clinical trial patterns
        trial_patterns = [
            r"nct\d+", r"clinical\s+trial", r"study\s+design", r"primary\s+endpoint",
            r"secondary\s+endpoint", r"inclusion\s+criteria", r"exclusion\s+criteria",
            r"patient\s+population", r"dose\s+escalation", r"safety\s+profile",
            r"efficacy\s+data", r"overall\s+survival", r"progression\s+free\s+survival"
        ]
        
        paragraphs = html_content.split('\n')
        relevant_paragraphs = []
        
        for para in paragraphs:
            para_lower = para.lower()
            if (any(keyword in para_lower for keyword in keywords) or 
                any(re.search(pattern, para_lower) for pattern in trial_patterns)):
                if len(para.strip()) > 30:
                    relevant_paragraphs.append(para.strip())
        
        if relevant_paragraphs:
            content.extend(relevant_paragraphs[:8])
        else:
            content.extend([
                "Clinical trials data extraction placeholder.",
                "In a full implementation, this would contain:",
                "- NCT numbers and trial identifiers",
                "- Study phases and designs",
                "- Patient enrollment information",
                "- Primary and secondary endpoints",
                "- Safety and efficacy results",
                "- Regulatory submissions and approvals"
            ])
        
        return content
    
    def _extract_products_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract products-specific content."""
        content = [
            "Products Information:",
            "This section contains information about approved and marketed products,",
            "including indications, mechanisms of action, and commercial information.",
            ""
        ]
        
        # Look for product patterns
        product_patterns = [
            r"indication", r"mechanism\s+of\s+action", r"dosing", r"administration",
            r"contraindication", r"adverse\s+event", r"side\s+effect", r"warning",
            r"precaution", r"drug\s+interaction", r"pharmacokinetic", r"pharmacodynamic"
        ]
        
        paragraphs = html_content.split('\n')
        relevant_paragraphs = []
        
        for para in paragraphs:
            para_lower = para.lower()
            if (any(keyword in para_lower for keyword in keywords) or 
                any(re.search(pattern, para_lower) for pattern in product_patterns)):
                if len(para.strip()) > 30:
                    relevant_paragraphs.append(para.strip())
        
        if relevant_paragraphs:
            content.extend(relevant_paragraphs[:8])
        else:
            content.extend([
                "Products data extraction placeholder.",
                "In a full implementation, this would contain:",
                "- Product names and brand names",
                "- Approved indications and uses",
                "- Mechanism of action descriptions",
                "- Dosing and administration guidelines",
                "- Safety and efficacy profiles",
                "- Commercial and market information"
            ])
        
        return content
    
    def _extract_oncology_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract oncology-specific content."""
        content = [
            "Oncology Information:",
            "This section contains information about cancer-related products and research,",
            "including tumor types, biomarkers, and therapeutic approaches.",
            ""
        ]
        
        # Look for oncology patterns
        oncology_patterns = [
            r"cancer", r"tumor", r"neoplasm", r"carcinoma", r"sarcoma", r"lymphoma",
            r"leukemia", r"metastasis", r"biomarker", r"immunotherapy", r"targeted\s+therapy",
            r"chemotherapy", r"radiation", r"precision\s+medicine", r"companion\s+diagnostic",
            r"pd\s*-\s*1", r"pd\s*-\s*l1", r"ctla\s*-\s*4", r"her2", r"egfr", r"alk"
        ]
        
        paragraphs = html_content.split('\n')
        relevant_paragraphs = []
        
        for para in paragraphs:
            para_lower = para.lower()
            if (any(keyword in para_lower for keyword in keywords) or 
                any(re.search(pattern, para_lower) for pattern in oncology_patterns)):
                if len(para.strip()) > 30:
                    relevant_paragraphs.append(para.strip())
        
        if relevant_paragraphs:
            content.extend(relevant_paragraphs[:8])
        else:
            content.extend([
                "Oncology data extraction placeholder.",
                "In a full implementation, this would contain:",
                "- Cancer types and tumor indications",
                "- Biomarker and genetic information",
                "- Immunotherapy and targeted therapy approaches",
                "- Clinical trial results in oncology",
                "- Regulatory approvals for cancer treatments",
                "- Partnership and collaboration in oncology"
            ])
        
        return content
    
    def _extract_general_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract general company content."""
        content = [
            "General Company Information:",
            "This section contains general information about the company,",
            "including corporate overview, mission, and strategic focus areas.",
            ""
        ]
        
        paragraphs = html_content.split('\n')
        relevant_paragraphs = []
        
        for para in paragraphs:
            para_lower = para.lower()
            if any(keyword in para_lower for keyword in keywords):
                if len(para.strip()) > 50:
                    relevant_paragraphs.append(para.strip())
        
        if relevant_paragraphs:
            content.extend(relevant_paragraphs[:6])
        else:
            content.extend([
                "General company data extraction placeholder.",
                "In a full implementation, this would contain:",
                "- Company overview and mission",
                "- Strategic focus areas and priorities",
                "- Research and development capabilities",
                "- Corporate partnerships and collaborations",
                "- Financial and business information"
            ])
        
        return content
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []
