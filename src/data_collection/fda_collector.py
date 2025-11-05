"""Enhanced FDA data collector focused on validation and signal extraction.

Core responsibilities kept:
- Validate drug names against FDA labels (and compute confidence)
- Extract targets and indications from FDA data

Note: High-level bulk collection endpoints were removed to avoid dead code.
"""

import requests
import asyncio
import spacy
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from loguru import logger
from .utils import BaseCollector, CollectedData, DataCollectionUtils
from .config import APIConfig


@dataclass
class ValidatedDrug:
    """Data class for validated drug information from FDA APIs."""
    drug_name: str
    brand_names: List[str]
    generic_names: List[str]
    manufacturer: Optional[str]
    product_type: Optional[str]
    route: Optional[str]
    indications: List[str]
    approval_date: Optional[str]
    application_number: Optional[str]
    fda_id: str
    validation_confidence: float
    source_url: str


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
    approval_status: bool
    approval_date: Optional[str]
    source: str
    confidence_score: float


class EnhancedFDACollector(BaseCollector):
    """Enhanced collector for FDA data with comprehensive drug validation capabilities."""
    
    def __init__(self):
        super().__init__("fda", APIConfig.FDA_BASE_URL)
        
        # Initialize NLP model for drug entity recognition
        try:
            self.nlp_model = spacy.load("en_core_sci_sm")
        except OSError:
            logger.warning("Scientific spaCy model not found, using default model")
            self.nlp_model = spacy.load("en_core_web_sm")
                
        # Use configuration for FDA API endpoints
        self.fda_base_url = APIConfig.FDA_BASE_URL
        self.endpoints = APIConfig.FDA_ENDPOINTS
    
    async def validate_drug_names(self, drug_names: List[str]) -> List[ValidatedDrug]:
        """Validate extracted drug names against FDA database."""
        validated_drugs = []
        
        logger.info(f"Validating {len(drug_names)} drug names against FDA database")
        
        for drug_name in drug_names:
            try:
                validated_drug = await self._validate_single_drug(drug_name)
                if validated_drug:
                    validated_drugs.append(validated_drug)
                    logger.info(f"✅ Validated: {drug_name}")
                else:
                    logger.warning(f"⚠️ No FDA validation found for: {drug_name}")
            except Exception as e:
                logger.error(f"Error validating {drug_name}: {e}")
                continue
        
        logger.info(f"Successfully validated {len(validated_drugs)}/{len(drug_names)} drugs")
        return validated_drugs
    
    async def _validate_single_drug(self, drug_name: str) -> Optional[ValidatedDrug]:
        """Validate a single drug name against FDA database."""
        try:
            # Search by brand name first
            brand_results = await self._search_fda_by_brand_name(drug_name)
            if brand_results:
                return self._create_validated_drug(brand_results[0], drug_name, "brand")
            
            # Search by generic name
            generic_results = await self._search_fda_by_generic_name(drug_name)
            if generic_results:
                return self._create_validated_drug(generic_results[0], drug_name, "generic")
            
            # Search by substance name
            substance_results = await self._search_fda_by_substance_name(drug_name)
            if substance_results:
                return self._create_validated_drug(substance_results[0], drug_name, "substance")
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating drug {drug_name}: {e}")
            return None
    
    async def _search_fda_by_brand_name(self, drug_name: str) -> List[Dict[str, Any]]:
        """Search FDA database by brand name."""
        return await self._search_fda_database(f"openfda.brand_name:\"{drug_name}\"")
    
    async def _search_fda_by_generic_name(self, drug_name: str) -> List[Dict[str, Any]]:
        """Search FDA database by generic name."""
        return await self._search_fda_database(f"openfda.generic_name:\"{drug_name}\"")
    
    async def _search_fda_by_substance_name(self, drug_name: str) -> List[Dict[str, Any]]:
        """Search FDA database by substance name."""
        return await self._search_fda_database(f"openfda.substance_name:\"{drug_name}\"")
    
    async def _search_fda_database(self, search_query: str) -> List[Dict[str, Any]]:
        """Generic FDA database search."""
        try:
            url = f"{self.fda_base_url}{self.endpoints['drug_label']}"
            params = {
                "limit": 5,
                "search": search_query,
                "sort": "effective_time:desc"
            }
            
            response = await self._make_async_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                logger.warning(f"FDA API request failed: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching FDA database: {e}")
            return []
    
    def _create_validated_drug(self, fda_result: Dict[str, Any], original_name: str, match_type: str) -> ValidatedDrug:
        """Create ValidatedDrug object from FDA result."""
        openfda = fda_result.get("openfda", {})
        
        # Calculate validation confidence based on match type and data completeness
        confidence = self._calculate_validation_confidence(fda_result, match_type)
        
        return ValidatedDrug(
            drug_name=original_name,
            brand_names=openfda.get("brand_name", []),
            generic_names=openfda.get("generic_name", []),
            manufacturer=openfda.get("manufacturer_name", [""])[0] if openfda.get("manufacturer_name") else None,
            product_type=openfda.get("product_type", [""])[0] if openfda.get("product_type") else None,
            route=openfda.get("route", [""])[0] if openfda.get("route") else None,
            indications=fda_result.get("indications_and_usage", []),
            approval_date=self._parse_approval_date(fda_result.get("effective_time", "")),
            application_number=(
                openfda.get("application_number", [""])[0] 
                if openfda.get("application_number") 
                else None
            ),
            fda_id=fda_result.get("id", ""),
            validation_confidence=confidence,
            source_url=f"{self.fda_base_url}{self.endpoints['drug_label']}?id={fda_result.get('id', '')}"
        )
    
    def _calculate_validation_confidence(self, fda_result: Dict[str, Any], match_type: str) -> float:
        """Calculate confidence score for drug validation."""
        base_confidence = {
            "brand": 0.95,
            "generic": 0.90,
            "substance": 0.85
        }.get(match_type, 0.80)
        
        # Boost confidence based on data completeness
        openfda = fda_result.get("openfda", {})
        completeness_factors = [
            bool(openfda.get("brand_name")),
            bool(openfda.get("generic_name")),
            bool(openfda.get("manufacturer_name")),
            bool(openfda.get("application_number")),
            bool(fda_result.get("indications_and_usage"))
        ]
        
        completeness_bonus = sum(completeness_factors) * 0.02
        return min(1.0, base_confidence + completeness_bonus)
    
    async def extract_drug_targets(self, drug_name: str, company_name: str = None) -> List[DrugTarget]:
        """Extract drug targets from FDA data and scientific literature."""
        targets = []
        
        try:
            # Get FDA drug data
            fda_data = await self._search_fda_by_brand_name(drug_name)
            if not fda_data:
                fda_data = await self._search_fda_by_generic_name(drug_name)
            
            if fda_data:
                # Extract targets from FDA clinical pharmacology
                fda_targets = self._extract_targets_from_fda_data(fda_data[0])
                targets.extend(fda_targets)
                        
            # Remove duplicates and sort by confidence
            targets = DataCollectionUtils.deduplicate_targets(targets)
            targets.sort(key=lambda x: x.confidence_score, reverse=True)
            targets = targets[:10]  # Return top 10 targets
            
        except Exception as e:
            logger.error(f"Error extracting targets for {drug_name}: {e}")
        
        return targets
    
    def _extract_targets_from_fda_data(self, fda_result: Dict[str, Any]) -> List[DrugTarget]:
        """Extract drug targets from FDA clinical pharmacology data."""
        targets = []
        
        # Extract from clinical pharmacology section
        clinical_pharm = fda_result.get("clinical_pharmacology", [])
        if clinical_pharm:
            text = " ".join(clinical_pharm)
            targets.extend(self._extract_targets_from_text(text, "FDA Clinical Pharmacology"))
        
        # Extract from mechanism of action
        mechanism = fda_result.get("mechanism_of_action", [])
        if mechanism:
            text = " ".join(mechanism)
            targets.extend(self._extract_targets_from_text(text, "FDA Mechanism of Action"))
        
        return targets
    
    def _extract_targets_from_text(self, text: str, source: str) -> List[DrugTarget]:
        """Extract drug targets from text using consolidated extractor."""
        from .utils import TargetExtractor
        
        # Initialize extractor with NLP model if available
        extractor = TargetExtractor(nlp_model=self.nlp_model)
        return extractor.extract_targets_from_text(text, source)
    
    # PubMed target extraction removed
    
    async def extract_drug_indications(self, drug_name: str, company_name: str = None) -> List[DrugIndication]:
        """Extract drug indications from FDA data and scientific literature."""
        indications = []
        
        try:
            # Get FDA drug data
            fda_data = await self._search_fda_by_brand_name(drug_name)
            if not fda_data:
                fda_data = await self._search_fda_by_generic_name(drug_name)
            
            if fda_data:
                # Extract indications from FDA data
                fda_indications = self._extract_indications_from_fda_data(fda_data[0])
                indications.extend(fda_indications)
                        
            # Remove duplicates and sort by confidence
            indications = DataCollectionUtils.deduplicate_indications(indications)
            indications.sort(key=lambda x: x.confidence_score, reverse=True)
            indications = indications[:10]  # Return top 10 indications
            
        except Exception as e:
            logger.error(f"Error extracting indications for {drug_name}: {e}")
        
        return indications
    
    def _extract_indications_from_fda_data(self, fda_result: Dict[str, Any]) -> List[DrugIndication]:
        """Extract drug indications from FDA data."""
        indications = []
        
        # Extract from indications and usage section
        fda_indications = fda_result.get("indications_and_usage", [])
        if fda_indications:
            for indication_text in fda_indications:
                indications.append(DrugIndication(
                    indication=indication_text,
                    approval_status=True,  # FDA data indicates approved indications
                    approval_date=self._parse_approval_date(fda_result.get("effective_time", "")),
                    source="FDA",
                    confidence_score=0.95  # High confidence for FDA data
                ))
        
        return indications
    
    async def _make_async_request(self, url: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        """Make asynchronous HTTP request."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, params=params, timeout=30)
            )
            return response
        except Exception as e:
            logger.error(f"Error making async request to {url}: {e}")
            return None
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect data from FDA source.
        
        Note: This collector primarily focuses on validation. For bulk data collection,
        use the validation methods directly. This method returns empty list as
        the collector is used for validation rather than document collection.
        """
        logger.info("FDA collector is primarily for validation, not document collection")
        return []
    
    def _parse_approval_date(self, effective_time: str) -> Optional[str]:
        """Parse FDA effective time to get approval date."""
        try:
            if not effective_time:
                return None
            
            # FDA effective time format: "20191220" -> "2019-12-20"
            if len(effective_time) == 8 and effective_time.isdigit():
                year = effective_time[:4]
                month = effective_time[4:6]
                day = effective_time[6:8]
                return f"{year}-{month}-{day}"
            
            return effective_time
            
        except Exception as e:
            logger.error(f"Error parsing approval date {effective_time}: {e}")
            return None
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []


# Keep the original FDACollector for backward compatibility
class FDACollector(EnhancedFDACollector):
    """Original FDA collector - now inherits from enhanced version."""
    
    def __init__(self):
        super().__init__()
        logger.info("Using enhanced FDA collector with drug validation capabilities")
