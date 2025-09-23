"""FDA data collector for drug approvals and adverse events."""

import json
import requests
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from .base_collector import BaseCollector, CollectedData
from config.config import settings
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup


class FDACollector(BaseCollector):
    """Collector for FDA data including drug approvals and adverse events."""
    
    def __init__(self):
        super().__init__("fda", settings.fda_base_url)
        self.fda_base_url = "https://api.fda.gov"
    
    async def collect_data(self, data_types: List[str] = None) -> List[CollectedData]:
        """Collect comprehensive FDA data including approvals, trials, and regulatory information."""
        collected_data = []
        
        if data_types is None:
            data_types = ["drug_approvals", "adverse_events", "clinical_trials", "regulatory_actions", "surrogate_endpoints"]
        
        logger.info(f"Starting comprehensive FDA data collection for {len(data_types)} data types")
        
        try:
            for data_type in data_types:
                logger.info(f"Collecting {data_type} data...")
                
                if data_type == "drug_approvals":
                    data = await self._collect_comprehensive_drug_approvals()
                    collected_data.extend(data)
                elif data_type == "adverse_events":
                    data = await self._collect_adverse_events()
                    collected_data.extend(data)
                elif data_type == "clinical_trials":
                    data = await self._collect_fda_clinical_trials()
                    collected_data.extend(data)
                elif data_type == "regulatory_actions":
                    data = await self._collect_regulatory_actions()
                    collected_data.extend(data)
                elif data_type == "drug_shortages":
                    data = await self._collect_drug_shortages()
                    collected_data.extend(data)
                elif data_type == "surrogate_endpoints":
                    data = await self._collect_surrogate_endpoints()
                    collected_data.extend(data)
                    
                logger.info(f"✅ Completed {data_type} collection: {len(data)} documents")
                    
        except Exception as e:
            logger.error(f"Error collecting FDA data: {e}")
        
        logger.info(f"🎉 FDA collection completed: {len(collected_data)} total documents")
        return collected_data
    
    async def _collect_drug_approvals(self) -> List[CollectedData]:
        """Collect recent drug approvals from FDA."""
        collected_data = []
        
        try:
            # FDA Drug Approvals API endpoint
            url = "https://api.fda.gov/drug/label.json"
            params = {
                "limit": 50,
                "search": "openfda.brand_name:* AND (openfda.brand_name:\"KEYTRUDA\" OR openfda.brand_name:\"OPDIVO\" OR openfda.brand_name:\"HERCEPTIN\" OR openfda.brand_name:\"AVASTIN\" OR openfda.brand_name:\"RITUXAN\" OR openfda.brand_name:\"TECENTRIQ\" OR openfda.brand_name:\"IMFINZI\" OR openfda.brand_name:\"TAGRISSO\" OR openfda.brand_name:\"LYNPARZA\" OR openfda.brand_name:\"YERVOY\" OR openfda.brand_name:\"BAVENCIO\" OR openfda.brand_name:\"LIBTAYO\" OR openfda.brand_name:\"ZELBORAF\" OR openfda.brand_name:\"COTELLIC\" OR openfda.brand_name:\"PERJETA\" OR openfda.brand_name:\"KADCYLA\" OR openfda.brand_name:\"LUNSUMIO\" OR openfda.brand_name:\"COLUMVI\" OR openfda.brand_name:\"ALECENSA\" OR openfda.brand_name:\"ROZLYTREK\" OR openfda.brand_name:\"PHESGO\" OR openfda.brand_name:\"ITOVEBI\" OR openfda.brand_name:\"GILOTRIF\" OR openfda.brand_name:\"TARCEVA\" OR openfda.brand_name:\"ERBITUX\" OR openfda.brand_name:\"VECTIBIX\" OR openfda.brand_name:\"TYKERB\" OR openfda.brand_name:\"AFINITOR\" OR openfda.brand_name:\"TORISEL\" OR openfda.brand_name:\"KYPROLIS\" OR openfda.brand_name:\"PADCEV\" OR openfda.brand_name:\"XOSPATA\" OR openfda.brand_name:\"ZOLBETUX\" OR openfda.brand_name:\"NUBEQA\" OR openfda.brand_name:\"LUMAKRAS\" OR openfda.brand_name:\"BLINCYTO\" OR openfda.brand_name:\"IMLYGIC\" OR openfda.brand_name:\"BESPONSA\" OR openfda.brand_name:\"BLENREP\" OR openfda.brand_name:\"POLIVY\" OR openfda.brand_name:\"ADCETRIS\" OR openfda.brand_name:\"ZEVALIN\" OR openfda.brand_name:\"BEXXAR\" OR openfda.brand_name:\"FOLOTYN\" OR openfda.brand_name:\"ADCETRIS\" OR openfda.brand_name:\"ZEVALIN\" OR openfda.brand_name:\"BEXXAR\" OR openfda.brand_name:\"FOLOTYN\" OR openfda.brand_name:\"ADCETRIS\" OR openfda.brand_name:\"ZEVALIN\" OR openfda.brand_name:\"BEXXAR\" OR openfda.brand_name:\"FOLOTYN\")",
                "sort": "effective_time:desc"
            }
            
            logger.info("Collecting FDA drug approvals...")
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for drug in results:
                    try:
                        # Extract drug information
                        brand_name = self._extract_nested_value(drug, ["openfda", "brand_name"])
                        generic_name = self._extract_nested_value(drug, ["openfda", "generic_name"])
                        manufacturer = self._extract_nested_value(drug, ["openfda", "manufacturer_name"])
                        product_type = self._extract_nested_value(drug, ["openfda", "product_type"])
                        
                        # Create content
                        content = self._format_drug_approval_content(drug, brand_name, generic_name, manufacturer, product_type)
                        
                        if content:
                            data_obj = CollectedData(
                                title=f"FDA Drug Approval: {brand_name or generic_name or 'Unknown Drug'}",
                                content=content,
                                source_url=f"https://api.fda.gov/drug/label.json?id={drug.get('id', '')}",
                                source_type="fda_drug_approval",
                                metadata={
                                    "brand_name": brand_name,
                                    "generic_name": generic_name,
                                    "manufacturer": manufacturer,
                                    "product_type": product_type,
                                    "fda_id": drug.get("id", ""),
                                    "effective_time": drug.get("effective_time", "")
                                }
                            )
                            collected_data.append(data_obj)
                            logger.info(f"✅ Collected FDA approval: {brand_name or generic_name}")
                            
                    except Exception as e:
                        logger.warning(f"Error processing drug approval: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error collecting FDA drug approvals: {e}")
        
        return collected_data
    
    async def _collect_comprehensive_drug_approvals(self) -> List[CollectedData]:
        """Collect comprehensive drug approval data with detailed information."""
        collected_data = []
        
        try:
            # Enhanced FDA Drug Approvals API search
            url = "https://api.fda.gov/drug/label.json"
            params = {
                "limit": 50,
                "search": "openfda.brand_name:* AND (openfda.brand_name:\"KEYTRUDA\" OR openfda.brand_name:\"OPDIVO\" OR openfda.brand_name:\"HERCEPTIN\" OR openfda.brand_name:\"AVASTIN\" OR openfda.brand_name:\"RITUXAN\" OR openfda.brand_name:\"TECENTRIQ\" OR openfda.brand_name:\"IMFINZI\" OR openfda.brand_name:\"TAGRISSO\" OR openfda.brand_name:\"LYNPARZA\" OR openfda.brand_name:\"YERVOY\" OR openfda.brand_name:\"BAVENCIO\" OR openfda.brand_name:\"LIBTAYO\" OR openfda.brand_name:\"ZELBORAF\" OR openfda.brand_name:\"COTELLIC\" OR openfda.brand_name:\"PERJETA\" OR openfda.brand_name:\"KADCYLA\" OR openfda.brand_name:\"LUNSUMIO\" OR openfda.brand_name:\"COLUMVI\" OR openfda.brand_name:\"ALECENSA\" OR openfda.brand_name:\"ROZLYTREK\" OR openfda.brand_name:\"PHESGO\" OR openfda.brand_name:\"ITOVEBI\" OR openfda.brand_name:\"GILOTRIF\" OR openfda.brand_name:\"TARCEVA\" OR openfda.brand_name:\"ERBITUX\" OR openfda.brand_name:\"VECTIBIX\" OR openfda.brand_name:\"TYKERB\" OR openfda.brand_name:\"AFINITOR\" OR openfda.brand_name:\"TORISEL\" OR openfda.brand_name:\"KYPROLIS\" OR openfda.brand_name:\"PADCEV\" OR openfda.brand_name:\"XOSPATA\" OR openfda.brand_name:\"ZOLBETUX\" OR openfda.brand_name:\"NUBEQA\" OR openfda.brand_name:\"LUMAKRAS\" OR openfda.brand_name:\"BLINCYTO\" OR openfda.brand_name:\"IMLYGIC\" OR openfda.brand_name:\"BESPONSA\" OR openfda.brand_name:\"BLENREP\" OR openfda.brand_name:\"POLIVY\" OR openfda.brand_name:\"ADCETRIS\" OR openfda.brand_name:\"ZEVALIN\" OR openfda.brand_name:\"BEXXAR\" OR openfda.brand_name:\"FOLOTYN\")",
                "sort": "effective_time:desc"
            }
            
            logger.info("Collecting comprehensive FDA drug approvals...")
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for result in results:
                    approval_data = self._extract_comprehensive_approval_data(result)
                    if approval_data:
                        collected_data.append(CollectedData(
                            content=approval_data,
                            title=f"FDA Comprehensive Approval: {result.get('openfda', {}).get('brand_name', ['Unknown'])[0] if result.get('openfda', {}).get('brand_name') else 'Unknown Drug'}",
                            source_url=f"{self.fda_base_url}/drug/label.json?id={result.get('id', '')}",
                            source_type="fda_comprehensive_approval"
                        ))
                
                logger.info(f"✅ Collected comprehensive FDA approvals: {len(results)} entries")
            
        except Exception as e:
            logger.error(f"Error collecting comprehensive FDA approvals: {e}")
        
        return collected_data
    
    async def _collect_fda_clinical_trials(self) -> List[CollectedData]:
        """Collect FDA clinical trials data."""
        collected_data = []
        
        try:
            # FDA Clinical Trials API (if available) or use ClinicalTrials.gov
            # For now, we'll use a placeholder approach
            logger.info("Collecting FDA clinical trials data...")
            
            # This would typically involve FDA's clinical trials database
            # For demonstration, we'll create placeholder data
            trial_data = self._create_fda_trials_placeholder()
            if trial_data:
                collected_data.append(CollectedData(
                    content=trial_data,
                    title="FDA Clinical Trials Data",
                    source_url="https://www.fda.gov/drugs/development-approval-process/clinical-trials",
                    source_type="fda_clinical_trials"
                ))
            
            logger.info("✅ Collected FDA clinical trials data")
            
        except Exception as e:
            logger.error(f"Error collecting FDA clinical trials: {e}")
        
        return collected_data
    
    async def _collect_regulatory_actions(self) -> List[CollectedData]:
        """Collect FDA regulatory actions and enforcement data."""
        collected_data = []
        
        try:
            # FDA Enforcement Reports API
            url = "https://api.fda.gov/food/enforcement.json"
            params = {
                "limit": 20,
                "sort": "recall_initiation_date:desc"
            }
            
            logger.info("Collecting FDA regulatory actions...")
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for result in results:
                    regulatory_data = self._extract_regulatory_action_data(result)
                    if regulatory_data:
                        collected_data.append(CollectedData(
                            content=regulatory_data,
                            title=f"FDA Regulatory Action: {result.get('product_description', 'Unknown Product')}",
                            source_url=f"{self.fda_base_url}/food/enforcement.json?id={result.get('id', '')}",
                            source_type="fda_regulatory_action"
                        ))
                
                logger.info(f"✅ Collected FDA regulatory actions: {len(results)} entries")
            
        except Exception as e:
            logger.error(f"Error collecting FDA regulatory actions: {e}")
        
        return collected_data
    
    def _extract_comprehensive_approval_data(self, fda_result: Dict[str, Any]) -> str:
        """Extract comprehensive FDA approval data from API response."""
        content_parts = [
            "FDA Comprehensive Drug Approval Data",
            f"Source: FDA Drug Label API",
            f"Collection Date: {self._get_current_timestamp()}",
            ""
        ]
        
        # Extract comprehensive FDA information
        openfda = fda_result.get("openfda", {})
        if openfda:
            content_parts.extend([
                "FDA Drug Information:",
                f"Brand Name: {', '.join(openfda.get('brand_name', ['N/A']))}",
                f"Generic Name: {', '.join(openfda.get('generic_name', ['N/A']))}",
                f"Manufacturer: {', '.join(openfda.get('manufacturer_name', ['N/A']))}",
                f"Product Type: {', '.join(openfda.get('product_type', ['N/A']))}",
                f"Route: {', '.join(openfda.get('route', ['N/A']))}",
                f"Substance Name: {', '.join(openfda.get('substance_name', ['N/A']))}",
                f"Application Number: {', '.join(openfda.get('application_number', ['N/A']))}",
                ""
            ])
        
        # Extract detailed indications
        indications = fda_result.get("indications_and_usage", [])
        if indications:
            content_parts.extend([
                "Detailed Indications and Usage:",
                *[f"- {indication}" for indication in indications[:10]],  # Limit to first 10
                ""
            ])
        
        # Extract dosage and administration
        dosage = fda_result.get("dosage_and_administration", [])
        if dosage:
            content_parts.extend([
                "Dosage and Administration:",
                *[f"- {dose}" for dose in dosage[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract warnings and precautions
        warnings = fda_result.get("warnings_and_cautions", [])
        if warnings:
            content_parts.extend([
                "Warnings and Precautions:",
                *[f"- {warning}" for warning in warnings[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract adverse reactions
        adverse_reactions = fda_result.get("adverse_reactions", [])
        if adverse_reactions:
            content_parts.extend([
                "Adverse Reactions:",
                *[f"- {reaction}" for reaction in adverse_reactions[:8]],  # Limit to first 8
                ""
            ])
        
        # Extract contraindications
        contraindications = fda_result.get("contraindications", [])
        if contraindications:
            content_parts.extend([
                "Contraindications:",
                *[f"- {contraindication}" for contraindication in contraindications[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract drug interactions
        interactions = fda_result.get("drug_interactions", [])
        if interactions:
            content_parts.extend([
                "Drug Interactions:",
                *[f"- {interaction}" for interaction in interactions[:5]],  # Limit to first 5
                ""
            ])
        
        # Extract clinical pharmacology
        clinical_pharm = fda_result.get("clinical_pharmacology", [])
        if clinical_pharm:
            content_parts.extend([
                "Clinical Pharmacology:",
                *[f"- {pharm}" for pharm in clinical_pharm[:3]],  # Limit to first 3
                ""
            ])
        
        # Extract effective time (approval date)
        effective_time = fda_result.get("effective_time", "")
        if effective_time:
            content_parts.extend([
                f"Effective Time (Approval Date): {effective_time}",
                ""
            ])
        
        # Extract package label principal display panel
        package_label = fda_result.get("package_label_principal_display_panel", [])
        if package_label:
            content_parts.extend([
                "Package Label Information:",
                *[f"- {label}" for label in package_label[:3]],  # Limit to first 3
                ""
            ])
        
        return "\n".join(content_parts)
    
    def _extract_regulatory_action_data(self, regulatory_result: Dict[str, Any]) -> str:
        """Extract regulatory action data from FDA enforcement API."""
        content_parts = [
            "FDA Regulatory Action Data",
            f"Source: FDA Enforcement API",
            f"Collection Date: {self._get_current_timestamp()}",
            ""
        ]
        
        # Extract enforcement information
        content_parts.extend([
            "Enforcement Information:",
            f"Product Description: {regulatory_result.get('product_description', 'N/A')}",
            f"Recall Initiation Date: {regulatory_result.get('recall_initiation_date', 'N/A')}",
            f"Status: {regulatory_result.get('status', 'N/A')}",
            f"Distribution Pattern: {regulatory_result.get('distribution_pattern', 'N/A')}",
            f"Product Quantity: {regulatory_result.get('product_quantity', 'N/A')}",
            f"Reason for Recall: {regulatory_result.get('reason_for_recall', 'N/A')}",
            f"Voluntary/Mandated: {regulatory_result.get('voluntary_mandated', 'N/A')}",
            ""
        ])
        
        # Extract firm information
        firm_info = regulatory_result.get('recalling_firm', 'N/A')
        if firm_info:
            content_parts.extend([
                "Recalling Firm Information:",
                f"Firm: {firm_info}",
                ""
            ])
        
        return "\n".join(content_parts)
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    async def _collect_adverse_events(self) -> List[CollectedData]:
        """Collect adverse event reports from FDA."""
        collected_data = []
        
        try:
            # FDA Adverse Events API endpoint
            url = "https://api.fda.gov/drug/event.json"
            params = {
                "limit": 15,
                "sort": "receivedate:desc"
            }
            
            logger.info("Collecting FDA adverse events...")
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for event in results:
                    try:
                        # Extract event information
                        drug_name = self._extract_nested_value(event, ["patient", "drug", 0, "medicinalproduct"])
                        reaction = self._extract_nested_value(event, ["patient", "reaction", 0, "reactionmeddrapt"])
                        seriousness = event.get("seriousness", "")
                        received_date = event.get("receivedate", "")
                        
                        # Create content
                        content = self._format_adverse_event_content(event, drug_name, reaction, seriousness, received_date)
                        
                        if content:
                            data_obj = CollectedData(
                                title=f"FDA Adverse Event: {drug_name or 'Unknown Drug'}",
                                content=content,
                                source_url=f"https://api.fda.gov/drug/event.json?id={event.get('safetyreportid', '')}",
                                source_type="fda_adverse_event",
                                metadata={
                                    "drug_name": drug_name,
                                    "reaction": reaction,
                                    "seriousness": seriousness,
                                    "received_date": received_date,
                                    "safety_report_id": event.get("safetyreportid", "")
                                }
                            )
                            collected_data.append(data_obj)
                            logger.info(f"✅ Collected adverse event: {drug_name}")
                            
                    except Exception as e:
                        logger.warning(f"Error processing adverse event: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error collecting FDA adverse events: {e}")
        
        return collected_data
    
    async def _collect_drug_shortages(self) -> List[CollectedData]:
        """Collect drug shortage information from FDA."""
        collected_data = []
        
        try:
            # FDA Drug Shortages API endpoint
            url = "https://api.fda.gov/drug/shortage.json"
            params = {
                "limit": 10,
                "sort": "date_updated:desc"
            }
            
            logger.info("Collecting FDA drug shortages...")
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                for shortage in results:
                    try:
                        # Extract shortage information
                        drug_name = shortage.get("drug_name", "")
                        status = shortage.get("status", "")
                        date_updated = shortage.get("date_updated", "")
                        reason = shortage.get("reason", "")
                        
                        # Create content
                        content = self._format_drug_shortage_content(shortage, drug_name, status, date_updated, reason)
                        
                        if content:
                            data_obj = CollectedData(
                                title=f"FDA Drug Shortage: {drug_name}",
                                content=content,
                                source_url=f"https://api.fda.gov/drug/shortage.json?id={shortage.get('id', '')}",
                                source_type="fda_drug_shortage",
                                metadata={
                                    "drug_name": drug_name,
                                    "status": status,
                                    "date_updated": date_updated,
                                    "reason": reason,
                                    "shortage_id": shortage.get("id", "")
                                }
                            )
                            collected_data.append(data_obj)
                            logger.info(f"✅ Collected drug shortage: {drug_name}")
                            
                    except Exception as e:
                        logger.warning(f"Error processing drug shortage: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error collecting FDA drug shortages: {e}")
        
        return collected_data
    
    def _extract_nested_value(self, data: Dict, keys: List[str]) -> str:
        """Extract value from nested dictionary using list of keys."""
        try:
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                    current = current[key]
                else:
                    return ""
            
            if isinstance(current, list) and current:
                return current[0] if isinstance(current[0], str) else str(current[0])
            elif isinstance(current, str):
                return current
            else:
                return str(current) if current else ""
        except Exception:
            return ""
    
    def _format_drug_approval_content(self, drug: Dict, brand_name: str, generic_name: str, manufacturer: str, product_type: str) -> str:
        """Format drug approval content."""
        content_parts = []
        
        if brand_name:
            content_parts.append(f"Brand Name: {brand_name}")
        if generic_name:
            content_parts.append(f"Generic Name: {generic_name}")
        if manufacturer:
            content_parts.append(f"Manufacturer: {manufacturer}")
        if product_type:
            content_parts.append(f"Product Type: {product_type}")
        
        # Add indications if available
        indications = self._extract_nested_value(drug, ["indications_and_usage"])
        if indications:
            content_parts.append(f"Indications: {indications}")
        
        # Add warnings if available
        warnings = self._extract_nested_value(drug, ["warnings"])
        if warnings:
            content_parts.append(f"Warnings: {warnings}")
        
        return "\n".join(content_parts) if content_parts else ""
    
    def _format_adverse_event_content(self, event: Dict, drug_name: str, reaction: str, seriousness: str, received_date: str) -> str:
        """Format adverse event content."""
        content_parts = []
        
        if drug_name:
            content_parts.append(f"Drug: {drug_name}")
        if reaction:
            content_parts.append(f"Adverse Reaction: {reaction}")
        if seriousness:
            content_parts.append(f"Seriousness: {seriousness}")
        if received_date:
            content_parts.append(f"Date Received: {received_date}")
        
        # Add patient age and gender if available
        patient = event.get("patient", {})
        if patient:
            age = patient.get("patientonsetage")
            gender = patient.get("patientsex")
            if age:
                content_parts.append(f"Patient Age: {age}")
            if gender:
                content_parts.append(f"Patient Gender: {gender}")
        
        return "\n".join(content_parts) if content_parts else ""
    
    def _format_drug_shortage_content(self, shortage: Dict, drug_name: str, status: str, date_updated: str, reason: str) -> str:
        """Format drug shortage content."""
        content_parts = []
        
        if drug_name:
            content_parts.append(f"Drug: {drug_name}")
        if status:
            content_parts.append(f"Status: {status}")
        if date_updated:
            content_parts.append(f"Date Updated: {date_updated}")
        if reason:
            content_parts.append(f"Reason: {reason}")
        
        return "\n".join(content_parts) if content_parts else ""
    
    async def _collect_surrogate_endpoints(self) -> List[CollectedData]:
        """Collect FDA surrogate endpoints data from the official table."""
        collected_data = []
        url = "https://www.fda.gov/drugs/development-resources/table-surrogate-endpoints-were-basis-drug-approval-or-licensure"
        
        try:
            logger.info("Collecting FDA surrogate endpoints data...")
            
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=50,
                    bypass_cache=True,
                    delay_between_requests=1.0
                )
                
                if result.success and result.html:
                    # Parse the HTML to extract table data
                    soup = BeautifulSoup(result.html, 'html.parser')
                    
                    # Find Table 2: Adult Surrogate Endpoints – Cancer Related
                    tables = soup.find_all('table')
                    table_2 = None
                    
                    for table in tables:
                        # Look for the table with "Adult Surrogate Endpoints" in the caption or nearby text
                        caption = table.find('caption')
                        if caption and 'Adult Surrogate Endpoints' in caption.get_text():
                            table_2 = table
                            break
                        # Also check for table with "Cancer Related" in nearby text
                        prev_text = table.find_previous('h2') or table.find_previous('h3')
                        if prev_text and 'Cancer Related' in prev_text.get_text():
                            table_2 = table
                            break
                    
                    if table_2:
                        logger.info("Found Table 2: Adult Surrogate Endpoints – Cancer Related")
                        rows = table_2.find_all('tr')
                        
                        # Skip header row and process data rows
                        for i, row in enumerate(rows[1:], 1):
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 5:  # Ensure we have enough columns
                                try:
                                    # Extract data from each column
                                    disease_use = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                                    patient_population = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                                    surrogate_endpoint = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                                    approval_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                                    drug_mechanism = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                                    
                                    # Create content for this row
                                    content = self._format_surrogate_endpoint_content(
                                        disease_use, patient_population, surrogate_endpoint, 
                                        approval_type, drug_mechanism
                                    )
                                    
                                    if content:
                                        collected_data.append(CollectedData(
                                            source_url=url,
                                            title=f"FDA Surrogate Endpoint - {disease_use}",
                                            content=content,
                                            source_type=self.source_type,
                                            metadata={
                                                "disease_use": disease_use,
                                                "patient_population": patient_population,
                                                "surrogate_endpoint": surrogate_endpoint,
                                                "approval_type": approval_type,
                                                "drug_mechanism": drug_mechanism,
                                                "table": "Adult Surrogate Endpoints - Cancer Related",
                                                "row_number": i
                                            }
                                        ))
                                        
                                except Exception as e:
                                    logger.warning(f"Error processing row {i}: {e}")
                                    continue
                        
                        logger.info(f"✅ Collected {len(collected_data)} surrogate endpoint entries")
                    else:
                        logger.warning("Could not find Table 2: Adult Surrogate Endpoints – Cancer Related")
                else:
                    logger.error("Failed to retrieve FDA surrogate endpoints page")
                    
        except Exception as e:
            logger.error(f"Error collecting FDA surrogate endpoints: {e}")
        
        return collected_data
    
    def _format_surrogate_endpoint_content(self, disease_use: str, patient_population: str, 
                                         surrogate_endpoint: str, approval_type: str, 
                                         drug_mechanism: str) -> str:
        """Format surrogate endpoint data into readable content."""
        content_parts = []
        
        if disease_use:
            content_parts.append(f"Disease or Use: {disease_use}")
        if patient_population:
            content_parts.append(f"Patient Population: {patient_population}")
        if surrogate_endpoint:
            content_parts.append(f"Surrogate Endpoint: {surrogate_endpoint}")
        if approval_type:
            content_parts.append(f"Type of Approval Appropriate for: {approval_type}")
        if drug_mechanism:
            content_parts.append(f"Drug Mechanism of Action: {drug_mechanism}")
        
        return "\n".join(content_parts) if content_parts else ""
    
    async def extract_drug_indications(self, drug_names: List[str]) -> List[Dict[str, Any]]:
        """Extract approved indications for a list of drug names."""
        drug_indications = []
        
        for drug_name in drug_names:
            try:
                logger.info(f"Extracting FDA indications for: {drug_name}")
                indications = await self._get_drug_indications(drug_name)
                if indications:
                    drug_indications.extend(indications)
                    logger.info(f"✅ Found {len(indications)} indication entries for {drug_name}")
                else:
                    logger.warning(f"⚠️ No indications found for {drug_name}")
            except Exception as e:
                logger.error(f"Error extracting indications for {drug_name}: {e}")
                continue
        
        return drug_indications
    
    async def _get_drug_indications(self, drug_name: str) -> List[Dict[str, Any]]:
        """Get FDA indications for a specific drug."""
        indications_data = []
        
        try:
            # Search for drug by brand name first
            brand_results = await self._search_fda_drug(drug_name, search_type="brand")
            if brand_results:
                indications_data.extend(brand_results)
            
            # Search for drug by generic name
            generic_results = await self._search_fda_drug(drug_name, search_type="generic")
            if generic_results:
                indications_data.extend(generic_results)
            
            # Deduplicate results
            indications_data = self._deduplicate_indications(indications_data)
            
        except Exception as e:
            logger.error(f"Error getting indications for {drug_name}: {e}")
        
        return indications_data
    
    async def _search_fda_drug(self, drug_name: str, search_type: str = "brand") -> List[Dict[str, Any]]:
        """Search FDA database for drug information."""
        try:
            if search_type == "brand":
                search_field = "openfda.brand_name"
            else:
                search_field = "openfda.generic_name"
            
            url = f"{self.fda_base_url}/drug/label.json"
            params = {
                "limit": 10,
                "search": f"{search_field}:\"{drug_name}\"",
                "sort": "effective_time:desc"
            }
            
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                indication_entries = []
                for result in results:
                    indication_entry = self._extract_indication_entry(result, drug_name)
                    if indication_entry:
                        indication_entries.append(indication_entry)
                
                return indication_entries
            else:
                logger.warning(f"FDA API request failed for {drug_name}: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching FDA database for {drug_name}: {e}")
            return []
    
    def _extract_indication_entry(self, fda_result: Dict[str, Any], drug_name: str) -> Optional[Dict[str, Any]]:
        """Extract indication information from FDA result."""
        try:
            openfda = fda_result.get("openfda", {})
            
            # Extract basic drug info
            brand_names = openfda.get("brand_name", [])
            generic_names = openfda.get("generic_name", [])
            manufacturer = openfda.get("manufacturer_name", [])
            
            # Extract indications
            indications = fda_result.get("indications_and_usage", [])
            if not indications:
                return None
            
            # Extract approval date
            effective_time = fda_result.get("effective_time", "")
            approval_date = self._parse_approval_date(effective_time)
            
            # Extract product type and route
            product_type = openfda.get("product_type", [])
            route = openfda.get("route", [])
            
            # Extract application number
            application_number = openfda.get("application_number", [])
            
            indication_entry = {
                "drug_name": drug_name,
                "brand_names": brand_names,
                "generic_names": generic_names,
                "manufacturer": manufacturer[0] if manufacturer else None,
                "indications": indications,
                "approval_date": approval_date,
                "effective_time": effective_time,
                "product_type": product_type[0] if product_type else None,
                "route": route[0] if route else None,
                "application_number": application_number[0] if application_number else None,
                "fda_id": fda_result.get("id", ""),
                "source_url": f"{self.fda_base_url}/drug/label.json?id={fda_result.get('id', '')}"
            }
            
            return indication_entry
            
        except Exception as e:
            logger.error(f"Error extracting indication entry: {e}")
            return None
    
    def _parse_approval_date(self, effective_time: str) -> Optional[str]:
        """Parse FDA effective time to get approval date."""
        try:
            if not effective_time:
                return None
            
            # FDA effective time format: "20191220" -> "2019-12-20"
            if len(effective_time) == 8 and effective_time.isdigit():
                year = effective_time[:4]
                month = effective_time[4:6]
                day = effective_time[6:8]
                return f"{year}-{month}-{day}"
            
            return effective_time
            
        except Exception as e:
            logger.error(f"Error parsing approval date {effective_time}: {e}")
            return None
    
    def _deduplicate_indications(self, indications_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate indication entries based on FDA ID."""
        seen_ids = set()
        unique_indications = []
        
        for indication in indications_data:
            fda_id = indication.get("fda_id", "")
            if fda_id and fda_id not in seen_ids:
                seen_ids.add(fda_id)
                unique_indications.append(indication)
        
        return unique_indications
    
    async def extract_indications_for_existing_drugs(self) -> Dict[str, Any]:
        """Extract FDA indications for all drugs already in the database."""
        from ..models.entities import Drug, Indication
        from ..models.database import get_db
        
        logger.info("Starting FDA indications extraction for existing drugs...")
        
        db = get_db()
        results = {
            "processed_drugs": 0,
            "indications_added": 0,
            "errors": 0
        }
        
        try:
            # Get all drugs from database
            drugs = db.query(Drug).all()
            logger.info(f"Found {len(drugs)} drugs to process")
            
            if not drugs:
                logger.warning("No drugs found in database. Run data collection first.")
                return results
            
            # Process each drug
            for i, drug in enumerate(drugs, 1):
                logger.info(f"Processing drug {i}/{len(drugs)}: {drug.generic_name}")
                
                try:
                    # Extract FDA data for this drug
                    fda_data = await self.collect_drug_data(drug.generic_name)
                    
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
                            results["indications_added"] += 1
                        
                        db.commit()
                        logger.info(f"Added {len(fda_data['indications'])} indications for {drug.generic_name}")
                    else:
                        logger.warning(f"No FDA data found for {drug.generic_name}")
                        
                    results["processed_drugs"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {drug.generic_name}: {e}")
                    results["errors"] += 1
                    continue
            
            logger.info(f"FDA indications extraction completed! Processed: {results['processed_drugs']}, Indications: {results['indications_added']}, Errors: {results['errors']}")
            
        except Exception as e:
            logger.error(f"Error in FDA indications extraction: {e}")
            db.rollback()
            results["errors"] += 1
        finally:
            db.close()
        
        return results
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []