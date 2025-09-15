"""FDA data collector."""

from typing import List, Dict, Any, Optional
from loguru import logger
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from .base_collector import BaseCollector, CollectedData
from config import settings


class FDACollector(BaseCollector):
    """Collector for FDA data."""
    
    def __init__(self):
        super().__init__("fda", settings.fda_base_url)
        
        # Define extraction strategy for FDA information
        self.extraction_strategy = LLMExtractionStrategy(
            provider="openai",
            api_token=settings.openai_api_key,
            instruction="""
            Extract the following FDA information from the page:
            - Drug name (generic and brand)
            - Approval status
            - Approval date
            - Indication
            - Company/sponsor
            - Safety information
            - Labeling information
            Return the information in a structured format.
            """
        )
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect FDA data."""
        collected_data = []
        
        # FDA endpoints to collect from
        fda_endpoints = [
            "/drugs/drug-approvals-and-databases/drug-approvals-and-databases",
            "/drugs/drug-safety-and-availability/drug-safety-and-availability",
            "/drugs/drug-approvals-and-databases/drug-approvals-and-databases-drug-approvals-and-databases"
        ]
        
        try:
            for endpoint in fda_endpoints:
                fda_data = await self._collect_fda_endpoint(endpoint)
                if fda_data:
                    collected_data.extend(fda_data)
                    
        except Exception as e:
            logger.error(f"Error collecting FDA data: {e}")
        
        return collected_data
    
    async def _collect_fda_endpoint(self, endpoint: str) -> List[CollectedData]:
        """Collect data from a specific FDA endpoint."""
        collected_data = []
        
        try:
            fda_url = f"{self.base_url}{endpoint}"
            
            # Crawl the page
            content = await self._crawl_with_crawl4ai(fda_url, self.extraction_strategy)
            
            if content:
                collected_data.append(CollectedData(
                    source_url=fda_url,
                    title=f"FDA Information: {endpoint}",
                    content=content,
                    source_type=self.source_type,
                    metadata={
                        "endpoint": endpoint,
                        "source": "fda.gov"
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error collecting FDA endpoint {endpoint}: {e}")
        
        return collected_data
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw FDA data."""
        # This method is implemented in collect_data for this collector
        return []
