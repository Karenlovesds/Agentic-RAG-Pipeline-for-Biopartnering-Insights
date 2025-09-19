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
from ..models.database import get_db
from ..models.entities import Drug

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
    
    def _get_drug_names_from_database(self, limit: int = 10) -> List[str]:
        """Get drug names from the database for data collection."""
        try:
            session = get_db()
            try:
                # Get unique drug names (both generic and brand names)
                drugs = session.query(Drug.generic_name, Drug.brand_name).filter(
                    Drug.generic_name.isnot(None)
                ).distinct().limit(limit).all()
                
                drug_names = []
                for generic_name, brand_name in drugs:
                    if generic_name:
                        drug_names.append(generic_name)
                    if brand_name and brand_name.strip():
                        drug_names.append(brand_name)
                
                logger.info(f"Retrieved {len(drug_names)} drug names from database")
                return drug_names
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error getting drug names from database: {e}")
            # Fallback to default drug names
            return      [
            # Common Roche/Genentech marketed
            "Atezolizumab","Giredestrant","Codrituzumab","Inavolisib","Polatuzumab vedotin piiq",
            "Mosunetuzumab","Trastuzumab emtansine","Cevostamab","Clesitamig","Divarasib",
            "Glofitamab","Mosperafenib","Alectinib","Autogene cevumeran","Cobimetinib",
            "Entrectinib","Pertuzumab","Tiragolumab","Trastuzumab","Vemurafenib","Venclexta",
            "Vismodegib","Bevacizumab","Obinutuzumab","Rituximab",
            # AbbVie/Gilead/etc.
            "Teliso-V","Epcoritamab","Mirvetuximab soravtansine",
            # Daiichi ADCs
            "Trastuzumab deruxtecan","Datopotamab deruxtecan-dlnk","Patrituzumab deruxtecan","Ifinatamab deruxtecan","Raludotatug deruxtecan",
            # AZ/JNJ/MSD/etc. (selected)
            "Durvalumab","Osimertinib","Olaparib","Tremelimumab","Gefitinib","Moxetumomab pasudotox",
            "Bemarituzumab","Blinatumomab","Tarlatamab-dlle","Sotorasib",
            "Carfilzomib","Enfortumab vedotin","Gilteritinib","Zolbetuximab","Fezolinetant",
            "Darolutamide","Sevabertinib",
            # Merck MK names
            "Pembrolizumab","Belzutifan","Zilovertamab vedotin","Bomedemstat",
            # Additional common oncology drugs
            "Nivolumab","Ipilimumab","Avelumab","Cemiplimab","Doxorubicin","Cisplatin",
            "Carboplatin","Paclitaxel","Docetaxel","Gemcitabine","Fluorouracil",
            "Methotrexate","Cyclophosphamide","Etoposide","Imatinib","Sorafenib",
            "Sunitinib","Erlotinib","Gefitinib","Cetuximab","Panitumumab",
            "Lapatinib","Everolimus","Temsirolimus","Rituximab","Bevacizumab"
        ]
    
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
                    # Collect clinical trials using multiple strategies
                    all_data = []
                    
                    # 1. Company keyword searches (company + cancer/oncology/tumor)
                    keyword_data = await self.collectors[source].collect_company_keyword_trials(max_companies=5)
                    all_data.extend(keyword_data)
                    
                    # 2. Drug-specific searches
                    drug_names = self._get_drug_names_from_database(limit=20)
                    drug_data = await self.collectors[source].collect_company_drug_trials({
                        "General Search": drug_names  # Search for trials involving these drugs
                    })
                    all_data.extend(drug_data)
                    
                    data = all_data
                elif source == "fda":
                    data = await self.collectors[source].collect_data(['drug_approvals', 'adverse_events', 'surrogate_endpoints'])
                elif source == "company_websites":
                    data = await self.collectors["company_websites"].collect_data(max_companies=5)
                elif source == "drugs":
                    # Get drug names dynamically from database (increased limit for better coverage)
                    drug_names = self._get_drug_names_from_database(limit=25)
                    data = await self.collectors[source].collect_data(drug_names)
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