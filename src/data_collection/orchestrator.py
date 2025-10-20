"""Data collection orchestrator to coordinate multiple collectors."""

import asyncio
import sys
import os
from typing import List, Dict, Any
from loguru import logger
from .clinical_trials_collector import ClinicalTrialsCollector
from .fda_collector import FDACollector
from .company_website_collector import CompanyWebsiteCollector
from .drugs_collector import DrugsCollector

# Add project root to path for maintenance imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class DataCollectionOrchestrator:
    """Orchestrates data collection from multiple sources."""
    
    def __init__(self, run_maintenance: bool = True):
        self.collectors = {
            "clinical_trials": ClinicalTrialsCollector(),
            "fda": FDACollector(),
            "company_websites": CompanyWebsiteCollector(),
            "drugs": DrugsCollector()
        }
        self.run_maintenance = run_maintenance
    
    async def run_full_collection(self, sources: List[str]) -> Dict[str, int]:
        """Run data collection for specified sources."""
        results = {}
        
        # Run maintenance before data collection if enabled
        if self.run_maintenance:
            maintenance_results = await self._run_maintenance()
            results["maintenance"] = maintenance_results
        
        # Run data collection for each source
        for source in sources:
            try:
                source_results = await self._collect_from_source(source)
                results[source] = source_results
            except Exception as e:
                logger.error(f"Error collecting from {source}: {e}")
                results[source] = 0
        
        # Generate CSV files after data collection
        csv_results = await self._generate_csv_exports()
        results["csv_generation"] = csv_results
        
        # Populate vector database after data collection
        vector_db_results = await self._populate_vector_database()
        results["vector_database"] = vector_db_results
        
        return results
    
    async def _run_maintenance(self) -> Dict[str, Any]:
        """Run database maintenance before data collection."""
        try:
            from scripts.maintenance.maintenance_orchestrator import run_maintenance
            logger.info("🔧 Running database maintenance before data collection...")
            maintenance_results = await run_maintenance()
            logger.info(f"✅ Maintenance completed: {maintenance_results['successful_tasks']}/{maintenance_results['total_tasks']} tasks successful")
            return maintenance_results
        except Exception as e:
            logger.error(f"❌ Maintenance failed: {e}")
            return {"error": str(e)}
    
    async def _collect_from_source(self, source: str) -> int:
        """Collect data from a specific source."""
        logger.info(f"Starting collection from {source}")
        
        # Determine collection parameters based on source
        collection_params = self._get_collection_params(source)
        
        # Collect data
        data = await self.collectors[source].collect_data(collection_params)
        
        # Save documents
        saved_count = self._save_documents(data, source)
        
        logger.info(f"✅ Collected {saved_count} documents from {source}")
        return saved_count
    
    def _get_collection_params(self, source: str) -> Any:
        """Get collection parameters for a specific source."""
        # Define parameter mappings for each source
        param_mappings = {
            "clinical_trials": {'pageSize': 10},
            "fda": ['drug_approvals', 'adverse_events'],
            "company_websites": {'max_companies': 2},
            "drugs": ['metformin', 'lisinopril', 'atorvastatin'],
            "drug_interactions": [('warfarin', 'aspirin'), ('metformin', 'insulin')]
        }
        
        if source in param_mappings:
            return param_mappings[source]
        else:
            logger.warning(f"Unknown source: {source}")
            return None
    
    def _save_documents(self, data: List, source: str) -> int:
        """Save documents from collected data."""
        saved_count = 0
        for doc in data:
            try:
                self.collectors[source]._save_document(doc)
                saved_count += 1
            except Exception as e:
                logger.warning(f"Failed to save document: {e}")
        return saved_count
    
    async def _generate_csv_exports(self) -> Dict[str, Any]:
        """Generate CSV files after data collection."""
        try:
            from src.processing.pipeline import generate_csv_exports
            from src.models.database import get_db
            
            logger.info("📊 Generating CSV exports after data collection...")
            db = get_db()
            csv_results = generate_csv_exports(db)
            db.close()
            
            if csv_results.get("success"):
                logger.info("✅ CSV files generated successfully")
            else:
                logger.error(f"❌ CSV generation failed: {csv_results.get('error', 'Unknown error')}")
            
            return csv_results
                
        except Exception as e:
            logger.error(f"❌ Error generating CSV files: {e}")
            return {"error": str(e), "success": False}
    
    async def _populate_vector_database(self) -> Dict[str, Any]:
        """Populate vector database after data collection."""
        try:
            from src.processing.pipeline import populate_vector_database
            
            logger.info("🧠 Populating vector database for React RAG agent...")
            vector_db_results = populate_vector_database()
            
            if vector_db_results.get("status") == "success":
                logger.info(f"✅ Vector database populated successfully with {vector_db_results.get('final_chunks', 0)} chunks")
            else:
                logger.error(f"❌ Vector database population failed: {vector_db_results.get('error', 'Unknown error')}")
            
            return vector_db_results
                
        except Exception as e:
            logger.error(f"❌ Error populating vector database: {e}")
            return {"error": str(e), "status": "error"}