"""Data collection orchestrator."""

import asyncio
from typing import List, Dict, Any
from loguru import logger
from datetime import datetime

from .clinical_trials_collector import ClinicalTrialsCollector
from .drugs_collector import DrugsCollector
from .fda_collector import FDACollector


class DataCollectionOrchestrator:
    """Orchestrates data collection from all sources."""
    
    def __init__(self):
        self.collectors = {
            "clinical_trials": ClinicalTrialsCollector(),
            "drugs": DrugsCollector(),
            "fda": FDACollector()
        }
    
    async def run_full_collection(self, sources: List[str] = None) -> Dict[str, int]:
        """Run data collection from all or specified sources."""
        if sources is None:
            sources = list(self.collectors.keys())
        
        logger.info(f"Starting data collection from sources: {sources}")
        start_time = datetime.now()
        
        results = {}
        
        # Run collectors concurrently
        tasks = []
        for source in sources:
            if source in self.collectors:
                task = asyncio.create_task(
                    self.collectors[source].run_collection(),
                    name=f"collect_{source}"
                )
                tasks.append((source, task))
        
        # Wait for all tasks to complete
        for source, task in tasks:
            try:
                count = await task
                results[source] = count
                logger.info(f"Completed collection from {source}: {count} documents")
            except Exception as e:
                logger.error(f"Error in collection from {source}: {e}")
                results[source] = 0
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        total_documents = sum(results.values())
        logger.info(f"Data collection completed in {duration:.2f} seconds. Total documents: {total_documents}")
        
        return results
    
    async def run_incremental_collection(self) -> Dict[str, int]:
        """Run incremental data collection (only new/updated data)."""
        logger.info("Starting incremental data collection")
        
        # For now, run full collection
        # In the future, this could be optimized to only collect new data
        return await self.run_full_collection()
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get status of data collection."""
        # This could be expanded to check database for recent collections
        return {
            "last_collection": "Not implemented yet",
            "total_documents": "Not implemented yet",
            "sources_available": list(self.collectors.keys())
        }
