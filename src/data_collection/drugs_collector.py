"""Enhanced drugs collector for drug profiles, FDA approval history, and clinical trial data."""

import asyncio
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from crawl4ai import AsyncWebCrawler
from .base_collector import BaseCollector, CollectedData
from config.config import settings


class DrugsCollector(BaseCollector):
    """Enhanced collector for comprehensive drug information including FDA approval history."""
    
    def __init__(self):
        super().__init__("drugs", settings.drugs_com_base_url)
        self.fda_base_url = "https://api.fda.gov"
        self.clinical_trials_url = "https://clinicaltrials.gov/api/v2/studies"
    
    async def collect_data(self, drug_names: List[str] = None) -> List[CollectedData]:
        """Collect comprehensive drug information including FDA approval history."""
        collected_data = []
        
        # Combine database drugs with known drugs for comprehensive coverage
        if drug_names is None:
            drug_names = self._get_comprehensive_drug_list()
        else:
            # Add known drugs to the database drugs for more comprehensive coverage
            known_drugs = self._get_comprehensive_drug_list()
            # Combine and deduplicate (case-insensitive)
            all_drugs = drug_names + known_drugs
            seen = set()
            drug_names = []
            for drug in all_drugs:
                drug_lower = drug.lower()
                if drug_lower not in seen:
                    seen.add(drug_lower)
                    drug_names.append(drug)
        
        # Limit to first 20 drugs for comprehensive collection
        drug_names = drug_names[:20]
        
        logger.info(f"Starting comprehensive drug data collection for {len(drug_names)} drugs (database + known drugs)")
        
        # Collect data from multiple sources
        for drug_name in drug_names:
            try:
                # 1. Drugs.com profile
                drugs_com_data = await self._collect_drugs_com_profile(drug_name)
                if drugs_com_data:
                    collected_data.extend(drugs_com_data)
                
                # 2. FDA approval history
                fda_data = await self._collect_fda_approval_history(drug_name)
                if fda_data:
                    collected_data.extend(fda_data)
                
                # 3. Clinical trials data
                trials_data = await self._collect_clinical_trials(drug_name)
                if trials_data:
                    collected_data.extend(trials_data)
                
                # 4. Drug interactions
                interactions_data = await self._collect_drug_interactions(drug_name)
                if interactions_data:
                    collected_data.extend(interactions_data)
                
                logger.info(f"✅ Completed comprehensive collection for {drug_name}")
                
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
    
    def _get_sample_known_drugs(self, limit: int = 10) -> List[str]:
        """Get a sample of known drugs for testing purposes."""
        known_drugs = self._get_comprehensive_drug_list()
        return known_drugs[:limit]
    
    async def _collect_drugs_com_profile(self, drug_name: str) -> List[CollectedData]:
        """Collect basic drug profile from Drugs.com."""
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
    
    async def _collect_fda_approval_history(self, drug_name: str) -> List[CollectedData]:
        """Collect comprehensive FDA approval history for a drug."""
        collected_data = []
        
        try:
            # Search FDA drug labels for the drug
            fda_url = f"{self.fda_base_url}/drug/label.json"
            params = {
                "search": f"openfda.brand_name:\"{drug_name}\" OR openfda.generic_name:\"{drug_name}\"",
                "limit": 10,
                "sort": "effective_time:desc"
            }
            
            response = self._make_request(fda_url, params)
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for i, result in enumerate(results):
                    approval_data = self._extract_fda_approval_data(result, drug_name)
                    if approval_data:
                        collected_data.append(CollectedData(
                            content=approval_data,
                            title=f"FDA Approval History: {drug_name.title()}",
                            source_url=f"{self.fda_base_url}/drug/label.json?id={result.get('id', '')}",
                            source_type="fda_drug_approval"
                        ))
                
                logger.info(f"✅ Collected FDA approval history for {drug_name} ({len(results)} entries)")
            
        except Exception as e:
            logger.error(f"Error collecting FDA approval history for {drug_name}: {e}")
        
        return collected_data
    
    async def _collect_clinical_trials(self, drug_name: str) -> List[CollectedData]:
        """Collect clinical trials data for a drug."""
        collected_data = []
        
        try:
            # Search ClinicalTrials.gov for trials involving the drug
            trials_url = self.clinical_trials_url
            params = {
                "format": "json",
                "query.cond": drug_name,
                "pageSize": 20
            }
            
            response = self._make_request(trials_url, params)
            if response and response.status_code == 200:
                data = response.json()
                studies = data.get("studies", [])
                
                for study in studies:
                    trial_data = self._extract_clinical_trial_data(study, drug_name)
                    if trial_data:
                        nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")
                        collected_data.append(CollectedData(
                            content=trial_data,
                            title=f"Clinical Trial: {drug_name.title()} - {nct_id}",
                            source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                            source_type="clinical_trial"
                        ))
                
                logger.info(f"✅ Collected clinical trials for {drug_name} ({len(studies)} trials)")
            
        except Exception as e:
            logger.error(f"Error collecting clinical trials for {drug_name}: {e}")
        
        return collected_data
    
    async def _collect_drug_interactions(self, drug_name: str) -> List[CollectedData]:
        """Collect drug interaction data."""
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
            f"Basic drug profile information for {drug_name} from Drugs.com",
            "This includes general information about the drug, its uses, and basic safety information.",
            "",
            "Note: This is a placeholder for extracted drug profile content.",
            "In a full implementation, this would contain parsed HTML content with:",
            "- Drug description and mechanism of action",
            "- Approved indications",
            "- Dosage and administration",
            "- Side effects and adverse reactions",
            "- Contraindications and warnings",
            "- Drug interactions",
            "- Storage and handling information"
        ]
        
        return "\n".join(content_parts)
    
    def _extract_fda_approval_data(self, fda_result: Dict[str, Any], drug_name: str) -> str:
        """Extract FDA approval data from API response."""
        content_parts = [
            f"FDA Approval Data: {drug_name.title()}",
            f"Source: FDA Drug Label API",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Extract key FDA information
        openfda = fda_result.get("openfda", {})
        if openfda:
            content_parts.extend([
                "FDA Information:",
                f"Brand Name: {', '.join(openfda.get('brand_name', ['N/A']))}",
                f"Generic Name: {', '.join(openfda.get('generic_name', ['N/A']))}",
                f"Manufacturer: {', '.join(openfda.get('manufacturer_name', ['N/A']))}",
                f"Product Type: {', '.join(openfda.get('product_type', ['N/A']))}",
                f"Route: {', '.join(openfda.get('route', ['N/A']))}",
                ""
            ])
        
        # Extract indications and usage
        indications = fda_result.get("indications_and_usage", [])
        if indications:
            content_parts.extend([
                "Indications and Usage:",
                *[f"- {indication}" for indication in indications[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract warnings
        warnings = fda_result.get("warnings_and_cautions", [])
        if warnings:
            content_parts.extend([
                "Warnings and Cautions:",
                *[f"- {warning}" for warning in warnings[:3]],  # Limit to first 3
                ""
            ])
        
        # Extract adverse reactions
        adverse_reactions = fda_result.get("adverse_reactions", [])
        if adverse_reactions:
            content_parts.extend([
                "Adverse Reactions:",
                *[f"- {reaction}" for reaction in adverse_reactions[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract effective time (approval date)
        effective_time = fda_result.get("effective_time", "")
        if effective_time:
            content_parts.extend([
                f"Effective Time (Approval Date): {effective_time}",
                ""
            ])
        
        return "\n".join(content_parts)
    
    def _extract_clinical_trial_data(self, study: Dict[str, Any], drug_name: str) -> str:
        """Extract clinical trial data from API response."""
        content_parts = [
            f"Clinical Trial Data: {drug_name.title()}",
            f"Source: ClinicalTrials.gov",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        protocol_section = study.get("protocolSection", {})
        identification = protocol_section.get("identificationModule", {})
        status = protocol_section.get("statusModule", {})
        conditions = protocol_section.get("conditionsModule", {})
        eligibility = protocol_section.get("eligibilityModule", {})
        
        # Basic trial information
        content_parts.extend([
            "Trial Information:",
            f"NCT ID: {identification.get('nctId', 'N/A')}",
            f"Title: {identification.get('briefTitle', 'N/A')}",
            f"Official Title: {identification.get('officialTitle', 'N/A')}",
            f"Status: {status.get('overallStatus', 'N/A')}",
            f"Phase: {', '.join(status.get('phases', ['N/A']))}",
            f"Start Date: {status.get('startDateStruct', {}).get('date', 'N/A')}",
            f"Completion Date: {status.get('completionDateStruct', {}).get('date', 'N/A')}",
            ""
        ])
        
        # Conditions
        conditions_list = conditions.get("conditions", [])
        if conditions_list:
            content_parts.extend([
                "Conditions:",
                *[f"- {condition}" for condition in conditions_list[:5]],
                ""
            ])
        
        # Eligibility criteria
        eligibility_criteria = eligibility.get("eligibilityCriteria", "")
        if eligibility_criteria:
            content_parts.extend([
                "Eligibility Criteria:",
                f"{eligibility_criteria[:500]}...",  # Truncate for brevity
                ""
            ])
        
        return "\n".join(content_parts)
    
    def _extract_drug_interactions_content(self, html_content: str, drug_name: str) -> str:
        """Extract drug interactions content from HTML."""
        content_parts = [
            f"Drug Interactions: {drug_name.title()}",
            f"Source: Drugs.com",
            f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Interaction Information:",
            f"Drug interaction data for {drug_name} from Drugs.com",
            "This includes information about potential drug-drug interactions,",
            "drug-food interactions, and other relevant interaction data.",
            "",
            "Note: This is a placeholder for extracted interaction content.",
            "In a full implementation, this would contain parsed HTML content with:",
            "- Major drug interactions",
            "- Moderate drug interactions", 
            "- Minor drug interactions",
            "- Drug-food interactions",
            "- Drug-alcohol interactions",
            "- Interaction severity levels",
            "- Clinical significance of interactions"
        ]
        
        return "\n".join(content_parts)
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this implementation
        # as we handle parsing in the individual collection methods
        return []