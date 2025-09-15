"""Clinical trials data collector."""

import json
from typing import List, Dict, Any, Optional
from loguru import logger
from .base_collector import BaseCollector, CollectedData
from config import settings, get_target_companies


class ClinicalTrialsCollector(BaseCollector):
    """Collector for ClinicalTrials.gov data."""
    
    def __init__(self):
        super().__init__("clinical_trials", settings.clinical_trials_base_url)
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect clinical trials data."""
        collected_data = []
        
        # Default query parameters
        default_params = {
            "format": "json",
            "query.cond": "cancer",
            "query.phase": "PHASE2 OR PHASE3",
            "query.overallStatus": "RECRUITING OR ACTIVE_NOT_RECRUITING",
            "pageSize": 100
        }
        
        params = {**default_params, **(query_params or {})}
        
        try:
            # Collect data for each target company (CSV-backed with fallback)
            for company in get_target_companies():
                company_params = {**params, "query.spons": company}
                data = await self._collect_company_trials(company_params)
                collected_data.extend(data)
                
        except Exception as e:
            logger.error(f"Error collecting clinical trials data: {e}")
        
        return collected_data
    
    async def _collect_company_trials(self, params: Dict[str, Any]) -> List[CollectedData]:
        """Collect trials for a specific company."""
        collected_data = []
        
        try:
            response = self._make_request(self.base_url, params)
            if not response:
                return collected_data
            
            data = response.json()
            studies = data.get("studies", [])
            
            for study in studies:
                protocol_section = study.get("protocolSection", {})
                identification_module = protocol_section.get("identificationModule", {})
                
                # Extract key information
                nct_id = identification_module.get("nctId", "")
                title = identification_module.get("briefTitle", "")
                
                # Create content from study data
                content = self._format_study_content(study)
                
                if nct_id and content:
                    collected_data.append(CollectedData(
                        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                        title=title,
                        content=content,
                        source_type=self.source_type,
                        metadata={
                            "nct_id": nct_id,
                            "company": params.get("query.spons", ""),
                            "study_data": study
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"Error collecting trials for company {params.get('query.spons', '')}: {e}")
        
        return collected_data
    
    def _format_study_content(self, study: Dict[str, Any]) -> str:
        """Format study data into readable content."""
        try:
            protocol_section = study.get("protocolSection", {})
            identification = protocol_section.get("identificationModule", {})
            status = protocol_section.get("statusModule", {})
            design = protocol_section.get("designModule", {})
            conditions = protocol_section.get("conditionsModule", {})
            interventions = protocol_section.get("interventionsModule", {})
            
            content_parts = [
                f"Study Title: {identification.get('briefTitle', 'N/A')}",
                f"NCT ID: {identification.get('nctId', 'N/A')}",
                f"Status: {status.get('overallStatus', 'N/A')}",
                f"Phase: {design.get('phases', ['N/A'])[0] if design.get('phases') else 'N/A'}",
                f"Conditions: {', '.join(conditions.get('conditions', ['N/A']))}",
                f"Interventions: {', '.join([i.get('name', '') for i in interventions.get('interventions', [])])}",
                f"Study Type: {design.get('studyType', 'N/A')}",
                f"Primary Purpose: {design.get('primaryPurpose', 'N/A')}"
            ]
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error formatting study content: {e}")
            return str(study)
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw clinical trials data."""
        # This method is implemented in collect_data for this collector
        return []
