#!/usr/bin/env python3
"""
Complete Biopartnering Insights Pipeline with Change Detection

This script runs the entire pipeline end-to-end with intelligent change detection
to skip steps when no changes are detected, making it efficient for production use.
"""

import asyncio
import sys
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

# Add project root to path
sys.path.append('.')

from src.models.database import get_db
from src.models.entities import Drug, Document, ClinicalTrial, Company
from src.data_collection.orchestrator import DataCollectionOrchestrator
from src.processing.pipeline import run_processing
from src.processing.csv_export import export_drug_table, export_basic


class PipelineStateManager:
    """Manages pipeline state and change detection."""
    
    def __init__(self, state_file: str = "pipeline_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load pipeline state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
        return {
            "last_run": None,
            "data_collection": {},
            "processing": {},
            "exports": {},
            "database_stats": {}
        }
    
    def _save_state(self):
        """Save pipeline state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save state file: {e}")
    
    def get_database_hash(self) -> str:
        """Generate hash of current database state."""
        db = get_db()
        try:
            # Get counts and last update times
            stats = {
                "companies": db.query(Company).count(),
                "drugs": db.query(Drug).count(),
                "documents": db.query(Document).count(),
                "trials": db.query(ClinicalTrial).count(),
                "last_document": db.query(Document).order_by(Document.created_at.desc()).first(),
                "last_drug": db.query(Drug).order_by(Drug.created_at.desc()).first(),
            }
            
            # Create hash from stats
            stats_str = json.dumps(stats, default=str, sort_keys=True)
            return hashlib.md5(stats_str.encode()).hexdigest()
        finally:
            db.close()
    
    def has_data_changed(self, step: str) -> bool:
        """Check if data has changed since last run for a specific step."""
        current_hash = self.get_database_hash()
        last_hash = self.state.get("database_stats", {}).get("hash")
        
        if last_hash != current_hash:
            logger.info(f"Data change detected for step: {step}")
            return True
        
        # Check if enough time has passed (force refresh every 24 hours)
        last_run = self.state.get("last_run")
        if last_run:
            last_run_time = datetime.fromisoformat(last_run)
            if (datetime.now() - last_run_time).total_seconds() > 86400:  # 24 hours
                logger.info(f"Time-based refresh triggered for step: {step}")
                return True
        
        logger.info(f"No changes detected for step: {step}")
        return False
    
    def update_step_state(self, step: str, success: bool, details: Dict[str, Any] = None):
        """Update state for a specific step."""
        self.state["last_run"] = datetime.now().isoformat()
        self.state[step] = {
            "last_run": datetime.now().isoformat(),
            "success": success,
            "details": details or {}
        }
        self.state["database_stats"]["hash"] = self.get_database_hash()
        self._save_state()


class CompletePipeline:
    """Complete pipeline with change detection and intelligent skipping."""
    
    def __init__(self):
        self.state_manager = PipelineStateManager()
        self.orchestrator = DataCollectionOrchestrator()
    
    async def run_data_collection(self) -> Dict[str, int]:
        """Run data collection with change detection."""
        logger.info("=== DATA COLLECTION PHASE ===")
        
        # Check if we need to run data collection
        if not self.state_manager.has_data_changed("data_collection"):
            logger.info("⏭️  Skipping data collection - no changes detected")
            return {"skipped": True}
        
        try:
            # Run data collection
            sources = ["clinical_trials", "fda", "company_websites", "drugs"]
            results = await self.orchestrator.run_full_collection(sources)
            
            # Update state
            self.state_manager.update_step_state("data_collection", True, results)
            
            logger.info(f"✅ Data collection completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Data collection failed: {e}")
            self.state_manager.update_step_state("data_collection", False, {"error": str(e)})
            raise
    
    def run_processing(self) -> Dict[str, int]:
        """Run processing pipeline with change detection."""
        logger.info("=== PROCESSING PHASE ===")
        
        # Check if we need to run processing
        if not self.state_manager.has_data_changed("processing"):
            logger.info("⏭️  Skipping processing - no changes detected")
            return {"skipped": True}
        
        try:
            # Run processing
            db = get_db()
            try:
                results = run_processing(db)
                logger.info(f"✅ Processing completed: {results}")
                
                # Update state
                self.state_manager.update_step_state("processing", True, results)
                return results
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            self.state_manager.update_step_state("processing", False, {"error": str(e)})
            raise
    
    def run_exports(self) -> Dict[str, str]:
        """Run CSV exports with change detection."""
        logger.info("=== EXPORT PHASE ===")
        
        # Check if we need to run exports
        if not self.state_manager.has_data_changed("exports"):
            logger.info("⏭️  Skipping exports - no changes detected")
            return {"skipped": True}
        
        try:
            # Ensure outputs directory exists
            Path("outputs").mkdir(exist_ok=True)
            
            # Run exports
            db = get_db()
            try:
                # Export drug table
                drug_file = "outputs/biopharma_drugs.csv"
                export_drug_table(db, drug_file)
                logger.info(f"✅ Drug table exported: {drug_file}")
                
                # Export basic data
                basic_file = "outputs/basic_export.csv"
                export_basic(db, basic_file)
                logger.info(f"✅ Basic data exported: {basic_file}")
                
                # Update state
                results = {
                    "drug_table": drug_file,
                    "basic_export": basic_file,
                    "timestamp": datetime.now().isoformat()
                }
                self.state_manager.update_step_state("exports", True, results)
                return results
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            self.state_manager.update_step_state("exports", False, {"error": str(e)})
            raise
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get summary of pipeline execution."""
        db = get_db()
        try:
            stats = {
                "companies": db.query(Company).count(),
                "drugs": db.query(Drug).count(),
                "documents": db.query(Document).count(),
                "clinical_trials": db.query(ClinicalTrial).count(),
                "last_run": self.state_manager.state.get("last_run"),
                "steps_completed": list(self.state_manager.state.keys())
            }
            return stats
        finally:
            db.close()
    
    async def run_complete_pipeline(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Run the complete pipeline with intelligent skipping."""
        logger.info("🚀 Starting Complete Biopartnering Insights Pipeline")
        logger.info(f"Force refresh: {force_refresh}")
        
        if force_refresh:
            logger.info("🔄 Force refresh enabled - running all steps")
            # Clear state to force all steps
            self.state_manager.state = {
                "last_run": None,
                "data_collection": {},
                "processing": {},
                "exports": {},
                "database_stats": {}
            }
        
        start_time = datetime.now()
        results = {
            "start_time": start_time.isoformat(),
            "steps": {},
            "summary": {}
        }
        
        try:
            # Step 1: Data Collection
            logger.info("📊 Step 1: Data Collection")
            collection_results = await self.run_data_collection()
            results["steps"]["data_collection"] = collection_results
            
            # Step 2: Processing
            logger.info("⚙️  Step 2: Processing")
            processing_results = self.run_processing()
            results["steps"]["processing"] = processing_results
            
            # Step 3: Exports
            logger.info("📤 Step 3: Exports")
            export_results = self.run_exports()
            results["steps"]["exports"] = export_results
            
            # Get final summary
            results["summary"] = self.get_pipeline_summary()
            results["end_time"] = datetime.now().isoformat()
            results["duration_seconds"] = (datetime.now() - start_time).total_seconds()
            
            logger.info("🎉 Complete pipeline execution finished successfully!")
            logger.info(f"⏱️  Total duration: {results['duration_seconds']:.2f} seconds")
            
            return results
            
        except Exception as e:
            logger.error(f"💥 Pipeline execution failed: {e}")
            results["error"] = str(e)
            results["end_time"] = datetime.now().isoformat()
            raise


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete Biopartnering Insights Pipeline")
    parser.add_argument("--force", action="store_true", help="Force refresh all steps")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    # Run pipeline
    pipeline = CompletePipeline()
    
    try:
        results = await pipeline.run_complete_pipeline(force_refresh=args.force)
        
        # Print summary
        print("\n" + "="*60)
        print("📊 PIPELINE EXECUTION SUMMARY")
        print("="*60)
        print(f"Start Time: {results['start_time']}")
        print(f"End Time: {results['end_time']}")
        print(f"Duration: {results['duration_seconds']:.2f} seconds")
        print()
        
        print("📈 Database Statistics:")
        summary = results['summary']
        print(f"  Companies: {summary['companies']}")
        print(f"  Drugs: {summary['drugs']}")
        print(f"  Documents: {summary['documents']}")
        print(f"  Clinical Trials: {summary['clinical_trials']}")
        print()
        
        print("✅ Steps Completed:")
        for step, result in results['steps'].items():
            if result.get('skipped'):
                print(f"  {step}: ⏭️  SKIPPED (no changes)")
            else:
                print(f"  {step}: ✅ COMPLETED")
        
        print("\n🎉 Pipeline execution completed successfully!")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
