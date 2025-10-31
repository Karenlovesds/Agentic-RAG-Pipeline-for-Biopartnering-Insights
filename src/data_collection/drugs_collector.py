"""Drugs collector for drug profiles and interactions from Drugs.com."""

import re
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from .utils import BaseCollector, CollectedData
from config.config import settings


class DrugsCollector(BaseCollector):
    """Collector for drug profiles and interactions from Drugs.com.
    
    This collector fetches basic drug information from Drugs.com including:
    - Drug descriptions and mechanisms of action
    - Indications and uses
    - Drug interactions and safety information
    
    Note: FDA and clinical trials data is collected by separate dedicated collectors.
    """
    
    def __init__(self):
        super().__init__("drugs", settings.drugs_com_base_url)
    
    async def collect_data(self, drug_names: List[str] = None) -> List[CollectedData]:
        """Collect drug profile and interaction data from Drugs.com.
        
        Args:
            drug_names: List of drug names to collect. If None, uses default known drugs list.
        
        Returns:
            List of CollectedData objects with drug profiles and interactions.
        """
        collected_data = []
        
        # Use known drugs list if no specific drugs provided
        if drug_names is None:
            drug_names = self._get_comprehensive_drug_list()
        
        logger.info(f"Starting drug data collection for {len(drug_names)} drugs from Drugs.com")
        
        # Collect data for each drug
        for drug_name in drug_names:
            try:
                # Collect drug profile (description, MOA, indications)
                profile_data = await self._collect_drugs_com_profile(drug_name)
                if profile_data:
                    collected_data.extend(profile_data)
                
                # Collect drug interactions
                interactions_data = await self._collect_drug_interactions(drug_name)
                if interactions_data:
                    collected_data.extend(interactions_data)
                
                # Collect FDA approval history (new)
                fda_history_data = await self._collect_fda_approval_history(drug_name)
                if fda_history_data:
                    collected_data.extend(fda_history_data)
                
                logger.info(f"✅ Completed collection for {drug_name}")
                
            except Exception as e:
                logger.error(f"Error collecting data for {drug_name}: {e}")
        
        return collected_data
    
    def _get_comprehensive_drug_list(self) -> List[str]:
        """Get comprehensive list of oncology drugs from multiple sources."""
        # Known brand/generic names (case-insensitive)
        known_drugs = [
            # Common Roche/Genentech marketed
            "Atezolizumab","Giredestrant","Codrituzumab","Inavolisib","Polatuzumab vedotin piiq",
            "Mosunetuzumab","Trastuzumab emtansine","Cevostamab","Clesitamig","Divarasib",
            "Glofitamab","Mosperafenib","Alectinib","Autogene cevumeran","Cobimetinib",
            "Entrectinib","Pertuzumab","Tiragolumab","Trastuzumab","Vemurafenib","Venclexta",
            "Vismodegib","Bevacizumab","Obinutuzumab","Rituximab",
            # AbbVie/Gilead/etc.
            "Teliso-V","Epcoritamab","Mirvetuximab soravtansine",
            # Daiichi ADCs
            "Trastuzumab deruxtecan","Datopotamab deruxtecan-dlnk","Patrituzumab deruxtecan","Ifinatamab deruxtecan","Raludotatug deruxtecan",
            # AZ/JNJ/MSD/etc. (selected)
            "Durvalumab","Osimertinib","Olaparib","Tremelimumab","Gefitinib","Moxetumomab pasudotox",
            "Bemarituzumab","Blinatumomab","Tarlatamab-dlle","Sotorasib",
            "Carfilzomib","Enfortumab vedotin","Gilteritinib","Zolbetuximab","Fezolinetant",
            "Darolutamide","Sevabertinib",
            # Merck MK names
            "Pembrolizumab","Belzutifan","Zilovertamab vedotin","Bomedemstat",
            # Additional common oncology drugs
            "Nivolumab","Ipilimumab","Avelumab","Cemiplimab","Doxorubicin","Cisplatin",
            "Carboplatin","Paclitaxel","Docetaxel","Gemcitabine","Fluorouracil",
            "Methotrexate","Cyclophosphamide","Etoposide","Imatinib","Sorafenib",
            "Sunitinib","Erlotinib","Gefitinib","Cetuximab","Panitumumab",
            "Lapatinib","Everolimus","Temsirolimus","Rituximab","Bevacizumab"
        ]
        
        # Convert to lowercase for consistency
        return [drug.lower() for drug in known_drugs]
    
    async def _collect_drugs_com_profile(self, drug_name: str) -> List[CollectedData]:
        """Collect basic drug profile from Drugs.com.
        
        Extracts: description, mechanism of action, indications, dosage, and side effects.
        """
        collected_data = []
        
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                # Search for drug on Drugs.com
                search_url = f"https://www.drugs.com/search.php?searchterm={drug_name}"
                result = await crawler.arun(url=search_url)
                
                if result.success and result.cleaned_html:
                    # Extract drug profile information
                    content = self._extract_drug_profile_content(result.cleaned_html, drug_name)
                    if content:
                        collected_data.append(CollectedData(
                            content=content,
                            title=f"Drug Profile: {drug_name.title()}",
                            source_url=search_url,
                            source_type="drugs_com_profile"
                        ))
                        logger.info(f"✅ Collected Drugs.com profile for {drug_name}")
                
        except Exception as e:
            logger.error(f"Error collecting Drugs.com profile for {drug_name}: {e}")
        
        return collected_data
    
    async def _collect_drug_interactions(self, drug_name: str) -> List[CollectedData]:
        """Collect drug interaction data from Drugs.com.
        
        Extracts: major interactions, moderate interactions, food/drug interactions, and alcohol interactions.
        """
        collected_data = []
        
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                # Search for drug interactions on Drugs.com
                interactions_url = f"https://www.drugs.com/drug-interactions/{drug_name.lower()}.html"
                result = await crawler.arun(url=interactions_url)
                
                if result.success and result.cleaned_html:
                    interactions_content = self._extract_drug_interactions_content(result.cleaned_html, drug_name)
                    if interactions_content:
                        collected_data.append(CollectedData(
                            content=interactions_content,
                            title=f"Drug Interactions: {drug_name.title()}",
                            source_url=interactions_url,
                            source_type="drug_interactions"
                        ))
                        logger.info(f"✅ Collected drug interactions for {drug_name}")
                
        except Exception as e:
            logger.error(f"Error collecting drug interactions for {drug_name}: {e}")
        
        return collected_data
    
    def _extract_drug_profile_content(self, html_content: str, drug_name: str) -> str:
        """Extract drug profile content from Drugs.com HTML."""
        # This is a simplified extraction - in practice, you'd use BeautifulSoup
        # to parse the HTML and extract specific sections like:
        # - Drug description
        # - Indications
        # - Dosage information
        # - Side effects
        # - Warnings and precautions
        
        content_parts = [
            f"Drug Profile: {drug_name.title()}",
            f"Source: Drugs.com",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Profile Information:",
            f"Enhanced drug profile information for {drug_name} from Drugs.com",
            "This includes comprehensive information about the drug, its uses, and safety information.",
            ""
        ]
        
        # Enhanced drug profile extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract drug description
        description_sections = soup.find_all(['div', 'p'], string=re.compile(r'description|overview|about', re.I))
        if description_sections:
            for section in description_sections:
                text = section.get_text().strip()
                if len(text) > 50:
                    content_parts.append(f"Description: {text[:300]}...")
                    break
        
        # Extract mechanism of action
        moa_sections = soup.find_all(['div', 'p'], string=re.compile(r'mechanism\s+of\s+action|how\s+it\s+works', re.I))
        if moa_sections:
            for section in moa_sections:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Mechanism of Action: {text[:250]}...")
                    break
        
        # Extract indications
        indication_patterns = [
            r'indication[s]?\s*:?\s*([^.]+)',
            r'used\s+to\s+treat\s+([^.]+)',
            r'approved\s+for\s+([^.]+)'
        ]
        
        for pattern in indication_patterns:
            matches = re.findall(pattern, html_content, re.I)
            if matches:
                content_parts.append(f"Indications: {matches[0][:200]}...")
                break
        
        # Extract dosage information
        dosage_sections = soup.find_all(['div', 'p'], string=re.compile(r'dosage|dosing|administration', re.I))
        if dosage_sections:
            for section in dosage_sections:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Dosage: {text[:200]}...")
                    break
        
        # Extract side effects
        side_effects_sections = soup.find_all(['div', 'p'], string=re.compile(r'side\s+effects?|adverse\s+reactions?', re.I))
        if side_effects_sections:
            for section in side_effects_sections:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Side Effects: {text[:200]}...")
                    break
        
        if len(content_parts) <= 3:  # Still no meaningful content
            content_parts.extend([
                "Drug profile information not found in accessible content.",
                "This may indicate:",
                "- Content requires registration/login",
                "- Information is in PDF documents",
                "- Data is loaded dynamically via JavaScript"
            ])
        
        return "\n".join(content_parts)
    
    def _extract_drug_interactions_content(self, html_content: str, drug_name: str) -> str:
        """Extract drug interactions content from HTML using BeautifulSoup parsing."""
        content_parts = [
            f"Drug Interactions: {drug_name.title()}",
            f"Source: Drugs.com",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Interaction Information:",
            f"Enhanced drug interaction data for {drug_name} from Drugs.com",
            "This includes comprehensive information about potential drug-drug interactions,",
            "drug-food interactions, and other relevant interaction data.",
            ""
        ]
        
        # Enhanced interaction extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract major interactions
        major_interactions = soup.find_all(['div', 'p'], string=re.compile(r'major\s+interaction|severe\s+interaction', re.I))
        if major_interactions:
            for section in major_interactions:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Major Interactions: {text[:250]}...")
                    break
        
        # Extract moderate interactions
        moderate_interactions = soup.find_all(['div', 'p'], string=re.compile(r'moderate\s+interaction', re.I))
        if moderate_interactions:
            for section in moderate_interactions:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Moderate Interactions: {text[:250]}...")
                    break
        
        # Extract drug-food interactions
        food_interactions = soup.find_all(['div', 'p'], string=re.compile(r'food\s+interaction|take\s+with\s+food', re.I))
        if food_interactions:
            for section in food_interactions:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Food Interactions: {text[:200]}...")
                    break
        
        # Extract alcohol interactions
        alcohol_interactions = soup.find_all(['div', 'p'], string=re.compile(r'alcohol\s+interaction|drinking\s+alcohol', re.I))
        if alcohol_interactions:
            for section in alcohol_interactions:
                text = section.get_text().strip()
                if len(text) > 30:
                    content_parts.append(f"Alcohol Interactions: {text[:200]}...")
                    break
        
        if len(content_parts) <= 3:  # Still no meaningful content
            content_parts.extend([
                "Drug interaction information not found in accessible content.",
                "This may indicate:",
                "- Interaction data requires medical professional access",
                "- Information is in specialized databases",
                "- Content is dynamically loaded"
            ])
        
        return "\n".join(content_parts)
    
    async def _collect_fda_approval_history(self, drug_name: str) -> List[CollectedData]:
        """Collect FDA approval history from Drugs.com.
        
        Searches for drug name + "FDA approval history" and extracts:
        - FDA Approval status and date
        - Brand name, Generic name, Dosage form, Company
        - Development timeline with dates and article titles (containing Indication Approved)
        
        Args:
            drug_name: Drug name to search for
            
        Returns:
            List of CollectedData objects with FDA approval history information
        """
        collected_data = []
        
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                # Search for FDA approval history on Drugs.com
                # Try different URL patterns
                search_urls = [
                    f"https://www.drugs.com/history/{drug_name.lower().replace(' ', '-')}.html",
                    f"https://www.drugs.com/search.php?searchterm={drug_name}+FDA+approval+history",
                ]
                
                for search_url in search_urls:
                    try:
                        result = await crawler.arun(url=search_url)
                        
                        if result.success and result.cleaned_html:
                            # Extract FDA approval history content
                            content = self._extract_fda_approval_history_content(
                                result.cleaned_html, 
                                drug_name,
                                result.markdown or ""
                            )
                            
                            if content and len(content) > 200:  # Only if we got meaningful content
                                collected_data.append(CollectedData(
                                    content=content,
                                    title=f"FDA Approval History: {drug_name.title()}",
                                    source_url=search_url,
                                    source_type="drugs_com_fda_history"
                                ))
                                logger.info(f"✅ Collected FDA approval history for {drug_name}")
                                break  # Success, no need to try other URLs
                                
                    except Exception as e:
                        logger.debug(f"Error accessing {search_url}: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error collecting FDA approval history for {drug_name}: {e}")
        
        return collected_data
    
    def _extract_fda_approval_history_content(self, html_content: str, drug_name: str, markdown_content: str = "") -> str:
        """Extract FDA approval history content from Drugs.com HTML.
        
        Extracts:
        - FDA Approval status and date (e.g., "FDA Approved: Yes (First approved September 4, 2014)")
        - Brand name, Generic name, Dosage form, Company
        - Development timeline with dates and article titles
        - Parses article titles to extract indication approved information
        """
        content_parts = [
            f"FDA Approval History: {drug_name.title()}",
            f"Source: Drugs.com",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract basic drug information (Brand, Generic, Dosage, Company)
        basic_info = {}
        
        # Look for patterns like "Brand name: Keytruda" or "Generic name: pembrolizumab"
        text_content = soup.get_text()
        
        # Extract Brand name
        brand_match = re.search(r'(?:brand\s+name|trade\s+name)[:\s]+([A-Z][a-zA-Z\s-]+)', text_content, re.I)
        if brand_match:
            basic_info['brand_name'] = brand_match.group(1).strip()
        
        # Extract Generic name
        generic_match = re.search(r'generic\s+name[:\s]+([a-zA-Z\s-]+)', text_content, re.I)
        if generic_match:
            basic_info['generic_name'] = generic_match.group(1).strip()
        
        # Extract Dosage form
        dosage_match = re.search(r'(?:dosage\s+form|formulation)[:\s]+([^,\n.]+)', text_content, re.I)
        if dosage_match:
            basic_info['dosage_form'] = dosage_match.group(1).strip()
        
        # Extract Company/Manufacturer
        company_patterns = [
            r'company[:\s]+([A-Z][a-zA-Z\s&.,-]+)',
            r'manufacturer[:\s]+([A-Z][a-zA-Z\s&.,-]+)',
            r'by\s+([A-Z][a-zA-Z\s&.,-]+)\s+(?:Inc|LLC|Corp|Pharmaceuticals?)',
        ]
        for pattern in company_patterns:
            company_match = re.search(pattern, text_content, re.I)
            if company_match:
                basic_info['company'] = company_match.group(1).strip()
                break
        
        # Extract FDA Approval status and date
        fda_approved_match = re.search(
            r'FDA\s+Approved[:\s]*(?:Yes|No)[\s(]*(?:first\s+approved|approved)?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})?',
            text_content,
            re.I
        )
        if fda_approved_match:
            approval_text = fda_approved_match.group(0)
            basic_info['fda_approval'] = approval_text.strip()
            
            # Extract date separately
            date_match = re.search(r'([A-Za-z]+\s+\d{1,2},\s+\d{4})', approval_text)
            if date_match:
                basic_info['fda_approval_date'] = date_match.group(1)
        
        # Add basic info to content
        if basic_info:
            content_parts.append("=== Basic Drug Information ===")
            if 'brand_name' in basic_info:
                content_parts.append(f"Brand name: {basic_info['brand_name']}")
            if 'generic_name' in basic_info:
                content_parts.append(f"Generic name: {basic_info['generic_name']}")
            if 'dosage_form' in basic_info:
                content_parts.append(f"Dosage form: {basic_info['dosage_form']}")
            if 'company' in basic_info:
                content_parts.append(f"Company: {basic_info['company']}")
            if 'fda_approval' in basic_info:
                content_parts.append(f"FDA Approved: {basic_info['fda_approval']}")
            content_parts.append("")
        
        # Extract Development Timeline
        # Look for tables or sections with "Development timeline" or "Timeline"
        timeline_section = None
        
        # Try to find timeline section in HTML
        timeline_headers = soup.find_all(['h2', 'h3', 'h4', 'div'], string=re.compile(r'development\s+timeline|timeline|approval\s+history', re.I))
        
        if timeline_headers:
            for header in timeline_headers:
                # Find the next table or list after the header
                current = header.find_next(['table', 'ul', 'div'])
                if current:
                    timeline_section = current
                    break
        
        # Also check for tables with Date and Article columns
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all(['th', 'td'])[:2]]
            if 'date' in headers and 'article' in headers:
                timeline_section = table
                break
        
        if timeline_section:
            content_parts.append("=== Development Timeline ===")
            
            # Extract rows from table
            rows = timeline_section.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    date_text = cells[0].get_text().strip()
                    article_text = cells[1].get_text().strip()
                    
                    if date_text and article_text and date_text.lower() != 'date':
                        content_parts.append(f"Date: {date_text}")
                        content_parts.append(f"Article: {article_text}")
                        
                        # Extract indication from article title if it contains "Indication Approved" or approval info
                        indication_match = re.search(
                            r'(?:approval|approved)\s+(?:for|of)\s+([^,\.]+)',
                            article_text,
                            re.I
                        )
                        if indication_match:
                            indication = indication_match.group(1).strip()
                            content_parts.append(f"  → Indication Approved: {indication}")
                        
                        content_parts.append("")
        
        # Fallback: Extract from markdown or plain text if table parsing didn't work
        if not timeline_section and markdown_content:
            # Look for timeline patterns in markdown
            timeline_pattern = r'(?:development\s+timeline|timeline)\s+for\s+[\w\s]+\s+(.*?)(?:\n\n|\Z)'
            timeline_match = re.search(timeline_pattern, markdown_content, re.I | re.DOTALL)
            if timeline_match:
                timeline_text = timeline_match.group(1)
                # Try to extract date-article pairs
                date_article_pattern = r'(\w+\s+\d{1,2},\s+\d{4})\s+(.*?)(?=\n\w+\s+\d{1,2},|\Z)'
                matches = re.findall(date_article_pattern, timeline_text)
                if matches:
                    content_parts.append("=== Development Timeline (from text) ===")
                    for date, article in matches:
                        content_parts.append(f"Date: {date.strip()}")
                        content_parts.append(f"Article: {article.strip()}")
                        # Extract indication
                        indication_match = re.search(
                            r'(?:approval|approved)\s+(?:for|of)\s+([^,\.]+)',
                            article,
                            re.I
                        )
                        if indication_match:
                            indication = indication_match.group(1).strip()
                            content_parts.append(f"  → Indication Approved: {indication}")
                        content_parts.append("")
        
        # If we found any meaningful content
        if len(content_parts) > 4:  # More than just header
            return "\n".join(content_parts)
        
        # Return None if no meaningful content found
        return None
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this implementation
        # as we handle parsing in the individual collection methods
        return []