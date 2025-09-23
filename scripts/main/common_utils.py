#!/usr/bin/env python3
"""
Common utilities for pipeline scripts.
Consolidates duplicate functionality across different pipeline runners.
"""

import signal
import sys
from pathlib import Path
from loguru import logger


class SignalHandler:
    """Common signal handling for graceful shutdown."""
    
    def __init__(self):
        self.running = True
        self.current_task = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        if self.current_task and not self.current_task.done():
            logger.info("Cancelling current pipeline run...")
            self.current_task.cancel()
    
    def set_current_task(self, task):
        """Set the current running task for cancellation."""
        self.current_task = task


def setup_production_logging():
    """Setup comprehensive logging for production scripts."""
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Configure loguru
    logger.remove()  # Remove default handler
    
    # Console logging
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # File logging
    logger.add(
        "logs/pipeline.log",
        level="DEBUG",
        rotation="1 week",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        compression="zip"
    )
    
    # Error logging
    logger.add(
        "logs/errors.log",
        level="ERROR",
        rotation="1 week",
        retention="3 months",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        compression="zip"
    )


def setup_basic_logging():
    """Setup basic logging for simple scripts."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    )


# Data Collection Common Utilities

import requests
import hashlib
import re
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime


class HTTPClient:
    """Common HTTP client for data collection with retry logic and error handling."""
    
    def __init__(self, timeout: int = 30, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BiopartneringInsights/1.0)'
        })
    
    def make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and error handling."""
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == self.retries - 1:
                    logger.error(f"All {self.retries} attempts failed for {url}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None


def generate_content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def clean_drug_name(name: str) -> str:
    """Clean and normalize drug names."""
    if not name:
        return ""
    
    # Remove common prefixes and suffixes
    name = re.sub(r'^(Drug Profile:|Generic Name:|Brand Name:)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(.*?\)$', '', name)  # Remove trailing parenthetical info
    name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
    name = name.strip()
    
    return name


def validate_drug_name(name: str) -> bool:
    """Validate if a name is likely a drug name."""
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
    
    return True


def clean_company_name(name: str) -> str:
    """Clean and normalize company names."""
    if not name:
        return ""
    
    # Remove common suffixes
    name = re.sub(r'\s+(Inc|Corp|Corporation|Company|Co|Ltd|Limited|Pharmaceuticals|Pharma|Biotech|Biotechnology)\.?$', '', name, flags=re.IGNORECASE)
    
    # Remove common prefixes
    name = re.sub(r'^(The|A|An)\s+', '', name, flags=re.IGNORECASE)
    
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def validate_company_name(name: str) -> bool:
    """Validate if a name is likely a company name."""
    if not name or len(name) < 2 or len(name) > 100:
        return False
    
    # Filter out common false positives
    false_positives = {
        'the', 'and', 'or', 'for', 'with', 'by', 'fda', 'drug', 'label', 'api', 
        'com', 'www', 'http', 'https', 'the drug', 'drug company', 'drug label', 
        'drug api', 'unknown', 'n/a', 'na', 'tbd', 'pending'
    }
    
    if name.lower() in false_positives:
        return False
    
    return True


def extract_nct_id(text: str) -> Optional[str]:
    """Extract NCT ID from text."""
    pattern = r'NCT\d{8}'
    match = re.search(pattern, text)
    return match.group() if match else None


def extract_all_nct_ids(text: str) -> List[str]:
    """Extract all NCT IDs from text."""
    pattern = r'NCT\d{8}'
    return re.findall(pattern, text)


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string with error handling."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default


def format_timestamp(timestamp: Optional[datetime] = None) -> str:
    """Format timestamp for consistent logging."""
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def log_collection_progress(current: int, total: int, item_name: str = "item") -> None:
    """Log collection progress with percentage."""
    percentage = (current / total) * 100 if total > 0 else 0
    logger.info(f"Progress: {current}/{total} {item_name}s ({percentage:.1f}%)")
