"""FDA data collector for drug approvals and adverse events."""

import json
import requests
from typing import List, Dict, Any, Optional
from loguru import logger
from .base_collector import BaseCollector, CollectedData
from config.config import settings


class FDACollector(BaseCollector):
    """Collector for FDA data including drug approvals and adverse events."""
    
    def __init__(self):
        super().__init__("fda", settings.fda_base_url)
        self.fda_base_url = "https://api.fda.gov"
    
    async def collect_data(self, data_types: List[str] = None) -> List[CollectedData]:
        """Collect comprehensive FDA data including approvals, trials, and regulatory information."""
        collected_data = []
        
        if data_types is None:
            data_types = ["drug_approvals", "adverse_events", "clinical_trials", "regulatory_actions"]
        
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
                "limit": 20,
                "search": "openfda.brand_name:* AND (indications_and_usage:\"cancer\" OR indications_and_usage:\"oncology\" OR indications_and_usage:\"tumor\" OR indications_and_usage:\"carcinoma\" OR indications_and_usage:\"sarcoma\" OR indications_and_usage:\"lymphoma\" OR indications_and_usage:\"leukemia\")",
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
                "limit": 30,
                "search": "openfda.brand_name:* AND (indications_and_usage:\"cancer\" OR indications_and_usage:\"oncology\" OR indications_and_usage:\"tumor\" OR indications_and_usage:\"carcinoma\" OR indications_and_usage:\"sarcoma\" OR indications_and_usage:\"lymphoma\" OR indications_and_usage:\"leukemia\" OR openfda.brand_name:\"pembrolizumab\" OR openfda.brand_name:\"nivolumab\" OR openfda.brand_name:\"trastuzumab\" OR openfda.brand_name:\"bevacizumab\" OR openfda.brand_name:\"rituximab\")",
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
    
    def _create_fda_trials_placeholder(self) -> str:
        """Create placeholder FDA clinical trials data."""
        return """FDA Clinical Trials Information

This section contains information about FDA-regulated clinical trials,
including trial design requirements, regulatory oversight, and compliance information.

Key Areas Covered:
- Clinical trial design and protocol requirements
- FDA guidance on clinical trial conduct
- Regulatory oversight and inspection processes
- Good Clinical Practice (GCP) requirements
- Data integrity and quality standards
- Patient safety monitoring requirements
- Investigational New Drug (IND) application process
- New Drug Application (NDA) clinical data requirements

Note: This is a placeholder for FDA clinical trials data.
In a full implementation, this would contain:
- Specific trial design requirements
- Regulatory guidance documents
- Compliance and inspection information
- Clinical trial database information
- Safety monitoring requirements
- Data submission requirements"""
    
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
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this collector
        # since we handle parsing in collect_data directly
        return []