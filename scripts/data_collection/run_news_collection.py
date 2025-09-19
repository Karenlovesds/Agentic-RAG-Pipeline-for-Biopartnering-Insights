#!/usr/bin/env python3
"""
News Collection Script for Biopartnering Insights Pipeline

This script collects news and press release data from biopharmaceutical companies
to capture the latest drug developments, partnerships, and regulatory updates.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data_collection.company_website_collector import CompanyWebsiteCollector
from src.data_collection.orchestrator import DataCollectionOrchestrator
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_news_collection():
    """Run news collection for all companies."""
    try:
        logger.info("🚀 Starting news collection process...")
        
        # Initialize the company website collector
        collector = CompanyWebsiteCollector()
        
        # Collect news data from all companies
        logger.info("📰 Collecting news and press releases...")
        news_data = await collector.collect_news_data(max_companies=30)
        
        logger.info(f"✅ News collection completed!")
        logger.info(f"📊 Total news documents collected: {len(news_data)}")
        
        # Log summary of collected data
        for data in news_data:
            logger.info(f"📄 {data.title} - {len(data.content)} characters")
            if 'news_drugs_found' in data.metadata:
                logger.info(f"   💊 Drugs found: {data.metadata['news_drugs_found']}")
        
        return len(news_data)
        
    except Exception as e:
        logger.error(f"❌ Error in news collection: {e}")
        raise

async def run_full_collection_with_news():
    """Run full data collection including news."""
    try:
        logger.info("🚀 Starting full data collection with news...")
        
        # Initialize orchestrator
        orchestrator = DataCollectionOrchestrator(run_maintenance=True)
        
        # Run collection from all sources including company websites (which now includes news)
        sources = ["company_website", "fda", "clinical_trials", "drugs"]
        results = await orchestrator.run_full_collection(sources)
        
        logger.info("✅ Full collection with news completed!")
        logger.info(f"📊 Collection results: {results}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in full collection: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run news collection for biopharma companies")
    parser.add_argument("--news-only", action="store_true", help="Run only news collection")
    parser.add_argument("--full", action="store_true", help="Run full collection including news")
    parser.add_argument("--companies", type=int, default=30, help="Number of companies to process")
    
    args = parser.parse_args()
    
    if args.news_only:
        asyncio.run(run_news_collection())
    elif args.full:
        asyncio.run(run_full_collection_with_news())
    else:
        print("Please specify --news-only or --full")
        print("Example: python run_news_collection.py --news-only")
        print("Example: python run_news_collection.py --full")
