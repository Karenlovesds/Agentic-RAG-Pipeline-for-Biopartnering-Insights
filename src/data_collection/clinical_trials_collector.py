"""Clinical trials data collector."""

import json
from typing import List, Dict, Any, Optional
from loguru import logger
from .base_collector import BaseCollector, CollectedData
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
                    for company in companies[:5]:  # Limit to first 5 companies for testing
                        company_params = {**params, "query.spons": company}
                        data = await self._collect_company_trials(company_params)
                        collected_data.extend(data)
                
        except Exception as e:
            logger.error(f"Error collecting clinical trials data: {e}")
        
        return collected_data

    async def collect_company_drug_trials(self, company_drug_mapping: Dict[str, List[str]]) -> List[CollectedData]:
        """Collect clinical trials data using company and drug name combinations."""
        collected_data = []
        
        logger.info(f"Starting targeted clinical trials collection for {len(company_drug_mapping)} companies")
        
        for company, drugs in company_drug_mapping.items():
            logger.info(f"Collecting trials for {company} with {len(drugs)} drugs")
            
            for drug in drugs:
                try:
                    # Search with drug name only (simpler query to avoid 400 errors)
                    params = {
                        "format": "json",
                        "pageSize": 20,
                        "query.cond": f"{drug}"
                    }
                    
                    data = await self._collect_company_trials(params)
                    collected_data.extend(data)
                    
                    if data:
                        logger.info(f"✅ Found {len(data)} trials for {company} + {drug}")
                    else:
                        logger.info(f"ℹ️ No trials found for {company} + {drug}")
                        
                except Exception as e:
                    logger.error(f"Error collecting trials for {company} + {drug}: {e}")
                    continue
        
        logger.info(f"🎉 Completed targeted clinical trials collection: {len(collected_data)} total documents")
        return collected_data

    async def collect_company_keyword_trials(self, max_companies: int = 5) -> List[CollectedData]:
        """Collect clinical trials using company-specific keyword combinations."""
        collected_data = []
        seen_trials = set()  # For deduplication using NCT IDs
        
        # Get company list
        companies = get_target_companies()
        if not companies:
            logger.warning("No companies found in CSV, skipping keyword-based collection")
            return collected_data
        
        companies = companies[:max_companies]
        
        # Define keyword combinations for each company
        keyword_combinations = [
            "cancer",
            "oncology", 
            "tumor"
        ]
        
        logger.info(f"Starting company keyword trials collection for {len(companies)} companies")
        
        for company in companies:
            logger.info(f"🔍 Collecting keyword trials for {company}")
            
            for keyword in keyword_combinations:
                try:
                    # Create search query: "company name + keyword"
                    search_query = f"{company} {keyword}"
                    
                    params = {
                        "format": "json",
                        "pageSize": 30,
                        "query.cond": search_query
                    }
                    
                    data = await self._collect_company_trials(params)
                    
                    # Deduplicate based on NCT ID
                    unique_data = []
                    for trial in data:
                        nct_id = trial.metadata.get("nct_id", "")
                        if nct_id and nct_id not in seen_trials:
                            seen_trials.add(nct_id)
                            unique_data.append(trial)
                    
                    collected_data.extend(unique_data)
                    
                    if unique_data:
                        logger.info(f"✅ Found {len(unique_data)} unique trials for '{search_query}'")
                    else:
                        logger.info(f"ℹ️ No new trials found for '{search_query}'")
                        
                except Exception as e:
                    logger.error(f"Error collecting trials for '{company} {keyword}': {e}")
                    continue
        
        logger.info(f"🎉 Completed company keyword trials collection: {len(collected_data)} unique documents")
        return collected_data
    
    async def _collect_company_trials(self, params: Dict[str, Any]) -> List[CollectedData]:
        """Collect trials for a specific company with pagination support."""
        collected_data = []
        max_pages = params.get("maxPages", 3)  # Collect up to 3 pages by default
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
    
    async def populate_trials_for_existing_drugs(self, max_drugs: int = 50) -> Dict[str, Any]:
        """Populate clinical trials for drugs already in the database."""
        from ..models.entities import Drug, ClinicalTrial, Indication, DrugIndication
        from ..models.database import get_db
        
        logger.info("🧬 Starting Clinical Trials Population for existing drugs")
        logger.info("=" * 50)
        
        db = get_db()
        results = {
            "processed_drugs": 0,
            "trials_added": 0,
            "indications_extracted": 0,
            "errors": 0
        }
        
        try:
            # Get all drugs from our database
            drugs = db.query(Drug).limit(max_drugs).all()
            logger.info(f"Found {len(drugs)} drugs in database")
            
            if not drugs:
                logger.warning("No drugs found in database. Please run data collection first.")
                return results
            
            # Process each drug
            for i, drug in enumerate(drugs, 1):
                logger.info(f"Processing drug {i}/{len(drugs)}: {drug.generic_name}")
                
                try:
                    drug_results = await self._process_single_drug_trials(drug, db)
                    results["trials_added"] += drug_results["trials_added"]
                    results["indications_extracted"] += drug_results["indications_extracted"]
                    results["processed_drugs"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {drug.generic_name}: {e}")
                    results["errors"] += 1
                    continue
            
            logger.info(f"Clinical trials population completed! Processed: {results['processed_drugs']}, Trials: {results['trials_added']}, Indications: {results['indications_extracted']}, Errors: {results['errors']}")
            
        except Exception as e:
            logger.error(f"Error in clinical trials population: {e}")
            db.rollback()
            results["errors"] += 1
        finally:
            db.close()
        
        return results
    
    async def _process_single_drug_trials(self, drug, db) -> Dict[str, int]:
        """Process clinical trials for a single drug."""
        results = {"trials_added": 0, "indications_extracted": 0}
        
        # Search for clinical trials for this drug
        search_terms = [drug.generic_name]
        if drug.brand_name:
            search_terms.append(drug.brand_name)
        
        # Use the existing search method
        trials_data = await self._search_clinical_trials(search_terms)
        
        if trials_data:
            results = await self._process_trials_data(trials_data, drug, db)
        else:
            logger.warning(f"No clinical trials found for {drug.generic_name}")
        
        return results
    
    async def _process_trials_data(self, trials_data, drug, db) -> Dict[str, int]:
        """Process trials data and create database entries."""
        results = {"trials_added": 0, "indications_extracted": 0}
        
        for trial_data in trials_data:
            # Check if trial already exists
            existing_trial = db.query(ClinicalTrial).filter(
                ClinicalTrial.nct_id == trial_data.get('nct_id')
            ).first()
            
            if not existing_trial:
                trial = self._create_clinical_trial(trial_data, drug, db)
                if trial:
                    results["trials_added"] += 1
                    
                    # Extract indications from trial title
                    indication_count = self._extract_indications_from_trial(trial_data, drug, db)
                    results["indications_extracted"] += indication_count
        
        db.commit()
        return results
    
    def _create_clinical_trial(self, trial_data, drug, db):
        """Create a new clinical trial from trial data."""
        try:
            trial = ClinicalTrial(
                nct_id=trial_data.get('nct_id'),
                title=trial_data.get('title', ''),
                status=trial_data.get('status', ''),
                phase=trial_data.get('phase', ''),
                study_type=trial_data.get('study_type', ''),
                start_date=trial_data.get('start_date'),
                completion_date=trial_data.get('completion_date'),
                sponsor=trial_data.get('sponsor', ''),
                conditions=trial_data.get('conditions', []),
                interventions=trial_data.get('interventions', []),
                study_population=trial_data.get('study_population', []),
                primary_endpoints=trial_data.get('primary_endpoints', [])
            )
            db.add(trial)
            db.flush()  # Get the ID
            
            # Link trial to drug
            if not any(ct.drug_id == drug.id for ct in drug.clinical_trials):
                drug.clinical_trials.append(trial)
            
            return trial
        except Exception as e:
            logger.error(f"Error creating clinical trial: {e}")
            return None
    
    def _extract_indications_from_trial(self, trial_data, drug, db) -> int:
        """Extract indications from trial title and create indication entries."""
        title = trial_data.get('title', '').lower()
        oncology_keywords = ['cancer', 'tumor', 'oncology', 'carcinoma', 'sarcoma', 'lymphoma', 'leukemia']
        
        if any(keyword in title for keyword in oncology_keywords):
            indication_text = trial_data.get('title', '')
            if indication_text:
                indication = Indication(
                    indication=indication_text,
                    approval_status=False,  # Clinical trial, not approved
                    source='Clinical Trial'
                )
                db.add(indication)
                db.flush()
                
                # Link indication to drug
                drug_indication = DrugIndication(
                    drug_id=drug.id,
                    indication_id=indication.id
                )
                db.add(drug_indication)
                return 1
        
        return 0
    
    def parse_data(self, raw_data: Any) -> List[CollectedData]:
        """Parse raw clinical trials data."""
        # This method is implemented in collect_data for this collector
        return []
