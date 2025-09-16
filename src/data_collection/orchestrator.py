"""Data collection orchestrator to coordinate multiple collectors."""

import asyncio
from typing import List, Dict, Any
from loguru import logger
from .clinical_trials_collector import ClinicalTrialsCollector
from .fda_collector import FDACollector
from .company_website_collector import CompanyWebsiteCollector
from .drugs_collector import DrugsCollector


class DataCollectionOrchestrator:
    """Orchestrates data collection from multiple sources."""
    
    def __init__(self):
        self.collectors = {
            "clinical_trials": ClinicalTrialsCollector(),
            "fda": FDACollector(),
            "company_websites": CompanyWebsiteCollector(),
            "drugs": DrugsCollector()
        }
    
    async def run_full_collection(self, sources: List[str]) -> Dict[str, int]:
        """Run data collection for specified sources."""
        results = {}
        
        for source in sources:
            try:
                logger.info(f"Starting collection from {source}")
                
                if source == "clinical_trials":
                    data = await self.collectors[source].collect_data({'pageSize': 10})
                elif source == "fda":
                    data = await self.collectors[source].collect_data(['drug_approvals', 'adverse_events'])
                elif source == "company_websites":
                    data = await self.collectors[source].collect_data(max_companies=2)
                elif source == "drugs":
                    data = await self.collectors[source].collect_data(['metformin', 'lisinopril', 'atorvastatin'])
                elif source == "drug_interactions":
                    data = await self.collectors[source].collect_data([('warfarin', 'aspirin'), ('metformin', 'insulin')])
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue
                
                # Save documents
                saved_count = 0
                for doc in data:
                    try:
                        self.collectors[source]._save_document(doc)
                        saved_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to save document: {e}")
                
                results[source] = saved_count
                logger.info(f"✅ Collected {saved_count} documents from {source}")
                
            except Exception as e:
                logger.error(f"Error collecting from {source}: {e}")
                results[source] = 0
        
        return results