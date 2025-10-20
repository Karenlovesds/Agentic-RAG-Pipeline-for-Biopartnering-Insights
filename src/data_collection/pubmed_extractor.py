"""PubMed API extractor for drug targets and indications from scientific literature."""

import asyncio
import re
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from loguru import logger
import spacy
from bs4 import BeautifulSoup
from .utils import DataCollectionUtils, DrugTarget
from .config import APIConfig


@dataclass
class PubMedArticle:
    """Data class for PubMed article information."""
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: str
    publication_date: str
    mesh_terms: List[str]
    keywords: List[str]
    drug_mentions: List[str]
    target_mentions: List[str]
    indication_mentions: List[str]


@dataclass
class DrugTargetInfo:
    """Data class for drug target information from PubMed."""
    drug_name: str
    target_name: str
    target_type: str
    mechanism_of_action: str
    confidence_score: float
    source_pmid: str
    source_title: str
    evidence_text: str


@dataclass
class DrugIndicationInfo:
    """Data class for drug indication information from PubMed."""
    drug_name: str
    indication: str
    approval_status: str
    evidence_type: str
    confidence_score: float
    source_pmid: str
    source_title: str
    evidence_text: str


class PubMedExtractor:
    """Extract drug targets and indications from PubMed scientific literature."""
    
    def __init__(self):
        self.base_url = APIConfig.PUBMED_BASE_URL
        self.search_url = f"{self.base_url}/esearch.fcgi"
        self.fetch_url = f"{self.base_url}/efetch.fcgi"
        
        # Initialize NLP model for scientific text processing
        try:
            self.nlp = spacy.load("en_core_sci_sm")
        except OSError:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not available, using basic text processing")
                self.nlp = None
        
        # Common drug targets for validation
        self.known_targets = [
            'EGFR', 'HER2', 'PD1', 'PDL1', 'CTLA4', 'VEGF', 'BRAF', 'MEK', 'PI3K',
            'AKT', 'mTOR', 'CDK', 'PARP', 'ALK', 'ROS1', 'MET', 'FGFR', 'RET',
            'KRAS', 'TP53', 'MYC', 'BCL2', 'MDM2', 'STAT3', 'JAK2', 'FLT3'
        ]
        
        # Common indications for validation
        self.known_indications = [
            'breast cancer', 'lung cancer', 'prostate cancer', 'colorectal cancer',
            'melanoma', 'lymphoma', 'leukemia', 'ovarian cancer', 'pancreatic cancer',
            'hepatocellular carcinoma', 'renal cell carcinoma', 'bladder cancer',
            'non-small cell lung cancer', 'small cell lung cancer', 'triple negative breast cancer',
            'acute myeloid leukemia', 'chronic lymphocytic leukemia', 'multiple myeloma'
        ]
        
        # Company name mappings for PubMed search
        # Use configuration for company search terms
        self.company_search_terms = APIConfig.COMPANY_SEARCH_TERMS
    
    def _get_company_search_terms(self, company_name: str) -> List[str]:
        """Get search terms for a company name."""
        return APIConfig.get_company_search_terms(company_name)
    
    async def extract_drug_targets(
        self, 
        drug_name: str, 
        max_articles: int = 20, 
        company_name: str = None
    ) -> List[DrugTargetInfo]:
        """Extract drug targets from PubMed literature, optionally filtered by company."""
        company_info = f" (company: {company_name})" if company_name else ""
        logger.info(f"Extracting drug targets for {drug_name} from PubMed{company_info}")
        
        try:
            # 1. Search for articles about the drug
            articles = await self._search_drug_articles(drug_name, max_articles, company_name)
            
            if not articles:
                logger.warning(f"No PubMed articles found for {drug_name}")
                return []
            
            # 2. Extract target information from articles
            target_info = []
            for article in articles:
                try:
                    targets = self._extract_targets_from_article(article, drug_name)
                    target_info.extend(targets)
                except Exception as e:
                    logger.error(f"Error extracting targets from article {article.pmid}: {e}")
                    continue
            
            # 3. Deduplicate and rank targets
            unique_targets = self._deduplicate_targets(target_info)
            
            logger.info(f"✅ Extracted {len(unique_targets)} unique targets for {drug_name}")
            return unique_targets
            
        except Exception as e:
            logger.error(f"Error extracting drug targets for {drug_name}: {e}")
            return []
    
    async def extract_drug_indications(
        self, 
        drug_name: str, 
        max_articles: int = 20, 
        company_name: str = None
    ) -> List[DrugIndicationInfo]:
        """Extract drug indications from PubMed literature, optionally filtered by company."""
        company_info = f" (company: {company_name})" if company_name else ""
        logger.info(f"Extracting drug indications for {drug_name} from PubMed{company_info}")
        
        try:
            # 1. Search for articles about the drug
            articles = await self._search_drug_articles(drug_name, max_articles, company_name)
            
            if not articles:
                logger.warning(f"No PubMed articles found for {drug_name}")
                return []
            
            # 2. Extract indication information from articles
            indication_info = []
            for article in articles:
                try:
                    indications = self._extract_indications_from_article(article, drug_name)
                    indication_info.extend(indications)
                except Exception as e:
                    logger.error(f"Error extracting indications from article {article.pmid}: {e}")
                    continue
            
            # 3. Deduplicate and rank indications
            unique_indications = self._deduplicate_indications(indication_info)
            
            logger.info(f"✅ Extracted {len(unique_indications)} unique indications for {drug_name}")
            return unique_indications
            
        except Exception as e:
            logger.error(f"Error extracting drug indications for {drug_name}: {e}")
            return []
    
    async def _search_drug_articles(self, drug_name: str, max_articles: int, company_name: str = None) -> List[PubMedArticle]:
        """Search PubMed for articles about a drug, optionally filtered by company."""
        try:
            # Construct search query
            search_query = (
                f'"{drug_name}"[Title/Abstract] AND '
                f'("drug" OR "therapeutic" OR "clinical trial" OR "mechanism")'
            )
            
            # Add company filter if provided
            if company_name:
                company_terms = self._get_company_search_terms(company_name)
                if company_terms:
                    company_query = " OR ".join([f'"{term}"' for term in company_terms])
                    search_query += f' AND ({company_query})'
            
            # Search for article IDs
            search_params = {
                'db': 'pubmed',
                'term': search_query,
                'retmax': str(max_articles),
                'retmode': 'xml',
                'sort': 'relevance'
            }
            
            search_response = await self._make_async_request(self.search_url, search_params)
            
            if not search_response or search_response.status_code != 200:
                logger.error(f"PubMed search failed for {drug_name}")
                return []
            
            # Parse search results to get PMIDs
            pmids = self._parse_search_results(search_response.text)
            
            if not pmids:
                logger.warning(f"No PMIDs found for {drug_name}")
                return []
            
            # Fetch article details
            articles = await self._fetch_article_details(pmids)
            
            return articles
            
        except Exception as e:
            logger.error(f"Error searching PubMed for {drug_name}: {e}")
            return []
    
    def _parse_search_results(self, xml_content: str) -> List[str]:
        """Parse PubMed search results to extract PMIDs."""
        pmids = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find all IdList elements
            for id_elem in root.findall('.//IdList/Id'):
                if id_elem.text:
                    pmids.append(id_elem.text)
            
        except ET.ParseError as e:
            logger.error(f"Error parsing PubMed search XML: {e}")
        
        return pmids
    
    async def _fetch_article_details(self, pmids: List[str]) -> List[PubMedArticle]:
        """Fetch detailed information for PubMed articles."""
        articles = []
        
        try:
            # Fetch article details in batches
            batch_size = 10
            for i in range(0, len(pmids), batch_size):
                batch_pmids = pmids[i:i + batch_size]
                
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(batch_pmids),
                    'retmode': 'xml',
                    'rettype': 'abstract'
                }
                
                fetch_response = await self._make_async_request(self.fetch_url, fetch_params)
                
                if fetch_response and fetch_response.status_code == 200:
                    batch_articles = self._parse_article_details(fetch_response.text)
                    articles.extend(batch_articles)
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error fetching article details: {e}")
        
        return articles
    
    def _parse_article_details(self, xml_content: str) -> List[PubMedArticle]:
        """Parse PubMed article details from XML."""
        articles = []
        
        try:
            root = ET.fromstring(xml_content)
            
            for article_elem in root.findall('.//PubmedArticle'):
                article = self._process_single_article(article_elem)
                if article:
                    articles.append(article)
                    
        except ET.ParseError as e:
            logger.error(f"Error parsing PubMed article XML: {e}")
        
        return articles
    
    def _process_single_article(self, article_elem) -> Optional[PubMedArticle]:
        """Process a single PubMed article element."""
        try:
            # Extract basic information
            pmid = self._extract_text(article_elem, './/PMID')
            title = self._extract_text(article_elem, './/ArticleTitle')
            abstract = self._extract_text(article_elem, './/AbstractText')
            
            if not pmid or not title:
                return None
            
            # Extract additional information
            authors = self._extract_authors(article_elem)
            journal = self._extract_text(article_elem, './/Journal/Title')
            pub_date = self._extract_publication_date(article_elem)
            mesh_terms = self._extract_mesh_terms(article_elem)
            keywords = self._extract_keywords(article_elem)
            
            return PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract or "",
                authors=authors,
                journal=journal or "",
                publication_date=pub_date,
                mesh_terms=mesh_terms,
                keywords=keywords,
                drug_mentions=[],
                target_mentions=[],
                indication_mentions=[]
            )
            
        except Exception as e:
            logger.warning(f"Error parsing article: {e}")
            return None
    
    def _extract_authors(self, article_elem) -> List[str]:
        """Extract authors from article element."""
        authors = []
        for author_elem in article_elem.findall('.//Author'):
            last_name = self._extract_text(author_elem, './/LastName')
            first_name = self._extract_text(author_elem, './/ForeName')
            if last_name and first_name:
                authors.append(f"{first_name} {last_name}")
        return authors
    
    def _extract_mesh_terms(self, article_elem) -> List[str]:
        """Extract MeSH terms from article element."""
        mesh_terms = []
        for mesh_elem in article_elem.findall('.//MeshHeading/DescriptorName'):
            if mesh_elem.text:
                mesh_terms.append(mesh_elem.text)
        return mesh_terms
    
    def _extract_keywords(self, article_elem) -> List[str]:
        """Extract keywords from article element."""
        keywords = []
        for keyword_elem in article_elem.findall('.//Keyword'):
            if keyword_elem.text:
                keywords.append(keyword_elem.text)
        return keywords
    
    def _extract_text(self, element, xpath: str) -> Optional[str]:
        """Extract text content from XML element."""
        try:
            found = element.find(xpath)
            return found.text.strip() if found is not None and found.text else None
        except Exception:
            return None
    
    def _extract_publication_date(self, article_elem) -> str:
        """Extract publication date from article element."""
        try:
            # Try to get publication date
            pub_date_elem = article_elem.find('.//PubDate')
            if pub_date_elem is not None:
                year = self._extract_text(pub_date_elem, './/Year')
                month = self._extract_text(pub_date_elem, './/Month')
                day = self._extract_text(pub_date_elem, './/Day')
                
                if year:
                    date_parts = [year]
                    if month:
                        date_parts.append(month)
                    if day:
                        date_parts.append(day)
                    return '-'.join(date_parts)
            
            return ""
        except Exception:
            return ""
    
    def _extract_targets_from_article(self, article: PubMedArticle, drug_name: str) -> List[DrugTargetInfo]:
        """Extract drug targets from a PubMed article."""
        targets = []
        
        try:
            # Combine title and abstract for analysis
            text_content = f"{article.title} {article.abstract}".lower()
            drug_lower = drug_name.lower()
            
            # Look for target mentions near drug mentions
            drug_positions = [m.start() for m in re.finditer(re.escape(drug_lower), text_content)]
            
            for drug_pos in drug_positions:
                # Look for targets within 300 characters
                context_start = max(0, drug_pos - 300)
                context_end = min(len(text_content), drug_pos + len(drug_name) + 300)
                context = text_content[context_start:context_end]
                
                # Extract targets from context
                context_targets = self._extract_targets_from_text(context)
                
                for target in context_targets:
                    confidence = self._calculate_target_confidence(target, context, drug_name)
                    if confidence > 0.3:  # Filter low confidence matches
                        targets.append(DrugTargetInfo(
                            drug_name=drug_name,
                            target_name=target,
                            target_type=self._classify_target_type(target),
                            mechanism_of_action=self._extract_mechanism_from_context(context),
                            confidence_score=confidence,
                            source_pmid=article.pmid,
                            source_title=article.title,
                            evidence_text=context[:500] + "..." if len(context) > 500 else context
                        ))
            
            return targets
            
        except Exception as e:
            logger.error(f"Error extracting targets from article {article.pmid}: {e}")
            return []
    
    def _extract_targets_from_text(self, text: str) -> List[str]:
        """Extract potential drug targets from text using consolidated extractor."""
        from .utils import target_extractor
        return target_extractor.extract_targets_simple(text)
    
    def _is_target_entity(self, entity) -> bool:
        """Check if spaCy entity is likely a drug target."""
        # Check for protein/gene patterns
        text = entity.text.upper()
        return (text in self.known_targets or 
                text.endswith('ASE') or 
                text.endswith('IN') or
                (len(text) <= 6 and text.isalpha()))
    
    def _extract_indications_from_article(self, article: PubMedArticle, drug_name: str) -> List[DrugIndicationInfo]:
        """Extract drug indications from a PubMed article."""
        indications = []
        
        try:
            # Combine title and abstract for analysis
            text_content = f"{article.title} {article.abstract}".lower()
            drug_lower = drug_name.lower()
            
            # Look for indication mentions near drug mentions
            drug_positions = [m.start() for m in re.finditer(re.escape(drug_lower), text_content)]
            
            for drug_pos in drug_positions:
                # Look for indications within 400 characters
                context_start = max(0, drug_pos - 400)
                context_end = min(len(text_content), drug_pos + len(drug_name) + 400)
                context = text_content[context_start:context_end]
                
                # Extract indications from context
                context_indications = self._extract_indications_from_text(context)
                
                for indication in context_indications:
                    confidence = self._calculate_indication_confidence(indication, context, drug_name)
                    if confidence > 0.3:  # Filter low confidence matches
                        indications.append(DrugIndicationInfo(
                            drug_name=drug_name,
                            indication=indication,
                            approval_status=self._determine_approval_status(context),
                            evidence_type=self._classify_evidence_type(context),
                            confidence_score=confidence,
                            source_pmid=article.pmid,
                            source_title=article.title,
                            evidence_text=context[:500] + "..." if len(context) > 500 else context
                        ))
            
            return indications
            
        except Exception as e:
            logger.error(f"Error extracting indications from article {article.pmid}: {e}")
            return []
    
    def _extract_indications_from_text(self, text: str) -> List[str]:
        """Extract potential drug indications from text."""
        indications = []
        
        # Look for known indications
        text_lower = text.lower()
        for indication in self.known_indications:
            if indication in text_lower:
                indications.append(indication)
        
        # Use NLP to find additional indications
        if self.nlp:
            try:
                doc = self.nlp(text)
                
                # Look for disease mentions
                for ent in doc.ents:
                    if self._is_indication_entity(ent):
                        indications.append(ent.text.lower())
            
            except Exception as e:
                logger.warning(f"Error in NLP indication extraction: {e}")
        
        return list(set(indications))  # Remove duplicates
    
    def _is_indication_entity(self, entity) -> bool:
        """Check if spaCy entity is likely a disease/indication."""
        # Check for disease patterns
        text = entity.text.lower()
        return (text in self.known_indications or 
                'cancer' in text or 
                'tumor' in text or
                'syndrome' in text or
                'disease' in text)
    
    def _calculate_target_confidence(self, target: str, context: str, drug_name: str) -> float:
        """Calculate confidence score for extracted target."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for known targets
        if target.upper() in self.known_targets:
            confidence += 0.3
        
        # Boost confidence based on context
        target_context_words = ['inhibits', 'targets', 'blocks', 'binds to', 'activates', 'modulates']
        context_lower = context.lower()
        for word in target_context_words:
            if word in context_lower:
                confidence += 0.1
        
        # Boost confidence if target appears near drug
        drug_pos = context.lower().find(drug_name.lower())
        target_pos = context.upper().find(target.upper())
        if drug_pos != -1 and target_pos != -1:
            distance = abs(drug_pos - target_pos)
            if distance < 200:
                confidence += 0.1
        
        return min(1.0, confidence)
    
    def _calculate_indication_confidence(self, indication: str, context: str, drug_name: str) -> float:
        """Calculate confidence score for extracted indication."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for known indications
        if indication.lower() in self.known_indications:
            confidence += 0.3
        
        # Boost confidence based on context
        indication_context_words = ['treats', 'therapy', 'treatment', 'indicated for', 'approved for']
        context_lower = context.lower()
        for word in indication_context_words:
            if word in context_lower:
                confidence += 0.1
        
        # Boost confidence if indication appears near drug
        drug_pos = context.lower().find(drug_name.lower())
        indication_pos = context.lower().find(indication.lower())
        if drug_pos != -1 and indication_pos != -1:
            distance = abs(drug_pos - indication_pos)
            if distance < 300:
                confidence += 0.1
        
        return min(1.0, confidence)
    
    def _classify_target_type(self, target: str) -> str:
        """Classify the type of drug target."""
        target_upper = target.upper()
        
        if target_upper.endswith('ASE'):
            return "Enzyme"
        elif target_upper.endswith('IN'):
            return "Protein"
        elif len(target_upper) <= 6 and target_upper.isalpha():
            return "Gene/Protein"
        else:
            return "Unknown"
    
    def _determine_approval_status(self, context: str) -> str:
        """Determine approval status from context."""
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['approved', 'fda approved', 'ema approved']):
            return "Approved"
        elif any(word in context_lower for word in ['clinical trial', 'phase', 'study']):
            return "Clinical Trial"
        elif any(word in context_lower for word in ['preclinical', 'in vitro', 'in vivo']):
            return "Preclinical"
        else:
            return "Unknown"
    
    def _classify_evidence_type(self, context: str) -> str:
        """Classify the type of evidence."""
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['clinical trial', 'randomized', 'phase']):
            return "Clinical Trial"
        elif any(word in context_lower for word in ['case study', 'case report']):
            return "Case Study"
        elif any(word in context_lower for word in ['review', 'meta-analysis']):
            return "Review"
        else:
            return "Research"
    
    def _extract_mechanism_from_context(self, context: str) -> str:
        """Extract mechanism of action from context."""
        # Look for mechanism-related text
        mechanism_keywords = ['inhibits', 'targets', 'blocks', 'binds to', 'activates', 'modulates']
        
        for keyword in mechanism_keywords:
            if keyword in context.lower():
                # Extract sentence containing the mechanism
                sentences = context.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        return sentence.strip()
        
        return context[:200] + "..." if len(context) > 200 else context
    
    def _deduplicate_targets(self, targets: List[DrugTargetInfo]) -> List[DrugTargetInfo]:
        """Remove duplicate targets and sort by confidence."""
        # Convert to DrugTarget format for utility function
        drug_targets = []
        for target in targets:
            drug_targets.append(DrugTarget(
                target_name=target.target_name,
                target_type=target.target_type,
                mechanism_of_action=target.mechanism_of_action,
                confidence_score=target.confidence_score,
                source=target.source
            ))
        
        # Use shared utility
        unique_targets = DataCollectionUtils.deduplicate_targets(drug_targets)
        
        # Convert back to DrugTargetInfo format
        result = []
        for target in unique_targets:
            result.append(DrugTargetInfo(
                drug_name=targets[0].drug_name if targets else "",
                target_name=target.target_name,
                target_type=target.target_type,
                mechanism_of_action=target.mechanism_of_action,
                confidence_score=target.confidence_score,
                source=target.source
            ))
        
        # Sort by confidence score
        result.sort(key=lambda x: x.confidence_score, reverse=True)
        return result[:15]  # Return top 15 targets
    
    def _deduplicate_indications(self, indications: List[DrugIndicationInfo]) -> List[DrugIndicationInfo]:
        """Remove duplicate indications and sort by confidence."""
        seen = set()
        unique_indications = []
        
        for indication in indications:
            key = (indication.drug_name, indication.indication)
            if key not in seen:
                seen.add(key)
                unique_indications.append(indication)
        
        # Sort by confidence score
        unique_indications.sort(key=lambda x: x.confidence_score, reverse=True)
        return unique_indications[:15]  # Return top 15 indications
    
    async def _make_async_request(self, url: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        """Make asynchronous HTTP request."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, params=params, timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; PubMed Extractor)'
                })
            )
            return response
        except Exception as e:
            logger.error(f"Error making async request to {url}: {e}")
            return None

