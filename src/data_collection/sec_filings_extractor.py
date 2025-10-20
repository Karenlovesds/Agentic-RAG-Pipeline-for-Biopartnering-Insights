"""SEC filings extractor for pipeline and drug development information."""

import asyncio
import re
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler


@dataclass
class SECFiling:
    """Data class for SEC filing information."""
    company_name: str
    filing_type: str
    filing_date: str
    accession_number: str
    document_url: str
    content: str
    extracted_pipeline_info: List[Dict[str, Any]]
    confidence_score: float


@dataclass
class PipelineInfo:
    """Data class for extracted pipeline information."""
    drug_name: str
    development_stage: str
    indication: str
    target: Optional[str]
    mechanism_of_action: Optional[str]
    phase: Optional[str]
    status: str
    source_filing: str
    extraction_confidence: float


class SECFilingsExtractor:
    """Extract pipeline information from SEC filings."""
    
    def __init__(self):
        self.sec_base_url = "https://www.sec.gov"
        self.edgar_search_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.filing_types = ["10-K", "10-Q", "8-K", "S-1", "424B5"]  # Focus on relevant filings
        self.pipeline_keywords = [
            "pipeline", "development", "clinical trial", "phase", "indication", "target",
            "mechanism of action", "drug candidate", "therapeutic", "oncology", "biomarker",
            "FDA", "approval", "IND", "NDA", "BLA", "fast track", "breakthrough therapy"
        ]
        
        # Initialize NLP for text processing
        try:
            import spacy
            self.nlp = spacy.load("en_core_sci_sm")
        except OSError:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not available, using basic text processing")
                self.nlp = None
    
    async def extract_pipeline_from_filings(self, company_name: str, max_filings: int = 10) -> List[SECFiling]:
        """Extract pipeline information from SEC filings for a company."""
        logger.info(f"Extracting pipeline information from SEC filings for {company_name}")
        
        try:
            # 1. Search for company filings
            filings = await self._search_company_filings(company_name, max_filings)
            
            if not filings:
                logger.warning(f"No SEC filings found for {company_name}")
                return []
            
            # 2. Extract content from relevant filings
            extracted_filings = []
            for filing_info in filings:
                try:
                    filing_content = await self._extract_filing_content(filing_info)
                    if filing_content:
                        pipeline_info = self._extract_pipeline_from_content(filing_content, filing_info)
                        extracted_filings.append(SECFiling(
                            company_name=company_name,
                            filing_type=filing_info.get("type", ""),
                            filing_date=filing_info.get("date", ""),
                            accession_number=filing_info.get("accession", ""),
                            document_url=filing_info.get("url", ""),
                            content=filing_content,
                            extracted_pipeline_info=pipeline_info,
                            confidence_score=self._calculate_filing_confidence(pipeline_info)
                        ))
                        logger.info(f"✅ Extracted pipeline info from {filing_info.get('type', '')} filing")
                except Exception as e:
                    logger.error(f"Error extracting content from filing {filing_info.get('accession', '')}: {e}")
                    continue
            
            logger.info(f"Successfully extracted pipeline info from {len(extracted_filings)} filings")
            return extracted_filings
            
        except Exception as e:
            logger.error(f"Error extracting pipeline from SEC filings for {company_name}: {e}")
            return []
    
    async def _search_company_filings(self, company_name: str, max_filings: int) -> List[Dict[str, Any]]:
        """Search for company SEC filings."""
        try:
            # Construct search parameters
            params = {
                "action": "getcompany",
                "CIK": self._get_company_cik(company_name),
                "type": "&".join([f"type={ft}" for ft in self.filing_types]),
                "dateb": "",  # No date restriction
                "owner": "exclude",
                "count": str(max_filings)
            }
            
            # Make request to SEC EDGAR
            response = await self._make_async_request(self.edgar_search_url, params)
            
            if response and response.status_code == 200:
                return self._parse_filing_search_results(response.text, company_name)
            else:
                logger.warning(f"SEC search failed for {company_name}: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching SEC filings for {company_name}: {e}")
            return []
    
    def _get_company_cik(self, company_name: str) -> str:
        """Get company CIK (Central Index Key) from SEC."""
        # Simplified mapping - in production, this would query SEC's company database
        cik_mapping = {
            "roche": "0000320864",
            "genentech": "0000320864",
            "abbvie": "0001551152",
            "amgen": "0000318154",
            "merck": "0000310158",
            "pfizer": "0000078003",
            "novartis": "0001114448",
            "gilead": "0000882095",
            "regeneron": "0000872589",
            "biogen": "0000875045",
            "moderna": "0001682852",
            "biontech": "0001776985",
            "daiichi sankyo": "0001507909",
            "bayer": "0000011034",
            "janssen": "000200406",
            "johnson & johnson": "000200406"
        }
        
        company_lower = company_name.lower()
        for key, cik in cik_mapping.items():
            if key in company_lower:
                return cik
        
        # Default fallback - would need to implement proper CIK lookup
        logger.warning(f"No CIK mapping found for {company_name}")
        return "0000000000"
    
    def _parse_filing_search_results(self, html_content: str, company_name: str) -> List[Dict[str, Any]]:
        """Parse SEC filing search results."""
        filings = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find filing table
            filing_table = soup.find('table', {'class': 'tableFile'})
            if not filing_table:
                logger.warning("No filing table found in SEC search results")
                return []
            
            # Parse filing rows
            rows = filing_table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    try:
                        filing_type = cells[0].get_text(strip=True)
                        filing_date = cells[3].get_text(strip=True)
                        
                        # Find document link
                        doc_link = cells[1].find('a')
                        if doc_link:
                            accession_number = doc_link.get_text(strip=True)
                            filing_url = f"{self.sec_base_url}{doc_link.get('href', '')}"
                            
                            filings.append({
                                "type": filing_type,
                                "date": filing_date,
                                "accession": accession_number,
                                "url": filing_url
                            })
                    except Exception as e:
                        logger.warning(f"Error parsing filing row: {e}")
                        continue
            
            logger.info(f"Found {len(filings)} SEC filings for {company_name}")
            return filings
            
        except Exception as e:
            logger.error(f"Error parsing SEC filing search results: {e}")
            return []
    
    async def _extract_filing_content(self, filing_info: Dict[str, Any]) -> Optional[str]:
        """Extract content from SEC filing document."""
        try:
            filing_url = filing_info.get("url", "")
            if not filing_url:
                return None
            
            # Use crawl4ai to extract content
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=filing_url,
                    word_count_threshold=100,
                    extraction_strategy="NoExtractionStrategy",
                    bypass_cache=True,
                    delay_between_requests=1.0
                )
                
                if result.success and result.cleaned_html:
                    # Extract text content
                    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
                    
                    # Remove unwanted elements
                    for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                        element.decompose()
                    
                    content = soup.get_text(separator=' ', strip=True)
                    
                    # Filter for pipeline-related content
                    pipeline_content = self._filter_pipeline_content(content)
                    
                    return pipeline_content
                else:
                    logger.warning(f"Failed to extract content from {filing_url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error extracting filing content: {e}")
            return None
    
    def _filter_pipeline_content(self, content: str) -> str:
        """Filter content to focus on pipeline-related information."""
        try:
            # Split content into paragraphs
            paragraphs = content.split('\n\n')
            
            pipeline_paragraphs = []
            for para in paragraphs:
                para_lower = para.lower()
                # Check if paragraph contains pipeline-related keywords
                if any(keyword in para_lower for keyword in self.pipeline_keywords):
                    pipeline_paragraphs.append(para)
            
            # Join relevant paragraphs
            filtered_content = '\n\n'.join(pipeline_paragraphs)
            
            # Limit content length to avoid overwhelming processing
            if len(filtered_content) > 50000:
                filtered_content = filtered_content[:50000] + "..."
            
            return filtered_content
            
        except Exception as e:
            logger.error(f"Error filtering pipeline content: {e}")
            return content[:10000]  # Return first 10k characters as fallback
    
    def _extract_pipeline_from_content(self, content: str, filing_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract pipeline information from filing content."""
        pipeline_info = []
        
        try:
            # Extract drug names using patterns
            drug_names = self._extract_drug_names(content)
            
            # Extract development stages
            development_stages = self._extract_development_stages(content)
            
            # Extract indications
            indications = self._extract_indications(content)
            
            # Extract targets and mechanisms
            targets = self._extract_targets(content)
            
            # Combine information
            for drug in drug_names:
                pipeline_entry = {
                    "drug_name": drug,
                    "development_stage": self._find_associated_stage(drug, development_stages, content),
                    "indication": self._find_associated_indication(drug, indications, content),
                    "target": self._find_associated_target(drug, targets, content),
                    "mechanism_of_action": self._extract_mechanism_of_action(drug, content),
                    "phase": self._extract_phase(drug, content),
                    "status": self._extract_status(drug, content),
                    "source_filing": filing_info.get("accession", ""),
                    "extraction_confidence": self._calculate_extraction_confidence(drug, content)
                }
                pipeline_info.append(pipeline_entry)
            
            return pipeline_info
            
        except Exception as e:
            logger.error(f"Error extracting pipeline from content: {e}")
            return []
    
    def _extract_drug_names(self, content: str) -> List[str]:
        """Extract drug names from content using NLP and patterns."""
        drug_names = set()
        
        try:
            if self.nlp:
                # Use spaCy for entity recognition
                doc = self.nlp(content)
                
                # Look for drug-related entities
                for ent in doc.ents:
                    if self._is_drug_entity(ent):
                        drug_names.add(ent.text.strip())
            
            # Fallback to pattern matching
            drug_patterns = [
                r'\b[A-Z][a-z]+mab\b',  # Monoclonal antibodies
                r'\b[A-Z][a-z]+nib\b',  # Kinase inhibitors
                r'\b[A-Z][a-z]+tinib\b',  # Tyrosine kinase inhibitors
                r'\b[A-Z][a-z]+zumab\b',  # Humanized antibodies
                r'\b[A-Z][a-z]+ciclib\b',  # CDK inhibitors
                r'\b[A-Z][a-z]+parib\b',  # PARP inhibitors
                r'\b[A-Z][a-z]+mig\b',    # Bispecific antibodies
                r'\b[A-Z][a-z]+vedotin\b',  # ADCs
                r'\b[A-Z][a-z]+deruxtecan\b',  # ADCs
                r'\b[A-Z][a-z]+emtansine\b',   # ADCs
            ]
            
            for pattern in drug_patterns:
                matches = re.findall(pattern, content)
                drug_names.update(matches)
            
            # Filter and clean drug names
            cleaned_drugs = []
            for drug in drug_names:
                if self._validate_drug_name(drug):
                    cleaned_drugs.append(drug)
            
            return cleaned_drugs[:20]  # Limit to top 20 drugs
            
        except Exception as e:
            logger.error(f"Error extracting drug names: {e}")
            return []
    
    def _is_drug_entity(self, entity) -> bool:
        """Check if spaCy entity is likely a drug."""
        # Check for drug-related labels and patterns
        drug_indicators = ['mab', 'nib', 'tinib', 'zumab', 'ciclib', 'parib', 'mig']
        return any(indicator in entity.text.lower() for indicator in drug_indicators)
    
    def _validate_drug_name(self, name: str) -> bool:
        """Validate if a name is likely a drug."""
        if len(name) < 3 or len(name) > 50:
            return False
        
        # Check for drug suffixes
        drug_suffixes = ['mab', 'nib', 'tinib', 'zumab', 'ciclib', 'parib', 'mig', 'vedotin', 'deruxtecan', 'emtansine']
        return any(name.lower().endswith(suffix) for suffix in drug_suffixes)
    
    def _extract_development_stages(self, content: str) -> List[str]:
        """Extract development stages from content."""
        stages = []
        
        stage_patterns = [
            r'phase\s+[I1-3]', r'phase\s+II', r'phase\s+III', r'phase\s+IV',
            r'preclinical', r'clinical', r'IND', r'NDA', r'BLA',
            r'fast\s+track', r'breakthrough\s+therapy', r'orphan\s+drug'
        ]
        
        for pattern in stage_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            stages.extend(matches)
        
        return list(set(stages))
    
    def _extract_indications(self, content: str) -> List[str]:
        """Extract indications from content."""
        indications = []
        
        # Common cancer indications
        cancer_types = [
            'breast cancer', 'lung cancer', 'prostate cancer', 'colorectal cancer',
            'melanoma', 'lymphoma', 'leukemia', 'ovarian cancer', 'pancreatic cancer',
            'hepatocellular carcinoma', 'renal cell carcinoma', 'bladder cancer',
            'non-small cell lung cancer', 'small cell lung cancer', 'triple negative breast cancer'
        ]
        
        content_lower = content.lower()
        for cancer in cancer_types:
            if cancer in content_lower:
                indications.append(cancer)
        
        return indications
    
    def _extract_targets(self, content: str) -> List[str]:
        """Extract drug targets from content."""
        targets = []
        
        # Common drug targets
        common_targets = [
            'EGFR', 'HER2', 'PD1', 'PDL1', 'CTLA4', 'VEGF', 'BRAF', 'MEK', 'PI3K',
            'AKT', 'mTOR', 'CDK', 'PARP', 'ALK', 'ROS1', 'MET', 'FGFR', 'RET'
        ]
        
        content_upper = content.upper()
        for target in common_targets:
            if target in content_upper:
                targets.append(target)
        
        return targets
    
    def _find_associated_stage(self, drug: str, stages: List[str], content: str) -> Optional[str]:
        """Find development stage associated with a drug."""
        # Look for drug name near stage mentions
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            # Look for stages within 200 characters
            context_start = max(0, drug_pos - 200)
            context_end = min(len(content), drug_pos + len(drug) + 200)
            context = content[context_start:context_end]
            
            for stage in stages:
                if stage.lower() in context.lower():
                    return stage
        
        return None
    
    def _find_associated_indication(self, drug: str, indications: List[str], content: str) -> Optional[str]:
        """Find indication associated with a drug."""
        # Similar logic to find associated stage
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            context_start = max(0, drug_pos - 300)
            context_end = min(len(content), drug_pos + len(drug) + 300)
            context = content[context_start:context_end]
            
            for indication in indications:
                if indication.lower() in context.lower():
                    return indication
        
        return None
    
    def _find_associated_target(self, drug: str, targets: List[str], content: str) -> Optional[str]:
        """Find target associated with a drug."""
        # Similar logic to find associated stage
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            context_start = max(0, drug_pos - 200)
            context_end = min(len(content), drug_pos + len(drug) + 200)
            context = content[context_start:context_end]
            
            for target in targets:
                if target in context.upper():
                    return target
        
        return None
    
    def _extract_mechanism_of_action(self, drug: str, content: str) -> Optional[str]:
        """Extract mechanism of action for a drug."""
        # Look for mechanism-related text near drug mentions
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            context_start = max(0, drug_pos - 500)
            context_end = min(len(content), drug_pos + len(drug) + 500)
            context = content[context_start:context_end]
            
            # Look for mechanism keywords
            mechanism_keywords = ['inhibits', 'targets', 'blocks', 'binds to', 'activates', 'modulates']
            for keyword in mechanism_keywords:
                if keyword in context.lower():
                    # Extract sentence containing the mechanism
                    sentences = context.split('.')
                    for sentence in sentences:
                        if keyword in sentence.lower() and drug.lower() in sentence.lower():
                            return sentence.strip()
        
        return None
    
    def _extract_phase(self, drug: str, content: str) -> Optional[str]:
        """Extract clinical phase for a drug."""
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            context_start = max(0, drug_pos - 100)
            context_end = min(len(content), drug_pos + len(drug) + 100)
            context = content[context_start:context_end]
            
            phase_patterns = [
                r'phase\s+[I1]', r'phase\s+II', r'phase\s+III', r'phase\s+IV',
                r'phase\s+1', r'phase\s+2', r'phase\s+3', r'phase\s+4'
            ]
            
            for pattern in phase_patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    return match.group(0)
        
        return None
    
    def _extract_status(self, drug: str, content: str) -> str:
        """Extract development status for a drug."""
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        
        for drug_pos in drug_positions:
            context_start = max(0, drug_pos - 200)
            context_end = min(len(content), drug_pos + len(drug) + 200)
            context = content[context_start:context_end].lower()
            
            if any(word in context for word in ['recruiting', 'enrolling', 'active']):
                return 'Active'
            elif any(word in context for word in ['completed', 'finished']):
                return 'Completed'
            elif any(word in context for word in ['discontinued', 'terminated']):
                return 'Discontinued'
            elif any(word in context for word in ['planned', 'upcoming']):
                return 'Planned'
        
        return 'Unknown'
    
    def _calculate_extraction_confidence(self, drug: str, content: str) -> float:
        """Calculate confidence score for extracted pipeline information."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for known drug patterns
        if any(suffix in drug.lower() for suffix in ['mab', 'nib', 'tinib']):
            confidence += 0.2
        
        # Boost confidence based on context richness
        drug_positions = [m.start() for m in re.finditer(re.escape(drug), content, re.IGNORECASE)]
        if len(drug_positions) > 1:
            confidence += 0.1
        
        # Boost confidence if drug appears near pipeline keywords
        for pos in drug_positions:
            context_start = max(0, pos - 100)
            context_end = min(len(content), pos + len(drug) + 100)
            context = content[context_start:context_end].lower()
            
            if any(keyword in context for keyword in self.pipeline_keywords):
                confidence += 0.1
                break
        
        return min(1.0, confidence)
    
    def _calculate_filing_confidence(self, pipeline_info: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence score for filing extraction."""
        if not pipeline_info:
            return 0.0
        
        # Average confidence of extracted pipeline entries
        total_confidence = sum(entry.get('extraction_confidence', 0.0) for entry in pipeline_info)
        avg_confidence = total_confidence / len(pipeline_info)
        
        # Boost confidence based on number of extracted entries
        quantity_bonus = min(0.2, len(pipeline_info) * 0.05)
        
        return min(1.0, avg_confidence + quantity_bonus)
    
    async def _make_async_request(self, url: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        """Make asynchronous HTTP request."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, params=params, timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; SEC Filing Extractor)'
                })
            )
            return response
        except Exception as e:
            logger.error(f"Error making async request to {url}: {e}")
            return None

