#!/usr/bin/env python3
"""
Script to improve company website scraping to extract actual drug names.
"""

import asyncio
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from src.models.database import get_db
from src.models.entities import Drug, Company, Document
from config.config import get_target_companies

async def test_improved_scraping():
    """Test improved scraping on a few company websites."""
    print("🔧 Testing improved company website scraping...")
    
    # Test on a few companies
    test_companies = ["Merck & Co.", "Bristol Myers Squibb", "Roche/Genentech"]
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        for company in test_companies:
            print(f"\n🏢 Testing {company}...")
            
            # Get company website
            website_url = get_company_website(company)
            if not website_url:
                print(f"  ❌ No website found for {company}")
                continue
            
            # Test different scraping strategies
            await test_scraping_strategies(crawler, company, website_url)

def get_company_website(company_name: str) -> str:
    """Get company website URL."""
    company_mapping = {
        "Merck & Co.": "https://www.merck.com",
        "Bristol Myers Squibb": "https://www.bms.com", 
        "Roche/Genentech": "https://www.gene.com",
        "Pfizer": "https://www.pfizer.com",
        "Novartis": "https://www.novartis.com",
        "AstraZeneca": "https://www.astrazeneca.com",
        "AbbVie": "https://www.abbvie.com",
        "Sanofi": "https://www.sanofi.com",
        "Eli Lilly": "https://www.lilly.com",
        "GSK": "https://www.gsk.com",
        "Bayer": "https://www.bayer.com",
        "Amgen": "https://www.amgen.com",
        "Takeda": "https://www.takeda.com",
        "Boehringer Ingelheim": "https://www.boehringer-ingelheim.com",
        "Novo Nordisk": "https://www.novonordisk.com",
        "Moderna": "https://www.modernatx.com",
        "Regeneron": "https://www.regeneron.com",
        "CSL Behring": "https://www.csl.com",
        "Biogen": "https://www.biogen.com",
        "Vertex": "https://www.vrtx.com",
        "Gilead Sciences": "https://www.gilead.com",
        "Seagen (Pfizer)": "https://www.seagen.com",
        "BeiGene": "https://www.beigene.com",
        "Incyte": "https://www.incyte.com",
        "Alnylam": "https://www.alnylam.com",
        "Ipsen": "https://www.ipsen.com",
        "UCB": "https://www.ucb.com",
        "Daiichi Sankyo": "https://www.daiichisankyo.com",
        "Servier": "https://servier.com"
    }
    return company_mapping.get(company_name)

async def test_scraping_strategies(crawler, company: str, base_url: str):
    """Test different scraping strategies."""
    
    # Strategy 1: Try to find pipeline pages
    pipeline_urls = await find_pipeline_pages(crawler, base_url)
    print(f"  📄 Found {len(pipeline_urls)} pipeline pages")
    
    for url in pipeline_urls[:2]:  # Test first 2 pages
        print(f"    Testing: {url}")
        
        # Try different extraction strategies
        strategies = [
            ("NoExtractionStrategy", "Raw HTML"),
            ("LLMExtractionStrategy", "LLM Extraction"),
            ("JsonCssExtractionStrategy", "JSON CSS Extraction")
        ]
        
        for strategy_name, strategy_desc in strategies:
            try:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=10,
                    extraction_strategy=strategy_name,
                    bypass_cache=True
                )
                
                if result.success:
                    # Extract drug names from content
                    drug_names = extract_drug_names_from_content(result.cleaned_html)
                    print(f"      {strategy_desc}: Found {len(drug_names)} potential drugs")
                    if drug_names:
                        print(f"        Sample drugs: {list(drug_names)[:5]}")
                else:
                    print(f"      {strategy_desc}: Failed")
                    
            except Exception as e:
                print(f"      {strategy_desc}: Error - {e}")

async def find_pipeline_pages(crawler, base_url: str) -> list:
    """Find pipeline-related pages."""
    pipeline_keywords = ["pipeline", "development", "research", "programs", "portfolio"]
    found_urls = []
    
    # Common pipeline URL patterns
    common_paths = [
        "/pipeline",
        "/research",
        "/development", 
        "/research-development",
        "/our-pipeline",
        "/development-pipeline",
        "/research/pipeline",
        "/pipeline/development"
    ]
    
    for path in common_paths:
        url = base_url.rstrip('/') + path
        try:
            result = await crawler.arun(url=url, bypass_cache=True)
            if result.success and result.cleaned_html:
                # Check if page contains pipeline-related content
                content_lower = result.cleaned_html.lower()
                if any(keyword in content_lower for keyword in pipeline_keywords):
                    found_urls.append(url)
        except:
            continue
    
    return found_urls

def extract_drug_names_from_content(html_content: str) -> set:
    """Extract potential drug names from HTML content."""
    drug_names = set()
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text content
    text = soup.get_text()
    
    # Look for drug name patterns
    drug_patterns = [
        # Monoclonal antibodies
        r'\b[A-Z][a-z]+mab\b',
        r'\b[A-Z][a-z]+zumab\b', 
        r'\b[A-Z][a-z]+ximab\b',
        # Kinase inhibitors
        r'\b[A-Z][a-z]+nib\b',
        r'\b[A-Z][a-z]+tinib\b',
        # Fusion proteins
        r'\b[A-Z][a-z]+cept\b',
        # CAR-T therapies
        r'\b[A-Z][a-z]+leucel\b',
        # ADCs
        r'\b[A-Z][a-z]+\s+Deruxtecan\b',
        r'\b[A-Z][a-z]+\s+Vedotin\b',
        r'\b[A-Z][a-z]+\s+Tirumotecan\b',
        # Known drug names
        r'\b(Pembrolizumab|Nivolumab|Trastuzumab|Atezolizumab|Ipilimumab|Elotuzumab|Avelumab|Blinatumomab|Dupilumab|Ruxolitinib|Sotatercept|Nemtabrutinib|Quavonlimab|Clesrovimab|Bezlotoxumab|Patritumab|Sacituzumab|Zilovertamab|Ifinatamab|Tisagenlecleucel|Yescarta|Kymriah|Carvykti|Abecma|Breyanzi)\b'
    ]
    
    for pattern in drug_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            drug_name = match.strip()
            if len(drug_name) >= 3 and len(drug_name) <= 50:
                drug_names.add(drug_name.title())
    
    # Also look for drug names in specific HTML elements
    drug_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
    for element in drug_elements:
        element_text = element.get_text().strip()
        if element_text and len(element_text) <= 50:
            # Check if it looks like a drug name
            if (element_text.endswith(('mab', 'nib', 'tinib', 'cept', 'leucel')) or
                'deruxtecan' in element_text.lower() or
                'vedotin' in element_text.lower()):
                drug_names.add(element_text.title())
    
    return drug_names

if __name__ == "__main__":
    asyncio.run(test_improved_scraping())
