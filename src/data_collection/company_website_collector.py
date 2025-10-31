"""Enhanced company website data collector for pipeline and development information."""

import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from .utils import BaseCollector, CollectedData
from .data_validator import DataValidator
from config.config import get_target_companies


class CompanyWebsiteCollector(BaseCollector):
    """Enhanced collector for company website data using crawl4AI."""
    
    def __init__(self):
        super().__init__("company_websites", "")
        self.data_validator = DataValidator()
    
    async def collect_data(self, max_companies: int = 5) -> List[CollectedData]:
        """Collect comprehensive data from company websites focusing on pipelines and development."""
        collected_data = []
        
        # Get company list from CSV
        companies = get_target_companies()[:max_companies]
        
        logger.info(f"Starting comprehensive company website collection for {len(companies)} companies")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company in companies:
                try:
                    logger.info(f"Collecting comprehensive data for {company}...")
                    
                    # Get company URLs
                    company_urls = self._get_company_urls(company)
                    if not company_urls:
                        logger.warning(f"No URLs found for {company}, skipping...")
                        continue
                    
                    # Collect data from multiple page types
                    company_data = await self._collect_company_comprehensive_data(crawler, company, company_urls)
                    
                    # Extract drug names for validation
                    extracted_drugs = self._extract_drug_names_from_data(company_data, [])
                    
                    # Validate drugs comprehensively
                    if extracted_drugs:
                        validated_data = await self._validate_drugs_comprehensively(extracted_drugs, company)
                        collected_data.extend(validated_data)
                    
                    # Use website data directly
                    collected_data.extend(company_data)
                    
                    logger.info(f"✅ Completed comprehensive collection for {company} (website + validation)")
                        
                except Exception as e:
                    logger.error(f"Error collecting data for {company}: {e}")
                    continue
        
        return collected_data


    def _extract_drug_names_from_data(self, website_data: List[CollectedData], sec_data: List[CollectedData] = None) -> List[str]:
        """Extract drug names from collected data."""
        drug_names = set()
        
        # Extract from website data
        for data in website_data:
            if "drug" in data.content.lower():
                # Simple drug extraction for validation
                drug_matches = re.findall(r'\b[A-Z][a-z]+mab\b|\b[A-Z][a-z]+nib\b|\b[A-Z][a-z]+tinib\b', data.content)
                drug_names.update(drug_matches)
        
        return list(drug_names)

    async def _validate_drugs_comprehensively(self, drug_names: List[str], company: str) -> List[CollectedData]:
        """Validate drugs comprehensively using all sources."""
        try:
            logger.info(f"Validating {len(drug_names)} drugs comprehensively for {company}")
            
            # Use data validator for comprehensive validation
            comprehensive_data, validation_report = await self.data_validator.validate_drug_list_comprehensive(drug_names, company)
            
            collected_data = []
            
            # Create collected data entries for each validated drug
            for drug_data in comprehensive_data:
                content_parts = [
                    f"Comprehensive Drug Validation Report for {drug_data.drug_name}",
                    f"Company: {company}",
                    f"Overall Confidence: {drug_data.overall_confidence:.3f}",
                    f"Data Sources: {', '.join(drug_data.data_sources)}",
                    "",
                    "Validation Results:",
                    ""
                ]
                
                for result in drug_data.validation_results:
                    status_icon = "✅" if result.validation_status == "validated" else "⚠️" if result.validation_status == "partial" else "❌"
                    content_parts.append(f"{status_icon} {result.source}: {result.confidence_score:.3f} ({result.validation_status})")
                
                content_parts.extend([
                    "",
                    f"Targets Found: {len(drug_data.targets)}",
                    f"Indications Found: {len(drug_data.indications)}",
                    ""
                ])
                
                # Add top targets
                if drug_data.targets:
                    content_parts.extend([
                        "Top Targets:",
                        ""
                    ])
                    for target in drug_data.targets[:5]:
                        content_parts.append(f"- {target.target_name} ({target.target_type}) - {target.confidence_score:.3f}")
                    content_parts.append("")
                
                # Add top indications
                if drug_data.indications:
                    content_parts.extend([
                        "Top Indications:",
                        ""
                    ])
                    for indication in drug_data.indications[:5]:
                        status = "Approved" if indication.approval_status else "Investigational"
                        content_parts.append(f"- {indication.indication} ({status}) - {indication.confidence_score:.3f}")
                    content_parts.append("")
                
                content = "\n".join(content_parts)
                
                collected_data.append(CollectedData(
                    title=f"Comprehensive Validation - {drug_data.drug_name}",
                    content=content,
                    source_url="",
                    source_type="comprehensive_validation",
                    metadata={
                        "company": company,
                        "drug_name": drug_data.drug_name,
                        "overall_confidence": drug_data.overall_confidence,
                        "data_sources": drug_data.data_sources,
                        "targets_count": len(drug_data.targets),
                        "indications_count": len(drug_data.indications)
                    }
                ))
            
            # Add validation report as a separate entry
            collected_data.append(CollectedData(
                title=f"Validation Report - {company}",
                content=validation_report,
                source_url="",
                source_type="validation_report",
                metadata={
                    "company": company,
                    "drugs_validated": len(drug_names),
                    "validation_timestamp": datetime.now().isoformat()
                }
            ))
            
            logger.info(f"✅ Completed comprehensive validation for {company}: {len(collected_data)} entries")
            return collected_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive validation for {company}: {e}")
            return []
    
    def _get_company_urls(self, company: str) -> Dict[str, str]:
        """Get company URLs from CSV: PipelineURL and NewsURL."""
        try:
            import pandas as pd
            df = pd.read_csv("data/companies.csv")
            company_row = df[df["Company"] == company]
            if not company_row.empty:
                return {
                    "pipeline": company_row.iloc[0]["PipelineURL"],
                    "news": company_row.iloc[0]["NewsURL"]
                }
        except Exception as e:
            logger.warning(f"Could not read company URLs from CSV: {e}")
        
        # Fallback: construct URLs based on company name
        company_lower = company.lower().replace(" ", "").replace("&", "").replace("(", "").replace(")", "")
        base_url = f"https://www.{company_lower}.com"
        return {
            "pipeline": f"{base_url}/pipeline",
            "news": f"{base_url}/news"
        }
    
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
        elif page_type == "news":
            # For news pages, extract general news content
            content_parts.extend(self._extract_news_content(html_content, keywords))
        elif page_type == "clinical_trials":
            content_parts.extend(self._extract_clinical_trials_content(html_content, keywords))
        elif page_type == "products":
            content_parts.extend(self._extract_products_content(html_content, keywords))
        elif page_type == "oncology":
            content_parts.extend(self._extract_oncology_content(html_content, keywords))
        else:
            # Fallback for any other page types
            content_parts.extend(self._extract_general_content(html_content, keywords))
        
        return "\n".join(content_parts)
    
    async def _collect_company_comprehensive_data(self, crawler, company: str, company_urls: Dict[str, str]) -> List[CollectedData]:
        """Collect comprehensive data from company URLs: PipelineURL and NewsURL."""
        collected_data = []
        
        # Define URL types and their purposes (pipeline and news only)
        url_types = [
            ("pipeline", company_urls["pipeline"], ["pipeline", "development", "research", "programs", "drugs"]),
            ("news", company_urls["news"], ["news", "press", "releases", "announcements"])
        ]
        
        for url_type, url, keywords in url_types:
            try:
                # Try with JavaScript rendering first for better content extraction
                from crawl4ai.async_configs import CrawlerRunConfig
                
                config = CrawlerRunConfig(
                    word_count_threshold=20,
                    extraction_strategy=None,
                    js_code="""
                    // Wait for page to load and dynamic content to render
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    
                    // Scroll to load any lazy-loaded content
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    window.scrollTo(0, 0);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    """,
                    wait_until='networkidle',
                    page_timeout=30000,
                    delay_before_return_html=2.0
                )
                
                result = await crawler.arun(url=url, config=config)
                
                # If JavaScript rendering fails, fall back to basic scraping
                if not result.success or len(result.cleaned_html) < 100:
                    logger.info(f"JavaScript rendering failed for {url}, trying basic scraping...")
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=20,
                        extraction_strategy="NoExtractionStrategy",
                        bypass_cache=True
                    )
                
                if result.success and result.cleaned_html:
                    content = self._extract_specialized_content(
                        result.cleaned_html, company, url_type, keywords
                    )
                    
                    if content:
                        data = CollectedData(
                            title=f"{company} - {url_type.title()} Information",
                            content=content,
                            source_url=url,
                            source_type=f"company_{url_type}",
                            metadata={
                                "company": company,
                                "url_type": url_type,
                                "keywords": keywords,
                                "content_length": len(content)
                            }
                        )
                        collected_data.append(data)
                        logger.info(f"✅ Collected {url_type} data for {company} from {url}")
                
            except Exception as e:
                logger.warning(f"Error collecting {url_type} data for {company} from {url}: {e}")
                continue
        
        return collected_data
    
    def _extract_pipeline_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract pipeline-specific content."""
        content = ["Pipeline Information:", ""]
        
        # Simple extraction - just get text content
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Extract drug names
        drug_patterns = [
            r'\b[A-Z][a-z]+mab\b',  # Monoclonal antibodies
            r'\b[A-Z][a-z]+nib\b',  # Kinase inhibitors
            r'\b[A-Z][a-z]+tinib\b',  # Tyrosine kinase inhibitors
        ]
        
        for pattern in drug_patterns:
            matches = re.findall(pattern, text_content)
            if matches:
                unique_drugs = list(set(matches))
                content.append(f"Drugs found: {', '.join(unique_drugs[:5])}")
                break
        
        if len(content) <= 2:
            content.append("No pipeline information found in accessible content.")
        
        return content
    
    def _extract_clinical_trials_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract clinical trials-specific content."""
        content = ["Clinical Trials Information:", ""]
        
        # Look for NCT numbers
        nct_pattern = r'NCT\d{8}'
        nct_matches = re.findall(nct_pattern, html_content)
        if nct_matches:
            unique_ncts = list(set(nct_matches))
            content.append(f"Clinical Trial IDs: {', '.join(unique_ncts[:5])}")
        
        if len(content) <= 2:
            content.append("No clinical trial information found.")
        
        return content
    
    def _extract_products_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract products-specific content."""
        content = ["Products Information:", ""]
        
        # Simple extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Extract product names
        product_patterns = [
            r'\b[A-Z][a-z]+mab\b',  # Monoclonal antibodies
            r'\b[A-Z][a-z]+nib\b',  # Kinase inhibitors
        ]
        
        for pattern in product_patterns:
            matches = re.findall(pattern, text_content)
            if matches:
                unique_products = list(set(matches))
                content.append(f"Products found: {', '.join(unique_products[:5])}")
                break
        
        if len(content) <= 2:
            content.append("No product information found.")
        
        return content
    
    def _extract_oncology_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract oncology-specific content."""
        content = ["Oncology Information:", ""]
        
        # Look for cancer types
        cancer_types = [
            'breast cancer', 'lung cancer', 'prostate cancer', 'colorectal cancer',
            'melanoma', 'lymphoma', 'leukemia', 'ovarian cancer'
        ]
        
        found_cancers = []
        for cancer in cancer_types:
            if cancer in html_content.lower():
                found_cancers.append(cancer)
        
        if found_cancers:
            content.append(f"Cancer types mentioned: {', '.join(found_cancers[:3])}")
        
        if len(content) <= 2:
            content.append("No oncology information found.")
        
        return content
    
    def _extract_news_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract news-specific content."""
        content = ["News and Press Releases:", ""]
        
        # Simple extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Extract drug names mentioned in news
        drug_patterns = [
            r'\b[A-Z][a-z]+mab\b',  # Monoclonal antibodies
            r'\b[A-Z][a-z]+nib\b',  # Kinase inhibitors
            r'\b[A-Z][a-z]+tinib\b',  # Tyrosine kinase inhibitors
        ]
        
        drugs_found = set()
        for pattern in drug_patterns:
            matches = re.findall(pattern, text_content)
            drugs_found.update(matches)
        
        if drugs_found:
            content.append(f"Drugs mentioned: {', '.join(sorted(drugs_found)[:10])}")
        
        # Get first few paragraphs/sentences
        paragraphs = text_content.split('\n\n')
        for para in paragraphs[:3]:
            if len(para.strip()) > 50:
                content.append(para.strip()[:200] + "...")
        
        if len(content) <= 2:
            content.append("No news information found.")
        
        return content
    
    def _extract_general_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract general content (fallback for other page types)."""
        content = ["General Information:", ""]
        
        # Simple extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Get first few paragraphs
        paragraphs = text_content.split('\n\n')
        for para in paragraphs[:3]:
            if len(para.strip()) > 50:
                content.append(para.strip()[:200] + "...")
        
        if len(content) <= 2:
            content.append("No content found.")
        
        return content
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []
