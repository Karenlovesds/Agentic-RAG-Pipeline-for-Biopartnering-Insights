"""Drugs.com data collector."""

from typing import List, Dict, Any, Optional
from loguru import logger
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from .base_collector import BaseCollector, CollectedData
from config import settings


class DrugsCollector(BaseCollector):
    """Collector for Drugs.com data."""
    
    def __init__(self):
        super().__init__("drugs_com", settings.drugs_com_base_url)
        
        # Define extraction strategy for drug information
        self.extraction_strategy = LLMExtractionStrategy(
            provider="openai",
            api_token=settings.openai_api_key,
            instruction="""
            Extract the following drug information from the page:
            - Generic name
            - Brand names
            - Drug class
            - Mechanism of action
            - FDA approval status
            - Indications
            - Side effects
            - Dosage information
            Return the information in a structured format.
            """
        )
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect drug data from Drugs.com."""
        collected_data = []
        
        # List of common cancer drugs to collect
        drug_names = [
            "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab",
            "trastuzumab", "pertuzumab", "ado-trastuzumab emtansine",
            "palbociclib", "ribociclib", "abemaciclib", "fulvestrant",
            "olaparib", "rucaparib", "niraparib", "talazoparib",
            "bevacizumab", "ramucirumab", "aflibercept", "regorafenib",
            "sorafenib", "sunitinib", "pazopanib", "cabozantinib"
        ]
        
        try:
            for drug_name in drug_names:
                drug_data = await self._collect_drug_info(drug_name)
                if drug_data:
                    collected_data.append(drug_data)
                    
        except Exception as e:
            logger.error(f"Error collecting drugs data: {e}")
        
        return collected_data
    
    async def _collect_drug_info(self, drug_name: str) -> Optional[CollectedData]:
        """Collect information for a specific drug."""
        try:
            # Construct URL for drug page
            drug_url = f"{self.base_url}/drug/{drug_name}.html"
            
            # Crawl the page
            content = await self._crawl_with_crawl4ai(drug_url, self.extraction_strategy)
            
            if content:
                return CollectedData(
                    source_url=drug_url,
                    title=f"Drug Information: {drug_name}",
                    content=content,
                    source_type=self.source_type,
                    metadata={
                        "drug_name": drug_name,
                        "source": "drugs.com"
                    }
                )
                
        except Exception as e:
            logger.error(f"Error collecting drug info for {drug_name}: {e}")
        
        return None
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw drug data."""
        # This method is implemented in collect_data for this collector
        return []
