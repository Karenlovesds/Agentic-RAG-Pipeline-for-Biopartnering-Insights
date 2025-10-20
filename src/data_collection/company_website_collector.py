"""Enhanced company website data collector for pipeline and development information."""

import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from .base_collector import BaseCollector, CollectedData
from .sec_filings_extractor import SECFilingsExtractor
from .data_validator import DataValidator
from config.config import get_target_companies


class CompanyWebsiteCollector(BaseCollector):
    """Enhanced collector for company website data using crawl4AI with SEC filings integration."""
    
    def __init__(self):
        super().__init__("company_websites", "")
        self.sec_extractor = SECFilingsExtractor()
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
                    
                    # Extract SEC filings for additional pipeline information
                    sec_data = await self._collect_sec_filings_data(company)
                    
                    # Extract drug names for validation
                    extracted_drugs = self._extract_drug_names_from_data(company_data, sec_data)
                    
                    # Validate drugs comprehensively
                    if extracted_drugs:
                        validated_data = await self._validate_drugs_comprehensively(extracted_drugs, company)
                        collected_data.extend(validated_data)
                    
                    # Combine website and SEC data
                    combined_data = self._combine_website_and_sec_data(company_data, sec_data, company)
                    collected_data.extend(combined_data)
                    
                    logger.info(f"✅ Completed comprehensive collection for {company} (website + SEC filings + validation)")
                        
                except Exception as e:
                    logger.error(f"Error collecting data for {company}: {e}")
                    continue
        
        return collected_data

    async def _collect_sec_filings_data(self, company: str) -> List[CollectedData]:
        """Collect SEC filings data for a company."""
        try:
            logger.info(f"Collecting SEC filings data for {company}")
            
            # Extract pipeline information from SEC filings
            sec_filings = await self.sec_extractor.extract_pipeline_from_filings(company, max_filings=5)
            
            collected_data = []
            for filing in sec_filings:
                if filing.extracted_pipeline_info:
                    # Create content from extracted pipeline information
                    content_parts = [
                        f"SEC Filing Pipeline Information for {company}",
                        f"Filing Type: {filing.filing_type}",
                        f"Filing Date: {filing.filing_date}",
                        f"Accession Number: {filing.accession_number}",
                        f"Confidence Score: {filing.confidence_score:.2f}",
                        "",
                        "Extracted Pipeline Information:",
                        ""
                    ]
                    
                    for pipeline_info in filing.extracted_pipeline_info:
                        content_parts.extend([
                            f"Drug: {pipeline_info['drug_name']}",
                            f"  Development Stage: {pipeline_info.get('development_stage', 'N/A')}",
                            f"  Indication: {pipeline_info.get('indication', 'N/A')}",
                            f"  Target: {pipeline_info.get('target', 'N/A')}",
                            f"  Phase: {pipeline_info.get('phase', 'N/A')}",
                            f"  Status: {pipeline_info.get('status', 'N/A')}",
                            f"  Mechanism of Action: {pipeline_info.get('mechanism_of_action', 'N/A')}",
                            f"  Confidence: {pipeline_info.get('extraction_confidence', 0.0):.2f}",
                            ""
                        ])
                    
                    content = "\n".join(content_parts)
                    
                    collected_data.append(CollectedData(
                        title=f"SEC Filing - {filing.filing_type} - {company}",
                        content=content,
                        source_url=filing.document_url,
                        source_type="sec_filing",
                        metadata={
                            "company": company,
                            "filing_type": filing.filing_type,
                            "filing_date": filing.filing_date,
                            "accession_number": filing.accession_number,
                            "pipeline_entries": len(filing.extracted_pipeline_info),
                            "confidence_score": filing.confidence_score
                        }
                    ))
            
            logger.info(f"✅ Collected SEC filings data for {company}: {len(collected_data)} filings")
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting SEC filings data for {company}: {e}")
            return []

    def _combine_website_and_sec_data(self, website_data: List[CollectedData], sec_data: List[CollectedData], company: str) -> List[CollectedData]:
        """Combine website and SEC filings data."""
        combined_data = []
        
        # Add website data
        combined_data.extend(website_data)
        
        # Add SEC data
        combined_data.extend(sec_data)
        
        # Create a summary entry if both sources have data
        if website_data and sec_data:
            summary_content = self._create_combined_summary(website_data, sec_data, company)
            combined_data.append(CollectedData(
                title=f"Combined Data Summary - {company}",
                content=summary_content,
                source_url="",
                source_type="combined_summary",
                metadata={
                    "company": company,
                    "website_entries": len(website_data),
                    "sec_entries": len(sec_data),
                    "total_entries": len(combined_data)
                }
            ))
        
        return combined_data

    def _create_combined_summary(self, website_data: List[CollectedData], sec_data: List[CollectedData], company: str) -> str:
        """Create a summary of combined website and SEC data."""
        summary_parts = [
            f"Combined Data Summary for {company}",
            f"Collection Date: {asyncio.get_event_loop().time()}",
            "",
            f"Website Data Entries: {len(website_data)}",
            f"SEC Filings Entries: {len(sec_data)}",
            "",
            "Data Sources:",
            "- Company Website (pipeline, clinical trials, products)",
            "- SEC Filings (10-K, 10-Q, 8-K reports)",
            "",
            "This combined dataset provides comprehensive pipeline information",
            "from both public website content and official regulatory filings.",
            ""
        ]
        
        # Extract unique drug names from both sources
        all_drugs = set()
        
        # Extract from website data
        for data in website_data:
            if "drug" in data.content.lower():
                # Simple drug extraction for summary
                drug_matches = re.findall(r'\b[A-Z][a-z]+mab\b|\b[A-Z][a-z]+nib\b|\b[A-Z][a-z]+tinib\b', data.content)
                all_drugs.update(drug_matches)
        
        # Extract from SEC data
        for data in sec_data:
            if "drug" in data.content.lower():
                drug_matches = re.findall(r'\b[A-Z][a-z]+mab\b|\b[A-Z][a-z]+nib\b|\b[A-Z][a-z]+tinib\b', data.content)
                all_drugs.update(drug_matches)
        
        if all_drugs:
            summary_parts.extend([
                f"Unique Drugs Identified: {len(all_drugs)}",
                f"Drug Names: {', '.join(sorted(all_drugs)[:10])}" + ("..." if len(all_drugs) > 10 else ""),
                ""
            ])
        
        return "\n".join(summary_parts)

    def _extract_drug_names_from_data(self, website_data: List[CollectedData], sec_data: List[CollectedData]) -> List[str]:
        """Extract drug names from collected data."""
        drug_names = set()
        
        # Extract from website data
        for data in website_data:
            if "drug" in data.content.lower():
                # Simple drug extraction for validation
                drug_matches = re.findall(r'\b[A-Z][a-z]+mab\b|\b[A-Z][a-z]+nib\b|\b[A-Z][a-z]+tinib\b', data.content)
                drug_names.update(drug_matches)
        
        # Extract from SEC data
        for data in sec_data:
            if "drug" in data.content.lower():
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
                    f"Pipeline Entries: {len(drug_data.pipeline_info)}",
                    f"SEC Filings: {len(drug_data.sec_filings)}",
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
                        "indications_count": len(drug_data.indications),
                        "pipeline_entries": len(drug_data.pipeline_info),
                        "sec_filings": len(drug_data.sec_filings)
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
                    
                    # Get company website
                    company_urls = self._get_company_urls(company)
                    if not company_urls:
                        logger.warning(f"No URLs found for {company}, skipping...")
                        continue
                    
                    # Find and scrape pipeline pages
                    drug_nct_mapping = await self._extract_pipeline_drugs(crawler, company, company_urls)
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
                    
                    # Get company website
                    company_urls = self._get_company_urls(company)
                    if not company_urls:
                        logger.warning(f"No URLs found for {company}, skipping...")
                        continue
                    
                    # Find and scrape pipeline pages
                    drug_nct_mapping = await self._extract_pipeline_drugs(crawler, company, company_urls)
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

    async def _extract_pipeline_drugs(self, crawler, company: str, company_urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Extract drug names and associated NCT codes from company URLs."""
        drug_names = set()
        all_text_content = ""
        
        # Use the three specific URLs from CSV
        urls_to_scrape = [
            ("official", company_urls["official"]),
            ("pipeline", company_urls["pipeline"]),
            ("news", company_urls["news"])
        ]
        
        for url_type, url in urls_to_scrape:
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
                    # Extract drug names from this page
                    page_drugs = self._extract_drug_names_from_html(result.cleaned_html, company)
                    drug_names.update(page_drugs)
                    
                    # Also collect text content for NCT code association
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
                    page_text = soup.get_text(separator=' ', strip=True)
                    all_text_content += " " + page_text
                    
                    logger.info(f"Found {len(page_drugs)} drugs on {url_type} URL: {url}")
                
            except Exception as e:
                logger.warning(f"Error scraping {url_type} URL {url}: {e}")
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
        """Validate if a name is likely a drug name using strict whitelist approach."""
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Check if it contains only letters, numbers, and common drug characters
        if not re.match(r'^[A-Za-z0-9\-\s\/\(\)]+$', name):
            return False
        
        # 1. Filter out clinical trial IDs (NCT followed by 8 digits)
        if re.match(r'^NCT\d{8}$', name):
            return False
        
        # 2. STRICT WHITELIST APPROACH - Only allow specific patterns
        # 2a. Company codes (AMG, ABP, RG, etc.)
        company_code_patterns = [
            r'^AMG\s?\d{3,4}$', r'^ABP\s?\d{3,4}$', r'^RG\d{3,5}$', r'^GDC\d{3,5}$',
            r'^RGT\d{3,5}$', r'^ABBV\d{3,5}$', r'^DS\d{3,5}$', r'^BAY\s?\d{3,7}$',
            r'^VVD-\d{3,6}$', r'^JNJ-\d{3,5}$', r'^TAR-\d{3}$', r'^REGN\d{3,5}$',
            r'^MK-\d{3,5}[A-Z]?$', r'^GS-\d{3,5}$', r'^AAA\d{3}$', r'^NVL-\d{3}$',
            r'^S\d{5}$'
        ]
        
        if any(re.match(pattern, name, re.IGNORECASE) for pattern in company_code_patterns):
            return True
        
        # 2b. Drug names with specific suffixes
        drug_suffixes = ['mab', 'nib', 'tinib', 'cept', 'zumab', 'ximab', 'tumab', 'lamab', 'sib', 'lisib', 'ciclib', 'fetinib', 'mig', 'vedotin', 'deruxtecan', 'emtansine', 'autoleucel']
        if any(name.lower().endswith(suffix) for suffix in drug_suffixes):
            return True
        
        # 2c. Known drug names (brand and generic)
        known_drugs = [
            'trastuzumab', 'pertuzumab', 'bevacizumab', 'rituximab', 'adalimumab',
            'infliximab', 'etanercept', 'golimumab', 'certolizumab', 'vedolizumab',
            'natalizumab', 'ocrelizumab', 'ofatumumab', 'obinutuzumab', 'alemtuzumab',
            'daratumumab', 'elotuzumab', 'isatuximab', 'belantamab', 'polatuzumab',
            'brentuximab', 'gemtuzumab', 'inotuzumab', 'moxetumomab', 'sacituzumab',
            'enfortumab', 'fam-trastuzumab', 'trodelvy', 'kadcyla', 'enhertu',
            'herceptin', 'perjeta', 'avastin', 'rituxan', 'humira', 'remicade',
            'enbrel', 'simponi', 'cimzia', 'entyvio', 'tysabri', 'ocrevus',
            'kesimpta', 'gazyva', 'campath', 'darzalex', 'emplify', 'sarclisa',
            'blenrep', 'polivy', 'adcetris', 'mylotarg', 'besponsa', 'lumoxiti',
            'padcev', 'bemarituzumab', 'blinatumomab', 'daxdilimab', 'tarlatamab',
            'teprotumumab', 'xaluritamig', 'inebilizumab', 'ordesekimab', 'rocatinlimab',
            'sotorasib', 'tezepelumab', 'romiplostim', 'romosozumab', 'evolocumab',
            'erenumab', 'nivolumab', 'pembrolizumab', 'ocrelizumab', 'ustekinumab'
        ]
        
        if name.lower() in known_drugs:
            return True
        
        # 2d. mRNA patterns
        if re.match(r'^mRNA-\d{3,5}$', name, re.IGNORECASE):
            return True
        
        # 3. REJECT EVERYTHING ELSE
        return False
    
    async def _collect_company_comprehensive_data(self, crawler, company: str, company_urls: Dict[str, str]) -> List[CollectedData]:
        """Collect comprehensive data from company URLs: OfficialWebsite, PipelineURL, NewsURL."""
        collected_data = []
        
        # Define URL types and their purposes
        url_types = [
            ("official", company_urls["official"], ["company", "overview", "mission", "about"]),
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
                        collected_data.append(CollectedData(
                            source=f"{company}_{url_type}_website",
                            content=content,
                            metadata={
                                "company": company,
                                "url": url,
                                "url_type": url_type,
                                "keywords": keywords,
                                "content_length": len(content)
                            }
                        ))
                        
                        logger.info(f"Collected {len(content)} characters from {company} {url_type} website")
                    else:
                        logger.warning(f"No content extracted from {company} {url_type} website")
                else:
                    logger.warning(f"Failed to scrape {company} {url_type} website: {url}")
                    
            except Exception as e:
                logger.error(f"Error collecting data from {company} {url_type} website: {e}")
                continue
        
        return collected_data
    
    def _get_company_urls(self, company: str) -> Dict[str, str]:
        """Get all company URLs from CSV: OfficialWebsite, PipelineURL, NewsURL."""
        try:
            import pandas as pd
            df = pd.read_csv("data/companies.csv")
            company_row = df[df["Company"] == company]
            if not company_row.empty:
                return {
                    "official": company_row.iloc[0]["OfficialWebsite"],
                    "pipeline": company_row.iloc[0]["PipelineURL"],
                    "news": company_row.iloc[0]["NewsURL"]
                }
        except Exception as e:
            logger.warning(f"Could not read company URLs from CSV: {e}")
        
        # Fallback: construct URLs based on company name
        company_lower = company.lower().replace(" ", "").replace("&", "").replace("(", "").replace(")", "")
        base_url = f"https://www.{company_lower}.com"
        return {
            "official": base_url,
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
        elif page_type == "clinical_trials":
            content_parts.extend(self._extract_clinical_trials_content(html_content, keywords))
        elif page_type == "products":
            content_parts.extend(self._extract_products_content(html_content, keywords))
        elif page_type == "oncology":
            content_parts.extend(self._extract_oncology_content(html_content, keywords))
        else:
            content_parts.extend(self._extract_general_content(html_content, keywords))
        
        return "\n".join(content_parts)
    
    async def _collect_company_comprehensive_data(self, crawler, company: str, company_urls: Dict[str, str]) -> List[CollectedData]:
        """Collect comprehensive data from company URLs: OfficialWebsite, PipelineURL, NewsURL."""
        collected_data = []
        
        # Define URL types and their purposes
        url_types = [
            ("official", company_urls["official"], ["company", "overview", "mission", "about"]),
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
    
    def _extract_general_content(self, html_content: str, keywords: List[str]) -> List[str]:
        """Extract general company content."""
        content = ["General Company Information:", ""]
        
        # Simple extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Get first few paragraphs
        paragraphs = text_content.split('\n\n')
        for para in paragraphs[:3]:
            if len(para.strip()) > 50:
                content.append(para.strip()[:200] + "...")
        
        if len(content) <= 2:
            content.append("No general company information found.")
        
        return content
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []
