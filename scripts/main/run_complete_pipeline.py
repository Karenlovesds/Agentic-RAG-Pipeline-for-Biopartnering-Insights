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
from src.processing.csv_export import export_drug_table
from sqlalchemy.orm import Session


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
            "maintenance": {},
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
    
    async def run_maintenance(self) -> Dict[str, Any]:
        """Run database maintenance with change detection."""
        logger.info("=== MAINTENANCE PHASE ===")
        
        # Check if we need to run maintenance
        if not self.state_manager.has_data_changed("maintenance"):
            logger.info("⏭️  Skipping maintenance - no changes detected")
            return {"skipped": True}
        
        try:
            # Run maintenance
            from scripts.maintenance.maintenance_orchestrator import run_maintenance
            results = await run_maintenance()
            logger.info(f"✅ Maintenance completed: {results['successful_tasks']}/{results['total_tasks']} tasks successful")
            
            # Update state
            self.state_manager.update_step_state("maintenance", True, results)
            return results
            
        except Exception as e:
            logger.error(f"❌ Maintenance failed: {e}")
            self.state_manager.update_step_state("maintenance", False, {"error": str(e)})
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
                # Export drug table (canonical export - replaces basic_export)
                drug_file = "outputs/biopharma_drugs.csv"
                export_drug_table(db, drug_file)
                logger.info(f"✅ Drug table exported: {drug_file}")
                
                # Generate drug collection summary
                summary_file = "outputs/drug_collection_summary.txt"
                self._generate_drug_summary(db, summary_file)
                logger.info(f"✅ Drug collection summary generated: {summary_file}")
                
                # Update state
                results = {
                    "drug_table": drug_file,
                    "basic_export": drug_file,  # basic_export replaced by biopharma_drugs.csv
                    "drug_summary": summary_file,
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
    
    def _generate_drug_summary(self, db: Session, output_path: str):
        """Generate drug collection summary with improved validation."""
        try:
            # Get all companies
            companies = db.query(Company).all()
            company_drugs = {}
            
            for company in companies:
                # Get drugs for this company
                drugs = db.query(Drug).filter(Drug.company_id == company.id).all()
                
                # Filter drugs using improved validation
                valid_drugs = []
                for drug in drugs:
                    if self._is_valid_drug_name(drug.generic_name):
                        valid_drugs.append(drug.generic_name)
                
                company_drugs[company.name] = valid_drugs
            
            # Get total counts
            total_drugs = sum(len(drugs) for drugs in company_drugs.values())
            total_trials = db.query(ClinicalTrial).count()
            total_documents = db.query(Document).count()
            
            # Count documents by type
            fda_docs = db.query(Document).filter(Document.source_type.like('%fda%')).count()
            clinical_trial_docs = db.query(Document).filter(Document.source_type.like('%clinical%')).count()
            company_docs = db.query(Document).filter(Document.source_type.like('%company%')).count()
            
            # Generate summary
            summary_lines = [
                "Comprehensive Drug Collection Summary",
                "========================================",
                "",
                f"Pipeline Drugs Found: {total_drugs}",
                f"FDA Documents: {fda_docs}",
                f"Clinical Trial Documents: {clinical_trial_docs}",
                f"Company Documents: {company_docs}",
                f"Clinical Trials (Extracted): {total_trials}",
                f"Total Documents: {total_documents}",
                f"Success: True",
                "",
                "Pipeline Drugs by Company:",
                "==============================",
                ""
            ]
            
            for company_name, drugs in company_drugs.items():
                if drugs:
                    summary_lines.append(f"{company_name}:")
                    summary_lines.append("-" * (len(company_name) + 1))
                    for i, drug in enumerate(sorted(drugs), 1):
                        summary_lines.append(f"  {i:3d}. {drug}")
                    summary_lines.append("")
            
            # Add summary by company
            summary_lines.extend([
                "",
                "Summary by Company:",
                "===================="
            ])
            
            for company_name, drugs in company_drugs.items():
                summary_lines.append(f"  {company_name}: {len(drugs)} drugs")
            
            # Write to file
            with open(output_path, 'w') as f:
                f.write('\n'.join(summary_lines))
                
        except Exception as e:
            logger.error(f"Failed to generate drug summary: {e}")
            raise
    
    def _is_valid_drug_name(self, name: str) -> bool:
        """Improved drug name validation."""
        import re
        
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        # Filter out clinical trial IDs
        if re.match(r'^NCT\d+', name.upper()):
            return False
        
        # Filter out study names and codes
        if re.match(r'^(Lung|Breast|PanTumor|Prostate|GI|Ovarian|Esophageal)\d+$', name):
            return False
        
        # Filter out generic protein/antibody terms
        generic_terms = {
            'ig', 'igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga', 'parp1', 'parp2', 'parp3',
            'tyk2', 'cdh6', 'ror1', 'her3', 'trop2', 'pcsk9', 'ov65'
        }
        
        if name.lower() in generic_terms:
            return False
        
        # Filter out common false positives
        false_positives = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'must', 'shall', 'accept', 'except', 'decline', 'drug', 'conjugate',
            'small', 'molecule', 'therapeutic', 'protein', 'bispecific', 'antibody',
            'dose', 'combination', 'acquired', 'noted', 'except', 'as', 'was', 'is',
            'being', 'an', 'a', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'
        }
        
        if name.lower() in false_positives:
            return False
        
        # Filter out incomplete drug names (ending with common words)
        incomplete_endings = [' is', ' was', ' being', ' an', ' a', ' the', ' and', ' or']
        if any(name.endswith(ending) for ending in incomplete_endings):
            return False
        
        # Filter out descriptive phrases
        descriptive_phrases = ['drug conjugate', 'small molecule', 'therapeutic protein', 'bispecific antibody', 'peptide']
        if any(phrase in name.lower() for phrase in descriptive_phrases):
            return False
        
        # Positive indicators for actual drug names
        drug_indicators = [
            # Monoclonal antibodies
            name.lower().endswith(('mab', 'zumab', 'ximab')),
            # Kinase inhibitors
            name.lower().endswith(('nib', 'tinib')),
            # Fusion proteins
            name.lower().endswith('cept'),
            # PARP inhibitors
            name.lower().endswith('parib'),
            # CDK inhibitors
            name.lower().endswith('ciclib'),
            # Specific known drugs
            name.lower() in {
                'pembrolizumab', 'nivolumab', 'sotatercept', 'patritumab', 'sacituzumab',
                'zilovertamab', 'nemtabrutinib', 'quavonlimab', 'clesrovimab', 'ifinatamab',
                'bezlotoxumab', 'ipilimumab', 'relatlimab', 'enasicon', 'dasatinib',
                'repotrectinib', 'elotuzumab', 'belatacept', 'fedratinib', 'luspatercept',
                'abatacept', 'deucravacitinib', 'olaparib', 'palbociclib', 'rucaparib',
                'niraparib', 'talazoparib', 'ribociclib', 'abemaciclib'
            },
            # Merck drug codes
            re.match(r'^mk-\d+', name.lower()),
            # Roche drug codes
            re.match(r'^rg\d+', name.lower()),
        ]
        
        return any(drug_indicators)

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
                "maintenance": {},
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
            # Step 1: Maintenance
            logger.info("🔧 Step 1: Database Maintenance")
            maintenance_results = await self.run_maintenance()
            results["steps"]["maintenance"] = maintenance_results
            
            # Step 2: Data Collection
            logger.info("📊 Step 2: Data Collection")
            collection_results = await self.run_data_collection()
            results["steps"]["data_collection"] = collection_results
            
            # Step 3: Processing
            logger.info("⚙️  Step 3: Processing")
            processing_results = self.run_processing()
            results["steps"]["processing"] = processing_results
            
            # Step 4: Exports
            logger.info("📤 Step 4: Exports")
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
