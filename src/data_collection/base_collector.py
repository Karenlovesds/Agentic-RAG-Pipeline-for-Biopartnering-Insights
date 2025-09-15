"""Base collector class for data collection from various sources."""

import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
import requests
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel

from ..models.entities import Document
from ..models.database import get_db


class CollectedData(BaseModel):
    """Model for collected data."""
    source_url: str
    title: Optional[str] = None
    content: str
    source_type: str
    metadata: Dict[str, Any] = {}


class BaseCollector(ABC):
    """Base class for data collectors."""
    
    def __init__(self, source_type: str, base_url: str):
        self.source_type = source_type
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BiopartneringInsights/1.0)'
        })
        
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _save_document(self, data: CollectedData) -> bool:
        """Save collected document to database."""
        try:
            db = next(get_db())
            
            # Check if document already exists
            existing_doc = db.query(Document).filter(
                Document.content_hash == self._generate_content_hash(data.content)
            ).first()
            
            if existing_doc:
                logger.info(f"Document already exists: {data.source_url}")
                return False
            
            # Create new document
            document = Document(
                source_url=data.source_url,
                title=data.title,
                content=data.content,
                content_hash=self._generate_content_hash(data.content),
                source_type=data.source_type,
                retrieval_date=datetime.utcnow()
            )
            
            db.add(document)
            db.commit()
            logger.info(f"Saved document: {data.source_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving document {data.source_url}: {e}")
            return False
        finally:
            db.close()
    
    async def _crawl_with_crawl4ai(self, url: str, extraction_strategy: Optional[LLMExtractionStrategy] = None) -> Optional[str]:
        """Crawl URL using crawl4ai."""
        try:
            async with AsyncWebCrawler(verbose=True) as crawler:
                result = await crawler.arun(
                    url=url,
                    extraction_strategy=extraction_strategy,
                    bypass_cache=True
                )
                
                if result.success:
                    return result.cleaned_html or result.html
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make HTTP request with error handling."""
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    @abstractmethod
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect data from the source. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into structured format. Must be implemented by subclasses."""
        pass
    
    async def run_collection(self, query_params: Optional[Dict[str, Any]] = None) -> int:
        """Run the complete data collection process."""
        logger.info(f"Starting data collection from {self.source_type}")
        
        try:
            # Collect data
            collected_data = await self.collect_data(query_params)
            logger.info(f"Collected {len(collected_data)} items from {self.source_type}")
            
            # Save to database
            saved_count = 0
            for data in collected_data:
                if self._save_document(data):
                    saved_count += 1
                
                # Rate limiting
                time.sleep(1.0)  # 1 second delay between requests
            
            logger.info(f"Saved {saved_count} new documents from {self.source_type}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error in data collection from {self.source_type}: {e}")
            return 0
