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
            try:
                from scripts.maintenance.maintenance_orchestrator import run_maintenance
                logger.info("🔧 Running database maintenance before data collection...")
                maintenance_results = await run_maintenance()
                results["maintenance"] = maintenance_results
                logger.info(f"✅ Maintenance completed: {maintenance_results['successful_tasks']}/{maintenance_results['total_tasks']} tasks successful")
            except Exception as e:
                logger.error(f"❌ Maintenance failed: {e}")
                results["maintenance"] = {"error": str(e)}
        
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
        
        # Generate CSV files after data collection
        try:
            from src.processing.pipeline import generate_csv_exports
            from src.models.database import get_db
            
            logger.info("📊 Generating CSV exports after data collection...")
            db = get_db()
            csv_results = generate_csv_exports(db)
            db.close()
            
            if csv_results.get("success"):
                logger.info("✅ CSV files generated successfully")
                results["csv_generation"] = csv_results
            else:
                logger.error(f"❌ CSV generation failed: {csv_results.get('error', 'Unknown error')}")
                results["csv_generation"] = csv_results
                
        except Exception as e:
            logger.error(f"❌ Error generating CSV files: {e}")
            results["csv_generation"] = {"error": str(e), "success": False}
        
        return results