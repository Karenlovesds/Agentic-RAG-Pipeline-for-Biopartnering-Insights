#!/usr/bin/env python3
"""
Clinical Trials Populator

This script populates the database with clinical trials data for drugs
from the ClinicalTrials.gov API.
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
from src.models.database import get_db
from src.models.entities import Drug, ClinicalTrial
from src.data_collection.clinical_trials_collector import ClinicalTrialsCollector

async def populate_clinical_trials():
    """Populate clinical trials for all drugs in the database."""
    logger.info("Starting clinical trials population...")
    
    db = get_db()
    
    try:
        # Get all drugs from database
        drugs = db.query(Drug).all()
        logger.info(f"Found {len(drugs)} drugs to process")
        
        if not drugs:
            logger.warning("No drugs found in database. Run data collection first.")
            return
        
        # Initialize clinical trials collector
        trials_collector = ClinicalTrialsCollector()
        
        # Process each drug
        for i, drug in enumerate(drugs, 1):
            logger.info(f"Processing drug {i}/{len(drugs)}: {drug.generic_name}")
            
            try:
                # Search for clinical trials
                trials_data = await trials_collector.search_trials(
                    condition=drug.generic_name,
                    max_results=50
                )
                
                if trials_data:
                    # Clear existing trials for this drug
                    db.query(ClinicalTrial).filter(ClinicalTrial.drug_id == drug.id).delete()
                    
                    # Add new trials
                    for trial_data in trials_data:
                        trial = ClinicalTrial(
                            drug_id=drug.id,
                            nct_id=trial_data.get('nct_id', ''),
                            title=trial_data.get('title', ''),
                            status=trial_data.get('status', ''),
                            phase=trial_data.get('phase', ''),
                            start_date=trial_data.get('start_date'),
                            completion_date=trial_data.get('completion_date'),
                            source='ClinicalTrials.gov'
                        )
                        db.add(trial)
                    
                    db.commit()
                    logger.info(f"Added {len(trials_data)} clinical trials for {drug.generic_name}")
                else:
                    logger.warning(f"No clinical trials found for {drug.generic_name}")
                    
            except Exception as e:
                logger.error(f"Error processing {drug.generic_name}: {e}")
                continue
        
        logger.info("Clinical trials population completed!")
        
    except Exception as e:
        logger.error(f"Error in clinical trials population: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(populate_clinical_trials())
