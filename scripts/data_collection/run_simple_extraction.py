#!/usr/bin/env python3
"""
Simple Entity Extraction

This script runs simple entity extraction on all documents in the database
using basic NLP techniques to extract drugs and companies.
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
from src.models.database import get_db
from src.models.entities import Document
from src.processing.simple_entity_extractor import SimpleEntityExtractor

async def run_simple_extraction():
    """Run simple entity extraction on all documents."""
    logger.info("Starting simple entity extraction...")
    
    db = get_db()
    
    try:
        # Get all documents from database
        documents = db.query(Document).all()
        logger.info(f"Found {len(documents)} documents to process")
        
        if not documents:
            logger.warning("No documents found in database. Run data collection first.")
            return
        
        # Initialize simple entity extractor
        extractor = SimpleEntityExtractor()
        
        # Process each document
        for i, doc in enumerate(documents, 1):
            logger.info(f"Processing document {i}/{len(documents)}: {doc.title}")
            
            try:
                # Extract entities from document
                entities = await extractor.extract_entities(doc.content)
                
                if entities:
                    # Save entities to database
                    await extractor.save_entities(entities, doc.id)
                    logger.info(f"Extracted {len(entities)} entities from {doc.title}")
                else:
                    logger.warning(f"No entities found in {doc.title}")
                    
            except Exception as e:
                logger.error(f"Error processing {doc.title}: {e}")
                continue
        
        logger.info("Simple entity extraction completed!")
        
    except Exception as e:
        logger.error(f"Error in simple extraction: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_simple_extraction())
