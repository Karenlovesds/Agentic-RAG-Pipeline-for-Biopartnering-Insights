"""Shared utility functions for data collection modules."""

import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import re
import requests
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from loguru import logger

from ..models.entities import Document
from ..models.database import get_db

logger = logging.getLogger(__name__)


class CollectedData(BaseModel):
    """Model for collected data."""
    source_url: str
    title: Optional[str] = None
    content: str
    source_type: str
    metadata: Dict[str, Any] = {}


class BaseCollector(ABC):
    """Base class for data collectors."""
    
    def __init__(self, source_type: str, base_url: str):
        self.source_type = source_type
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BiopartneringInsights/1.0)'
        })
        
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _save_document(self, data: CollectedData) -> bool:
        """Save collected document to database."""
        try:
            db = get_db()
            content_hash = self._generate_content_hash(data.content)
            
            # Check if document already exists
            existing_doc = db.query(Document).filter(
                Document.content_hash == content_hash
            ).first()
            
            if existing_doc:
                logger.info(f"Document already exists: {data.source_url}")
                return False
            
            # Create new document
            document = Document(
                source_url=data.source_url,
                title=data.title,
                content=data.content,
                content_hash=content_hash,
                source_type=data.source_type,
                retrieval_date=datetime.utcnow()
            )
            
            db.add(document)
            db.commit()
            logger.info(f"Saved document: {data.source_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving document {data.source_url}: {e}")
            return False
        finally:
            db.close()
    
    async def _crawl_with_crawl4ai(self, url: str, extraction_strategy: Optional[LLMExtractionStrategy] = None) -> Optional[str]:
        """Crawl URL using crawl4ai."""
        try:
            async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy(), verbose=True) as crawler:
                result = await crawler.arun(
                    url=url,
                    extraction_strategy=extraction_strategy,
                    bypass_cache=True
                )
                
                if result.success:
                    return result.cleaned_html or result.html
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make HTTP request with error handling."""
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    @abstractmethod
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect data from the source. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into structured format. Must be implemented by subclasses."""
        pass
    
    async def run_collection(self, query_params: Optional[Dict[str, Any]] = None) -> int:
        """Run the complete data collection process."""
        logger.info(f"Starting data collection from {self.source_type}")
        
        try:
            # Collect data
            collected_data = await self.collect_data(query_params)
            logger.info(f"Collected {len(collected_data)} items from {self.source_type}")
            
            # Save to database
            saved_count = 0
            for data in collected_data:
                if self._save_document(data):
                    saved_count += 1
                
                # Rate limiting
                time.sleep(1.0)  # 1 second delay between requests
            
            logger.info(f"Saved {saved_count} new documents from {self.source_type}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error in data collection from {self.source_type}: {e}")
            return 0


@dataclass
class DrugTarget:
    """Data class for drug target information."""
    target_name: str
    target_type: str
    mechanism_of_action: str
    confidence_score: float
    source: str


@dataclass
class DrugIndication:
    """Data class for drug indication information."""
    indication: str
    status: str
    confidence_score: float
    source: str


class DataCollectionUtils:
    """Utility class for common data collection operations."""
    
    @staticmethod
    def deduplicate_targets(targets: List[DrugTarget]) -> List[DrugTarget]:
        """Remove duplicate targets based on target name and type."""
        seen = set()
        unique_targets = []
        
        for target in targets:
            key = (target.target_name.lower(), target.target_type.lower())
            if key not in seen:
                seen.add(key)
                unique_targets.append(target)
            else:
                # Update confidence score if this target has higher confidence
                for existing_target in unique_targets:
                    if (existing_target.target_name.lower() == target.target_name.lower() and
                        existing_target.target_type.lower() == target.target_type.lower()):
                        if target.confidence_score > existing_target.confidence_score:
                            existing_target.confidence_score = target.confidence_score
                            existing_target.mechanism_of_action = target.mechanism_of_action
                            existing_target.source = target.source
                        break
        
        return unique_targets
    
    @staticmethod
    def deduplicate_indications(indications: List[DrugIndication]) -> List[DrugIndication]:
        """Remove duplicate indications based on indication name."""
        seen = set()
        unique_indications = []
        
        for indication in indications:
            key = indication.indication.lower()
            if key not in seen:
                seen.add(key)
                unique_indications.append(indication)
            else:
                # Update confidence score if this indication has higher confidence
                for existing_indication in unique_indications:
                    if existing_indication.indication.lower() == indication.indication.lower():
                        if indication.confidence_score > existing_indication.confidence_score:
                            existing_indication.confidence_score = indication.confidence_score
                            existing_indication.status = indication.status
                            existing_indication.source = indication.source
                        break
        
        return unique_indications
    
    @staticmethod
    def parse_data(data: Any) -> Dict[str, Any]:
        """Parse data into a standardized format."""
        if data is None:
            return {}
        
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            try:
                import json
                return json.loads(data)
            except (json.JSONDecodeError, ValueError):
                return {"raw_data": data}
        
        if isinstance(data, list):
            return {"items": data}
        
        return {"raw_data": str(data)}
    
    @staticmethod
    def calculate_confidence_score(
        factors: List[float], 
        weights: List[float] = None
    ) -> float:
        """Calculate weighted confidence score from multiple factors."""
        if not factors:
            return 0.0
        
        if weights is None:
            weights = [1.0] * len(factors)
        
        if len(factors) != len(weights):
            logger.warning("Mismatch between factors and weights length")
            weights = [1.0] * len(factors)
        
        weighted_sum = sum(f * w for f, w in zip(factors, weights))
        total_weight = sum(weights)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        
        return text.strip().lower()
    
    @staticmethod
    def extract_keywords(text: str, keywords: List[str]) -> List[str]:
        """Extract keywords from text."""
        if not text or not keywords:
            return []
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    @staticmethod
    def merge_metadata(
        metadata1: Dict[str, Any], 
        metadata2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two metadata dictionaries."""
        merged = metadata1.copy()
        
        for key, value in metadata2.items():
            if key in merged:
                if isinstance(merged[key], list) and isinstance(value, list):
                    merged[key].extend(value)
                elif isinstance(merged[key], str) and isinstance(value, str):
                    merged[key] = f"{merged[key]}, {value}"
                else:
                    merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    @staticmethod
    def validate_drug_name(drug_name: str) -> bool:
        """Validate drug name format."""
        if not drug_name or not isinstance(drug_name, str):
            return False
        
        # Check for minimum length
        if len(drug_name.strip()) < 2:
            return False
        
        # Check for valid characters (letters, numbers, spaces, hyphens, parentheses)
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-\(\)]+$', drug_name):
            return False
        
        return True
    
    @staticmethod
    def clean_drug_name(drug_name: str) -> str:
        """Clean and normalize drug name."""
        if not drug_name:
            return ""
        
        # Remove extra whitespace
        cleaned = " ".join(drug_name.split())
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = ["drug:", "medication:", "medicine:"]
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned
    
    @staticmethod
    def format_confidence_score(score: float) -> str:
        """Format confidence score for display."""
        if score >= 0.9:
            return "High"
        elif score >= 0.7:
            return "Medium"
        elif score >= 0.5:
            return "Low"
        else:
            return "Very Low"
    
    @staticmethod
    def group_by_company(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by company name."""
        grouped = {}
        
        for item in data:
            company = item.get("company", "Unknown")
            if company not in grouped:
                grouped[company] = []
            grouped[company].append(item)
        
        return grouped
    
    @staticmethod
    def group_by_target(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by target name."""
        grouped = {}
        
        for item in data:
            target = item.get("target", "Unknown")
            if target not in grouped:
                grouped[target] = []
            grouped[target].append(item)
        
        return grouped


class TargetExtractor:
    """Consolidated target extraction utility."""
    
    def __init__(self, nlp_model=None):
        """Initialize the target extractor.
        
        Args:
            nlp_model: Optional spaCy NLP model for advanced extraction
        """
        self.nlp_model = nlp_model
        
        # Known drug targets for validation
        self.known_targets = {
            'EGFR', 'HER2', 'HER3', 'PD-L1', 'PD-1', 'VEGF', 'VEGFR', 'ALK', 'ROS1', 'MET',
            'KRAS', 'BRAF', 'MEK', 'PI3K', 'AKT', 'mTOR', 'CDK4', 'CDK6', 'PARP', 'BCL2',
            'BCL6', 'MYC', 'TP53', 'BRCA1', 'BRCA2', 'TROP2', 'CEA', 'PSMA', 'CD19', 'CD20',
            'CD22', 'CD30', 'CD33', 'CD38', 'CD47', 'CD123', 'FLT3', 'KIT', 'RET', 'FGFR',
            'IGF1R', 'AXL', 'MER', 'TYRO3', 'DLL3', 'NOTCH1', 'WNT', 'HEDGEHOG', 'MTAP',
            'PRMT5', 'MAT2A', 'DHODH', 'IDO1', 'TDO2', 'ARG1', 'ARG2', 'CD73', 'CD39',
            'TIM3', 'LAG3', 'TIGIT', 'CTLA4', 'OX40', '4-1BB', 'GITR', 'ICOS', 'CD27',
            'CD28', 'CD40', 'CD70', 'CD137', 'CD134', 'CD278', 'CD357', 'CD223', 'CD366',
            'CD279', 'CD274', 'CD273', 'CD272', 'CD271', 'CD270', 'CD269', 'CD268', 'CD267',
            'CD266', 'CD265', 'CD264', 'CD263', 'CD262', 'CD261', 'CD260', 'CD259', 'CD258',
            'CD257', 'CD256', 'CD255', 'CD254', 'CD253', 'CD252', 'CD251', 'CD250', 'CD249',
            'CD248', 'CD247', 'CD246', 'CD245', 'CD244', 'CD243', 'CD242', 'CD241', 'CD240',
            'CD239', 'CD238', 'CD237', 'CD236', 'CD235', 'CD234', 'CD233', 'CD232', 'CD231',
            'CD230', 'CD229', 'CD228', 'CD227', 'CD226', 'CD225', 'CD224', 'CD222', 'CD221',
            'CD220', 'CD219', 'CD218', 'CD217', 'CD216', 'CD215', 'CD214', 'CD213', 'CD212',
            'CD211', 'CD210', 'CD209', 'CD208', 'CD207', 'CD206', 'CD205', 'CD204', 'CD203',
            'CD202', 'CD201', 'CD200', 'CD199', 'CD198', 'CD197', 'CD196', 'CD195', 'CD194',
            'CD193', 'CD192', 'CD191', 'CD190', 'CD189', 'CD188', 'CD187', 'CD186', 'CD185',
            'CD184', 'CD183', 'CD182', 'CD181', 'CD180', 'CD179', 'CD178', 'CD177', 'CD176',
            'CD175', 'CD174', 'CD173', 'CD172', 'CD171', 'CD170', 'CD169', 'CD168', 'CD167',
            'CD166', 'CD165', 'CD164', 'CD163', 'CD162', 'CD161', 'CD160', 'CD159', 'CD158',
            'CD157', 'CD156', 'CD155', 'CD154', 'CD153', 'CD152', 'CD151', 'CD150', 'CD149',
            'CD148', 'CD147', 'CD146', 'CD145', 'CD144', 'CD143', 'CD142', 'CD141', 'CD140',
            'CD139', 'CD138', 'CD137', 'CD136', 'CD135', 'CD134', 'CD133', 'CD132', 'CD131',
            'CD130', 'CD129', 'CD128', 'CD127', 'CD126', 'CD125', 'CD124', 'CD123', 'CD122',
            'CD121', 'CD120', 'CD119', 'CD118', 'CD117', 'CD116', 'CD115', 'CD114', 'CD113',
            'CD112', 'CD111', 'CD110', 'CD109', 'CD108', 'CD107', 'CD106', 'CD105', 'CD104',
            'CD103', 'CD102', 'CD101', 'CD100', 'CD99', 'CD98', 'CD97', 'CD96', 'CD95',
            'CD94', 'CD93', 'CD92', 'CD91', 'CD90', 'CD89', 'CD88', 'CD87', 'CD86', 'CD85',
            'CD84', 'CD83', 'CD82', 'CD81', 'CD80', 'CD79', 'CD78', 'CD77', 'CD76', 'CD75',
            'CD74', 'CD73', 'CD72', 'CD71', 'CD70', 'CD69', 'CD68', 'CD67', 'CD66', 'CD65',
            'CD64', 'CD63', 'CD62', 'CD61', 'CD60', 'CD59', 'CD58', 'CD57', 'CD56', 'CD55',
            'CD54', 'CD53', 'CD52', 'CD51', 'CD50', 'CD49', 'CD48', 'CD47', 'CD46', 'CD45',
            'CD44', 'CD43', 'CD42', 'CD41', 'CD40', 'CD39', 'CD38', 'CD37', 'CD36', 'CD35',
            'CD34', 'CD33', 'CD32', 'CD31', 'CD30', 'CD29', 'CD28', 'CD27', 'CD26', 'CD25',
            'CD24', 'CD23', 'CD22', 'CD21', 'CD20', 'CD19', 'CD18', 'CD17', 'CD16', 'CD15',
            'CD14', 'CD13', 'CD12', 'CD11', 'CD10', 'CD9', 'CD8', 'CD7', 'CD6', 'CD5',
            'CD4', 'CD3', 'CD2', 'CD1'
        }
        
        # Common stop words to filter out
        self.stop_words = {
            'THE', 'AND', 'OR', 'FOR', 'WITH', 'BY', 'FROM', 'TO', 'IN', 'ON', 'AT',
            'OF', 'A', 'AN', 'IS', 'ARE', 'WAS', 'WERE', 'BE', 'BEEN', 'BEING',
            'HAVE', 'HAS', 'HAD', 'DO', 'DOES', 'DID', 'WILL', 'WOULD', 'COULD',
            'SHOULD', 'MAY', 'MIGHT', 'MUST', 'CAN', 'CANT', 'DONT', 'WONT', 'SHANT'
        }
    
    def extract_targets_from_text(self, text: str, source: str = "unknown") -> List[DrugTarget]:
        """Extract drug targets from text using multiple methods.
        
        Args:
            text: Text to extract targets from
            source: Source of the text for attribution
            
        Returns:
            List of DrugTarget objects
        """
        targets = []
        
        # Method 1: Known targets lookup
        known_targets = self._extract_known_targets(text)
        targets.extend(known_targets)
        
        # Method 2: Pattern-based extraction
        pattern_targets = self._extract_pattern_targets(text, source)
        targets.extend(pattern_targets)
        
        # Method 3: NLP-based extraction (if available)
        if self.nlp_model:
            nlp_targets = self._extract_nlp_targets(text, source)
            targets.extend(nlp_targets)
        
        # Remove duplicates and return
        return self._deduplicate_targets(targets)
    
    def _extract_known_targets(self, text: str) -> List[DrugTarget]:
        """Extract targets that are in our known targets list."""
        targets = []
        text_upper = text.upper()
        
        for target in self.known_targets:
            if target in text_upper:
                confidence = self._calculate_target_confidence(target, text)
                targets.append(DrugTarget(
                    target_name=target,
                    target_type=self._classify_target_type(target),
                    mechanism_of_action=self._extract_mechanism_context(target, text),
                    confidence_score=confidence,
                    source="known_targets"
                ))
        
        return targets
    
    def _extract_pattern_targets(self, text: str, source: str) -> List[DrugTarget]:
        """Extract targets using regex patterns."""
        targets = []
        
        # Target patterns
        patterns = [
            (r'\b[A-Z]{2,10}\b', 'gene_symbol'),  # Gene symbols (e.g., EGFR, HER2)
            (r'\b[a-z]+ase\b', 'enzyme'),         # Enzymes (e.g., kinase, protease)
            (r'\b[a-z]+in\b', 'protein'),         # Proteins (e.g., insulin, albumin)
            (r'\b[A-Z][a-z]+in\b', 'protein'),    # Proper protein names
            (r'\b[A-Z][a-z]+mab\b', 'antibody'),  # Monoclonal antibodies
            (r'\b[A-Z][a-z]+nib\b', 'inhibitor'), # Kinase inhibitors
        ]
        
        for pattern, target_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match_upper = match.upper()
                if (len(match) > 2 and 
                    match_upper not in self.stop_words and
                    match_upper not in self.known_targets):
                    
                    confidence = self._calculate_target_confidence(match, text)
                    if confidence > 0.3:  # Filter low confidence matches
                        targets.append(DrugTarget(
                            target_name=match,
                            target_type=target_type,
                            mechanism_of_action=self._extract_mechanism_context(match, text),
                            confidence_score=confidence,
                            source=source
                        ))
        
        return targets
    
    def _extract_nlp_targets(self, text: str, source: str) -> List[DrugTarget]:
        """Extract targets using NLP model."""
        targets = []
        
        try:
            doc = self.nlp_model(text)
            
            # Look for protein/gene mentions in named entities
            for ent in doc.ents:
                if self._is_target_entity(ent):
                    confidence = self._calculate_target_confidence(ent.text, text)
                    targets.append(DrugTarget(
                        target_name=ent.text.upper(),
                        target_type=self._classify_target_type(ent.text),
                        mechanism_of_action=self._extract_mechanism_context(ent.text, text),
                        confidence_score=confidence,
                        source=source
                    ))
            
        except Exception as e:
            logger.warning(f"Error in NLP target extraction: {e}")
        
        return targets
    
    def _is_target_entity(self, entity) -> bool:
        """Check if spaCy entity is likely a drug target."""
        text = entity.text.upper()
        return (text in self.known_targets or 
                text.endswith('ASE') or 
                text.endswith('IN') or
                (len(text) <= 6 and text.isalpha()))
    
    def _calculate_target_confidence(self, target: str, text: str) -> float:
        """Calculate confidence score for a target match."""
        confidence = 0.0
        target_upper = target.upper()
        text_upper = text.upper()
        
        # Known target bonus
        if target_upper in self.known_targets:
            confidence += 0.8
        
        # Pattern-based scoring
        if re.match(r'^[A-Z]{2,10}$', target_upper):  # Gene symbol pattern
            confidence += 0.6
        elif target_upper.endswith('ASE'):  # Enzyme pattern
            confidence += 0.5
        elif target_upper.endswith('IN'):  # Protein pattern
            confidence += 0.4
        
        # Context scoring
        context_words = ['target', 'inhibit', 'block', 'bind', 'activate', 'modulate']
        for word in context_words:
            if word in text_upper:
                confidence += 0.1
        
        # Frequency scoring
        frequency = text_upper.count(target_upper)
        confidence += min(frequency * 0.1, 0.3)
        
        return min(confidence, 1.0)
    
    def _classify_target_type(self, target: str) -> str:
        """Classify the type of target."""
        target_upper = target.upper()
        
        if target_upper in self.known_targets:
            if target_upper.startswith('CD'):
                return 'cell_surface_marker'
            elif target_upper.endswith('ASE'):
                return 'enzyme'
            elif target_upper.endswith('IN'):
                return 'protein'
            else:
                return 'gene_protein'
        
        # Pattern-based classification
        if re.match(r'^[A-Z]{2,10}$', target_upper):
            return 'gene_symbol'
        elif target_upper.endswith('ASE'):
            return 'enzyme'
        elif target_upper.endswith('IN'):
            return 'protein'
        elif target_upper.endswith('MAB'):
            return 'antibody'
        elif target_upper.endswith('NIB'):
            return 'inhibitor'
        else:
            return 'unknown'
    
    def _extract_mechanism_context(self, target: str, text: str) -> str:
        """Extract mechanism of action context around the target."""
        target_pos = text.upper().find(target.upper())
        if target_pos == -1:
            return text[:200] + "..." if len(text) > 200 else text
        
        # Get context around the target
        start = max(0, target_pos - 200)
        end = min(len(text), target_pos + 200)
        context = text[start:end]
        
        return context
    
    def _deduplicate_targets(self, targets: List[DrugTarget]) -> List[DrugTarget]:
        """Remove duplicate targets, keeping the one with highest confidence."""
        target_dict = {}
        
        for target in targets:
            key = target.target_name.upper()
            if key not in target_dict or target.confidence_score > target_dict[key].confidence_score:
                target_dict[key] = target
        
        return list(target_dict.values())
    
    def extract_targets_simple(self, text: str) -> List[str]:
        """Simple target extraction returning just target names.
        
        This method provides backward compatibility with existing code.
        
        Args:
            text: Text to extract targets from
            
        Returns:
            List of target names
        """
        targets = self.extract_targets_from_text(text)
        return [target.target_name for target in targets]


# Global instance for easy import
target_extractor = TargetExtractor()

