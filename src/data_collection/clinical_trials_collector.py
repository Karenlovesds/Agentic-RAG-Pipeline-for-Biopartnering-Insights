"""Clinical trials data collector."""

from typing import List, Dict, Any, Optional
from loguru import logger
from .utils import BaseCollector, CollectedData
from config.config import settings, get_target_companies


class ClinicalTrialsCollector(BaseCollector):
    """Collector for ClinicalTrials.gov data."""
    
    def __init__(self):
        super().__init__("clinical_trials", settings.clinical_trials_base_url)
    
    async def collect_data(self, query_params: Optional[Dict[str, Any]] = None) -> List[CollectedData]:
        """Collect clinical trials data."""
        collected_data = []
        
        # Default query parameters focused on oncology
        default_params = {
            "format": "json",
            "pageSize": 50,
            "query.cond": "cancer"
        }
        
        # Use provided params or defaults
        if query_params:
            params = {**default_params, **query_params}
        else:
            params = default_params
        
        try:
            # If no sponsor filter in params, collect general data
            if "query.spons" not in params:
                data = await self._collect_company_trials(params)
                collected_data.extend(data)
            else:
                # Collect data for each target company
                companies = get_target_companies()
                if not companies:
                    logger.warning("No companies found in CSV, skipping company-based collection")
                else:
                    for company in companies:
                        company_params = {**params, "query.spons": company}
                        data = await self._collect_company_trials(company_params)
                        collected_data.extend(data)
                
        except Exception as e:
            logger.error(f"Error collecting clinical trials data: {e}")
        
        return collected_data
    
    async def _collect_company_trials(self, params: Dict[str, Any]) -> List[CollectedData]:
        """Collect trials for a specific company with pagination support."""
        collected_data = []
        max_pages = params.get("maxPages", 10)  # Collect up to 10 pages by default
        page_token = None
        
        try:
            for page in range(max_pages):
                # Add pagination parameters (remove maxPages from API params)
                page_params = {k: v for k, v in params.items() if k != "maxPages"}
                # Use pageToken for pagination (API v2 format)
                if page_token:
                    page_params["pageToken"] = page_token
                
                response = self._make_request(self.base_url, page_params)
                if not response:
                    break
                
                data = response.json()
                studies = data.get("studies", [])
                
                if not studies:
                    logger.info(f"No more studies found on page {page + 1}, stopping pagination")
                    break
                
                logger.info(f"Processing page {page + 1}, found {len(studies)} studies")
                
                # Get nextPageToken for pagination
                page_token = data.get("nextPageToken")
                if not page_token:
                    logger.info("No nextPageToken found, stopping pagination")
                    break
                
                for study in studies:
                    protocol_section = study.get("protocolSection", {})
                    identification_module = protocol_section.get("identificationModule", {})
                    
                    # Extract key information
                    nct_id = identification_module.get("nctId", "")
                    # Use official title if available, fallback to brief title
                    title = identification_module.get("officialTitle", "") or identification_module.get("briefTitle", "")
                    
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
                                "study_data": study,
                                "page": page + 1
                            }
                        ))
                    
        except Exception as e:
            logger.error(f"Error collecting trials for company {params.get('query.spons', '')}: {e}")
        
        logger.info(f"✅ Collected {len(collected_data)} total trials across {page + 1} pages")
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
        """Parse raw data into CollectedData objects."""
        # This method is required by the base class but not used in this implementation
        # as we handle parsing in collect_data directly
        return []
