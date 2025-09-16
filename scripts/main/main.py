"""Main application entry point for Biopartnering Insights Pipeline."""

import asyncio
import sys
from pathlib import Path
from loguru import logger
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.models.database import create_tables
from src.data_collection.orchestrator import DataCollectionOrchestrator
from config.config import settings


def setup_logging():
    """Setup logging configuration."""
    logger.remove()  # Remove default handler
    logger.add(
        settings.log_file,
        level=settings.log_level,
        rotation="1 week",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    )
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )


async def run_data_collection():
    """Run the data collection pipeline."""
    logger.info("Starting Biopartnering Insights data collection pipeline")
    
    # Create database tables
    create_tables()
    logger.info("Database tables created/verified")
    
    # Initialize orchestrator
    orchestrator = DataCollectionOrchestrator()
    
    # Run data collection for all sources
    sources = ["clinical_trials", "fda", "company_websites", "drugs"]
    results = await orchestrator.run_full_collection(sources)
    
    logger.info(f"Data collection completed: {results}")
    return results


def main():
    """Main application entry point."""
    setup_logging()
    
    logger.info("Biopartnering Insights Pipeline starting...")
    
    # Check if running as Streamlit app
    if len(sys.argv) > 1 and sys.argv[1] == "streamlit":
        logger.info("Starting Streamlit UI...")
        # Streamlit app will be started separately
        return
    
    # Run data collection
    try:
        results = asyncio.run(run_data_collection())
        print(f"Data collection completed successfully: {results}")
    except Exception as e:
        logger.error(f"Error in main application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
