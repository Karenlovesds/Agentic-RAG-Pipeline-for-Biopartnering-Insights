"""
FDA Indication Extractor - Extracts approved indications for drugs from FDA data.
"""

import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from .base_collector import BaseCollector, CollectedData
from config.config import settings


class FDAIndicationExtractor(BaseCollector):
    """Extracts approved indications for specific drugs from FDA data."""
    
    def __init__(self):
        super().__init__("fda_indications", "https://api.fda.gov")
        self.fda_base_url = "https://api.fda.gov"
    
    async def extract_drug_indications(self, drug_names: List[str]) -> List[Dict[str, Any]]:
        """Extract approved indications for a list of drug names."""
        drug_indications = []
        
        for drug_name in drug_names:
            try:
                logger.info(f"Extracting FDA indications for: {drug_name}")
                indications = await self._get_drug_indications(drug_name)
                if indications:
                    drug_indications.extend(indications)
                    logger.info(f"✅ Found {len(indications)} indication entries for {drug_name}")
                else:
                    logger.warning(f"⚠️ No indications found for {drug_name}")
            except Exception as e:
                logger.error(f"Error extracting indications for {drug_name}: {e}")
                continue
        
        return drug_indications
    
    async def _get_drug_indications(self, drug_name: str) -> List[Dict[str, Any]]:
        """Get FDA indications for a specific drug."""
        indications_data = []
        
        try:
            # Search for drug by brand name first
            brand_results = await self._search_fda_drug(drug_name, search_type="brand")
            if brand_results:
                indications_data.extend(brand_results)
            
            # Search for drug by generic name
            generic_results = await self._search_fda_drug(drug_name, search_type="generic")
            if generic_results:
                indications_data.extend(generic_results)
            
            # Remove duplicates based on drug ID
            unique_indications = self._deduplicate_indications(indications_data)
            
        except Exception as e:
            logger.error(f"Error getting FDA indications for {drug_name}: {e}")
        
        return unique_indications
    
    async def _search_fda_drug(self, drug_name: str, search_type: str = "brand") -> List[Dict[str, Any]]:
        """Search FDA database for drug information."""
        try:
            if search_type == "brand":
                search_field = "openfda.brand_name"
            else:
                search_field = "openfda.generic_name"
            
            url = f"{self.fda_base_url}/drug/label.json"
            params = {
                "limit": 10,
                "search": f"{search_field}:\"{drug_name}\"",
                "sort": "effective_time:desc"
            }
            
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                indication_entries = []
                for result in results:
                    indication_entry = self._extract_indication_entry(result, drug_name)
                    if indication_entry:
                        indication_entries.append(indication_entry)
                
                return indication_entries
            
        except Exception as e:
            logger.error(f"Error searching FDA for {drug_name} ({search_type}): {e}")
        
        return []
    
    def _extract_indication_entry(self, fda_result: Dict[str, Any], drug_name: str) -> Optional[Dict[str, Any]]:
        """Extract indication information from FDA result."""
        try:
            openfda = fda_result.get("openfda", {})
            
            # Extract basic drug info
            brand_names = openfda.get("brand_name", [])
            generic_names = openfda.get("generic_name", [])
            manufacturer = openfda.get("manufacturer_name", [])
            
            # Extract indications
            indications = fda_result.get("indications_and_usage", [])
            if not indications:
                return None
            
            # Extract approval date
            effective_time = fda_result.get("effective_time", "")
            approval_date = self._parse_approval_date(effective_time)
            
            # Extract product type and route
            product_type = openfda.get("product_type", [])
            route = openfda.get("route", [])
            
            # Extract application number
            application_number = openfda.get("application_number", [])
            
            indication_entry = {
                "drug_name": drug_name,
                "brand_names": brand_names,
                "generic_names": generic_names,
                "manufacturer": manufacturer[0] if manufacturer else None,
                "indications": indications,
                "approval_date": approval_date,
                "effective_time": effective_time,
                "product_type": product_type[0] if product_type else None,
                "route": route[0] if route else None,
                "application_number": application_number[0] if application_number else None,
                "fda_id": fda_result.get("id", ""),
                "source_url": f"{self.fda_base_url}/drug/label.json?id={fda_result.get('id', '')}"
            }
            
            return indication_entry
            
        except Exception as e:
            logger.error(f"Error extracting indication entry: {e}")
            return None
    
    def _parse_approval_date(self, effective_time: str) -> Optional[str]:
        """Parse FDA effective time to get approval date."""
        if not effective_time:
            return None
        
        try:
            # FDA effective time format: "20141219" -> "2014-12-19"
            if len(effective_time) == 8 and effective_time.isdigit():
                year = effective_time[:4]
                month = effective_time[4:6]
                day = effective_time[6:8]
                return f"{year}-{month}-{day}"
            else:
                return effective_time
        except Exception:
            return effective_time
    
    def _deduplicate_indications(self, indications_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate indication entries based on FDA ID."""
        seen_ids = set()
        unique_indications = []
        
        for entry in indications_data:
            fda_id = entry.get("fda_id")
            if fda_id and fda_id not in seen_ids:
                seen_ids.add(fda_id)
                unique_indications.append(entry)
        
        return unique_indications
    
    def format_indications_for_database(self, indication_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format indication entries for database storage."""
        formatted_entries = []
        
        for entry in indication_entries:
            # Extract and clean indications
            raw_indications = entry.get("indications", [])
            cleaned_indications = self._clean_indications(raw_indications)
            
            if cleaned_indications:
                formatted_entry = {
                    "drug_name": entry.get("drug_name"),
                    "brand_name": entry.get("brand_names", [None])[0],
                    "generic_name": entry.get("generic_names", [None])[0],
                    "manufacturer": entry.get("manufacturer"),
                    "approved_indications": cleaned_indications,
                    "approval_date": entry.get("approval_date"),
                    "product_type": entry.get("product_type"),
                    "route": entry.get("route"),
                    "fda_id": entry.get("fda_id"),
                    "source_url": entry.get("source_url")
                }
                formatted_entries.append(formatted_entry)
        
        return formatted_entries
    
    def _clean_indications(self, raw_indications: List[str]) -> List[str]:
        """Clean and standardize indication text."""
        cleaned = []
        
        for indication in raw_indications:
            if not indication or len(indication.strip()) < 10:
                continue
            
            # Clean up the indication text
            cleaned_indication = indication.strip()
            
            # Remove common prefixes
            prefixes_to_remove = [
                "INDICATIONS AND USAGE:",
                "INDICATIONS:",
                "USAGE:",
                "This drug is indicated for",
                "Indicated for",
                "For the treatment of",
                "For treatment of"
            ]
            
            for prefix in prefixes_to_remove:
                if cleaned_indication.upper().startswith(prefix.upper()):
                    cleaned_indication = cleaned_indication[len(prefix):].strip()
                    break
            
            # Capitalize first letter
            if cleaned_indication:
                cleaned_indication = cleaned_indication[0].upper() + cleaned_indication[1:]
                cleaned.append(cleaned_indication)
        
        return cleaned
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect FDA indication data for specific drugs."""
        # This method is required by BaseCollector but we'll use extract_drug_indications instead
        return []
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into structured format."""
        # This method is required by BaseCollector but we don't use it
        return []


def create_fda_indication_extractor() -> FDAIndicationExtractor:
    """Create an FDA indication extractor instance."""
    return FDAIndicationExtractor()
