#!/usr/bin/env python3
"""
Script to collect drug data from company websites using improved scraping methods.
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
import pandas as pd

async def collect_improved_company_data():
    """Collect drug data from company websites using improved methods."""
    print("🔧 Collecting improved company drug data...")
    
    # Read companies from CSV to get correct pipeline URLs
    companies_df = pd.read_csv('data/companies.csv')
    
    # Filter to companies with working pipeline URLs
    working_companies = [
        ('AstraZeneca', 'https://www.astrazeneca.com/our-science/pipeline.html'),
        ('AbbVie', 'https://www.abbvie.com/science/pipeline.html'),
        ('Sanofi', 'https://www.sanofi.com/en/our-science/our-pipeline'),
        ('Novartis', 'https://www.novartis.com/research-development/novartis-pipeline'),
        ('Roche/Genentech', 'https://www.roche.com/solutions/pipeline')
    ]
    
    db = get_db()
    
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            for company_name, pipeline_url in working_companies:
                print(f"\n🏢 Collecting data for {company_name}...")
                
                # Get or create company
                company = db.query(Company).filter(Company.name == company_name).first()
                if not company:
                    company = Company(name=company_name)
                    db.add(company)
                    db.commit()
                
                # Collect data from pipeline URL
                await collect_company_pipeline_data(crawler, company, pipeline_url, db)
                
        print("\n✅ Company data collection completed!")
        
    except Exception as e:
        print(f"❌ Error during collection: {e}")
        raise
    finally:
        db.close()

async def collect_company_pipeline_data(crawler, company: Company, pipeline_url: str, db):
    """Collect drug data from a company's pipeline page."""
    try:
        print(f"  📄 Scraping: {pipeline_url}")
        
        # Use JavaScript to wait for content to load
        result = await crawler.arun(
            url=pipeline_url,
            word_count_threshold=5,
            extraction_strategy='NoExtractionStrategy',
            bypass_cache=True,
            js_code='''
            // Wait for content to load
            await new Promise(resolve => setTimeout(resolve, 3000));
            
            // Try to click any 'load more' or 'show all' buttons
            const buttons = document.querySelectorAll('button, a');
            for (let button of buttons) {
                const text = button.textContent.toLowerCase();
                if (text.includes('load') || text.includes('show') || text.includes('more') || text.includes('all')) {
                    button.click();
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            '''
        )
        
        if not result.success:
            print(f"    ❌ Failed to fetch content")
            return
        
        # Extract drug names from content
        drug_names = extract_drug_names_from_content(result.cleaned_html)
        
        if drug_names:
            print(f"    💊 Found {len(drug_names)} drugs: {list(drug_names)[:5]}")
            
            # Create or update drugs in database
            for drug_name in drug_names:
                # Check if drug already exists for this company
                existing_drug = db.query(Drug).filter(
                    Drug.company_id == company.id,
                    Drug.generic_name.ilike(drug_name)
                ).first()
                
                if not existing_drug:
                    # Create new drug
                    drug = Drug(
                        generic_name=drug_name,
                        company_id=company.id,
                        drug_class=infer_drug_class(drug_name)
                    )
                    db.add(drug)
                    print(f"      ➕ Added: {drug_name}")
                else:
                    print(f"      ✅ Exists: {drug_name}")
            
            db.commit()
            
            # Create document record
            content_hash = hash(result.cleaned_html)
            existing_doc = db.query(Document).filter(
                Document.content_hash == str(content_hash)
            ).first()
            
            if not existing_doc:
                doc = Document(
                    source_url=pipeline_url,
                    title=f"{company.name} - Pipeline Data",
                    content=result.cleaned_html,
                    content_hash=str(content_hash),
                    source_type="company_pipeline_improved"
                )
                db.add(doc)
                db.commit()
                print(f"    📄 Saved document: {doc.id}")
        else:
            print(f"    💊 No drug names found")
            
    except Exception as e:
        print(f"    ❌ Error collecting data for {company.name}: {e}")

def extract_drug_names_from_content(html_content: str) -> set:
    """Extract drug names from HTML content using improved patterns."""
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
        # Specific known drugs (expanded list)
        r'\b(Pembrolizumab|Nivolumab|Trastuzumab|Atezolizumab|Ipilimumab|Elotuzumab|Avelumab|Blinatumomab|Dupilumab|Ruxolitinib|Sotatercept|Nemtabrutinib|Quavonlimab|Clesrovimab|Bezlotoxumab|Patritumab|Sacituzumab|Zilovertamab|Ifinatamab|Tisagenlecleucel|Yescarta|Kymriah|Carvykti|Abecma|Breyanzi|Oleclumab|Tozorakimab|Osimertinib|Obinutuzumab|Epcoritamab|Upadacitinib|Elezanumab|Teplizumab|Frexalimab|Itepekimab|Rilzabrutinib|Amlitelimab)\b'
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
    drug_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'span', 'div'])
    for element in drug_elements:
        element_text = element.get_text().strip()
        if element_text and len(element_text) <= 50:
            # Check if it looks like a drug name
            if (element_text.endswith(('mab', 'nib', 'tinib', 'cept', 'leucel')) or
                'deruxtecan' in element_text.lower() or
                'vedotin' in element_text.lower()):
                drug_names.add(element_text.title())
    
    return drug_names

def infer_drug_class(drug_name: str) -> str:
    """Infer drug class from drug name."""
    name_lower = drug_name.lower()
    
    if name_lower.endswith(('mab', 'zumab', 'ximab')):
        return "Monoclonal Antibody"
    elif name_lower.endswith(('nib', 'tinib')):
        return "Kinase Inhibitor"
    elif name_lower.endswith('cept'):
        return "Fusion Protein"
    elif name_lower.endswith('leucel'):
        return "CAR-T Therapy"
    elif 'deruxtecan' in name_lower or 'vedotin' in name_lower:
        return "Antibody Drug Conjugate"
    else:
        return "Unknown"

if __name__ == "__main__":
    asyncio.run(collect_improved_company_data())
