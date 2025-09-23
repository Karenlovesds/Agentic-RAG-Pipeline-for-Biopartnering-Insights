#!/usr/bin/env python3
"""
Maintenance Orchestrator for Biopartnering Insights Pipeline

This module coordinates all database maintenance tasks that should be run
before data collection to ensure data quality and consistency.
"""

import sys
import os
import asyncio
from typing import Dict, Any, List
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.database import get_db, engine, Base
from src.models.entities import Drug, Company, ClinicalTrial, Document, Target, Indication, DrugTarget, DrugIndication


class MaintenanceOrchestrator:
    """Orchestrates database maintenance tasks."""
    
    def __init__(self):
        self.maintenance_tasks = [
            {
                "name": "database_initialization",
                "description": "Initialize database tables",
                "function": self._initialize_database_async,
                "enabled": True
            },
            {
                "name": "drug_capitalization",
                "description": "Fix drug name capitalization",
                "function": self._fix_drug_capitalization,
                "enabled": True
            },
            {
                "name": "drug_validation", 
                "description": "Fix drug validation issues",
                "function": self._fix_drug_validation,
                "enabled": True
            },
            {
                "name": "drug_deduplication",
                "description": "Remove duplicate drugs",
                "function": self._fix_drug_deduplication,
                "enabled": True
            }
        ]
    
    async def run_maintenance(self, tasks: List[str] = None) -> Dict[str, Any]:
        """Run maintenance tasks."""
        logger.info("🔧 Starting database maintenance...")
        
        results = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "task_results": {}
        }
        
        # Filter tasks if specific ones are requested
        tasks_to_run = self.maintenance_tasks
        if tasks:
            tasks_to_run = [task for task in self.maintenance_tasks if task["name"] in tasks]
        
        # Run enabled tasks
        enabled_tasks = [task for task in tasks_to_run if task["enabled"]]
        results["total_tasks"] = len(enabled_tasks)
        
        for task in enabled_tasks:
            try:
                logger.info(f"Running maintenance task: {task['description']}")
                task_result = await task["function"]()
                results["task_results"][task["name"]] = {
                    "success": True,
                    "result": task_result
                }
                results["successful_tasks"] += 1
                logger.info(f"✅ {task['description']} completed successfully")
                
            except Exception as e:
                logger.error(f"❌ {task['description']} failed: {e}")
                results["task_results"][task["name"]] = {
                    "success": False,
                    "error": str(e)
                }
                results["failed_tasks"] += 1
        
        logger.info(f"🔧 Maintenance completed: {results['successful_tasks']}/{results['total_tasks']} tasks successful")
        return results
    
    async def _fix_drug_capitalization(self) -> Dict[str, Any]:
        """Fix drug name capitalization without removing duplicates."""
        db = get_db()
        
        try:
            # Get all drugs
            drugs = db.query(Drug).all()
            logger.info(f"Found {len(drugs)} total drugs in database")
            
            # Standardize capitalization for all drugs
            updated_count = 0
            for drug in drugs:
                if drug.generic_name:
                    original_name = drug.generic_name
                    drug.generic_name = drug.generic_name.title()  # Standardize capitalization
                    if original_name != drug.generic_name:
                        updated_count += 1
            
            # Commit changes
            db.commit()
            logger.info(f"Updated capitalization for {updated_count} drugs")
            
            return {
                "total_drugs": len(drugs),
                "updated_drugs": updated_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error fixing drug capitalization: {e}")
            raise
        finally:
            db.close()
    
    async def _fix_drug_validation(self) -> Dict[str, Any]:
        """Fix drug validation issues."""
        db = get_db()
        
        try:
            # Get all drugs
            drugs = db.query(Drug).all()
            logger.info(f"Found {len(drugs)} total drugs in database")
            
            # Remove drugs that don't meet validation criteria
            removed_count = 0
            drugs_to_remove = []
            
            for drug in drugs:
                if not self._is_valid_drug_name(drug.generic_name):
                    drugs_to_remove.append(drug)
                    removed_count += 1
            
            # Remove invalid drugs
            for drug in drugs_to_remove:
                db.delete(drug)
            
            # Commit changes
            db.commit()
            logger.info(f"Removed {removed_count} invalid drugs")
            
            return {
                "total_drugs": len(drugs),
                "removed_drugs": removed_count,
                "remaining_drugs": len(drugs) - removed_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error fixing drug validation: {e}")
            raise
        finally:
            db.close()
    
    async def _fix_drug_deduplication(self) -> Dict[str, Any]:
        """Remove duplicate drugs, keeping the one with most complete data."""
        db = get_db()
        
        try:
            # Get all drugs
            drugs = db.query(Drug).all()
            logger.info(f"Found {len(drugs)} total drugs in database")
            
            # Group drugs by generic name (case-insensitive)
            drug_groups = {}
            for drug in drugs:
                key = drug.generic_name.lower() if drug.generic_name else ""
                if key not in drug_groups:
                    drug_groups[key] = []
                drug_groups[key].append(drug)
            
            # Process each group
            removed_count = 0
            for group_name, group_drugs in drug_groups.items():
                if len(group_drugs) > 1:
                    # Keep the drug with most complete data
                    primary_drug = max(group_drugs, key=lambda d: self._get_drug_completeness_score(d))
                    primary_drug.generic_name = primary_drug.generic_name.title()  # Standardize capitalization
                    
                    # Remove duplicates
                    for drug in group_drugs:
                        if drug.id != primary_drug.id:
                            db.delete(drug)
                            removed_count += 1
            
            # Standardize capitalization for all remaining drugs
            remaining_drugs = db.query(Drug).all()
            for drug in remaining_drugs:
                if drug.generic_name:
                    drug.generic_name = drug.generic_name.title()
            
            # Commit changes
            db.commit()
            logger.info(f"Removed {removed_count} duplicate drugs")
            
            return {
                "total_drugs": len(drugs),
                "removed_duplicates": removed_count,
                "remaining_drugs": len(remaining_drugs)
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error fixing drug deduplication: {e}")
            raise
        finally:
            db.close()
    
    def _is_valid_drug_name(self, name: str) -> bool:
        """Check if a drug name is valid."""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        # Filter out clinical trial IDs
        import re
        if re.match(r'^NCT\d+', name.upper()):
            return False
        
        # Filter out study names and codes
        if re.match(r'^[A-Z]{2,}\d+', name.upper()):
            return False
        
        # Filter out generic terms
        generic_terms = ['study', 'trial', 'phase', 'protocol', 'program', 'project']
        if any(term in name.lower() for term in generic_terms):
            return False
        
        # Filter out incomplete drug names
        if len(name.split()) == 1 and len(name) < 4:
            return False
        
        return True
    
    def _get_drug_completeness_score(self, drug: Drug) -> int:
        """Calculate completeness score for a drug (higher is better)."""
        score = 0
        
        if drug.generic_name:
            score += 1
        if drug.brand_name:
            score += 1
        if drug.drug_class:
            score += 1
        if drug.fda_approval_status:
            score += 1
        if drug.fda_approval_date:
            score += 1
        if drug.mechanism_of_action:
            score += 1
        if drug.nct_codes:
            score += 1
        if drug.rxnorm_id:
            score += 1
        
        return score
    
    def _initialize_database(self) -> Dict[str, Any]:
        """Initialize database tables."""
        try:
            logger.info("🗄️  Initializing database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created successfully")
            return {"success": True, "message": "Database tables initialized"}
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _initialize_database_async(self) -> Dict[str, Any]:
        """Async wrapper for database initialization."""
        return self._initialize_database()


async def run_maintenance(tasks: List[str] = None) -> Dict[str, Any]:
    """Run maintenance tasks."""
    orchestrator = MaintenanceOrchestrator()
    return await orchestrator.run_maintenance(tasks)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run database maintenance tasks")
    parser.add_argument("--tasks", nargs="+", 
                       choices=["drug_capitalization", "drug_validation", "drug_deduplication"],
                       help="Specific tasks to run (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    
    # Run maintenance
    results = asyncio.run(run_maintenance(args.tasks))
    
    print(f"\n🔧 Maintenance Results:")
    print(f"Total tasks: {results['total_tasks']}")
    print(f"Successful: {results['successful_tasks']}")
    print(f"Failed: {results['failed_tasks']}")
    
    for task_name, task_result in results['task_results'].items():
        status = "✅" if task_result['success'] else "❌"
        print(f"{status} {task_name}: {task_result}")
