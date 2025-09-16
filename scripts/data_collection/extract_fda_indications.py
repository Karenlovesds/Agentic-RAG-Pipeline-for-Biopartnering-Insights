#!/usr/bin/env python3
"""
FDA Indications Extractor

This script extracts FDA-approved indications for drugs from the FDA database
and populates the database with structured indication data.
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
from src.models.database import get_db
from src.models.entities import Drug, Indication
from src.data_collection.fda_collector import FDACollector

async def extract_fda_indications():
    """Extract FDA indications for all drugs in the database."""
    logger.info("Starting FDA indications extraction...")
    
    db = get_db()
    
    try:
        # Get all drugs from database
        drugs = db.query(Drug).all()
        logger.info(f"Found {len(drugs)} drugs to process")
        
        if not drugs:
            logger.warning("No drugs found in database. Run data collection first.")
            return
        
        # Initialize FDA collector
        fda_collector = FDACollector()
        
        # Process each drug
        for i, drug in enumerate(drugs, 1):
            logger.info(f"Processing drug {i}/{len(drugs)}: {drug.generic_name}")
            
            try:
                # Extract FDA data for this drug
                fda_data = await fda_collector.collect_drug_data(drug.generic_name)
                
                if fda_data and 'indications' in fda_data:
                    # Clear existing indications
                    db.query(Indication).filter(Indication.drug_id == drug.id).delete()
                    
                    # Add new indications
                    for indication_data in fda_data['indications']:
                        indication = Indication(
                            drug_id=drug.id,
                            indication=indication_data.get('indication', ''),
                            approval_status=indication_data.get('approved', False),
                            approval_date=indication_data.get('approval_date'),
                            source='FDA'
                        )
                        db.add(indication)
                    
                    db.commit()
                    logger.info(f"Added {len(fda_data['indications'])} indications for {drug.generic_name}")
                else:
                    logger.warning(f"No FDA data found for {drug.generic_name}")
                    
            except Exception as e:
                logger.error(f"Error processing {drug.generic_name}: {e}")
                continue
        
        logger.info("FDA indications extraction completed!")
        
    except Exception as e:
        logger.error(f"Error in FDA indications extraction: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(extract_fda_indications())
