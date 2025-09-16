#!/usr/bin/env python3
"""
Populate clinical trials for drugs in our database by searching ClinicalTrials.gov.
Extracts indication information from official titles.
"""

import asyncio
import sys
import requests
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path
# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.models.database import get_db
from src.models.entities import Drug, ClinicalTrial, Indication, DrugIndication
from sqlalchemy.orm import Session
from loguru import logger


class ClinicalTrialsPopulatorV2:
    """Populates clinical trials for drugs in our database with indication extraction."""
    
    def __init__(self):
        self.base_url = "https://clinicaltrials.gov/api/v2/studies"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BiopartneringInsights/1.0)'
        })
    
    async def populate_all_drug_trials(self):
        """Populate clinical trials for all drugs in our database."""
        logger.info("🧬 Starting Clinical Trials Population V2")
        logger.info("=" * 50)
        
        db = get_db()
        try:
            # Get all drugs from our database
            drugs = db.query(Drug).all()
            logger.info(f"Found {len(drugs)} drugs in database")
            
            if not drugs:
                logger.warning("No drugs found in database. Please run data collection first.")
                return
            
            total_trials_added = 0
            total_indications_added = 0
            
            for i, drug in enumerate(drugs, 1):
                logger.info(f"\n🔍 Processing drug {i}/{len(drugs)}: {drug.generic_name}")
                
                try:
                    # Search for clinical trials for this drug
                    trials_added, indications_added = await self._search_and_add_trials_for_drug(db, drug)
                    total_trials_added += trials_added
                    total_indications_added += indications_added
                    
                    logger.info(f"✅ Added {trials_added} trials and {indications_added} indications for {drug.generic_name}")
                    
                    # Small delay to be respectful to the API
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {drug.generic_name}: {e}")
                    continue
            
            logger.info(f"\n🎉 Clinical trials population complete!")
            logger.info(f"   - Total trials added: {total_trials_added}")
            logger.info(f"   - Total indications added: {total_indications_added}")
            
        finally:
            db.close()
    
    async def _search_and_add_trials_for_drug(self, db: Session, drug: Drug) -> tuple[int, int]:
        """Search and add clinical trials for a specific drug."""
        trials_added = 0
        indications_added = 0
        
        # Search terms to try
        search_terms = [
            drug.generic_name,
            drug.brand_name if drug.brand_name else None,
            f"{drug.generic_name} cancer",
            f"{drug.generic_name} oncology",
            f"{drug.generic_name} tumor"
        ]
        
        # Remove None values
        search_terms = [term for term in search_terms if term]
        
        for search_term in search_terms:
            try:
                logger.info(f"   Searching for: {search_term}")
                
                # Search ClinicalTrials.gov
                trials = await self._search_clinical_trials(search_term)
                
                for trial_data in trials:
                    # Check if trial already exists
                    existing_trial = db.query(ClinicalTrial).filter(
                        ClinicalTrial.nct_id == trial_data['nct_id']
                    ).first()
                    
                    if existing_trial:
                        # Link existing trial to drug if not already linked
                        if existing_trial.drug_id is None:
                            existing_trial.drug_id = drug.id
                            trials_added += 1
                            logger.info(f"     ✅ Linked existing trial: {trial_data['nct_id']}")
                        else:
                            logger.info(f"     ⚠️ Trial already linked: {trial_data['nct_id']}")
                    else:
                        # Create new trial
                        trial = ClinicalTrial(
                            nct_id=trial_data['nct_id'],
                            title=trial_data['title'],
                            status=trial_data.get('status', 'Unknown'),
                            phase=trial_data.get('phase', 'Unknown'),
                            drug_id=drug.id
                        )
                        db.add(trial)
                        trials_added += 1
                        logger.info(f"     ✅ Added new trial: {trial_data['nct_id']}")
                    
                    # Extract indications from title
                    if trial_data.get('title'):
                        extracted_indications = self._extract_indications_from_title(trial_data['title'])
                        for indication_text in extracted_indications:
                            indication_added = await self._add_indication_to_drug(db, drug, indication_text)
                            if indication_added:
                                indications_added += 1
                
                # Commit after each search term
                db.commit()
                
                # Small delay between searches
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"     ❌ Error searching for '{search_term}': {e}")
                db.rollback()
                continue
        
        return trials_added, indications_added
    
    def _extract_indications_from_title(self, title: str) -> List[str]:
        """Extract indication information from clinical trial title."""
        indications = []
        
        # Common cancer types and conditions to look for
        cancer_patterns = [
            r'\b(?:breast|lung|prostate|colorectal|gastric|gastroesophageal|esophageal|hepatocellular|renal|bladder|ovarian|cervical|endometrial|melanoma|lymphoma|leukemia|myeloma|sarcoma|glioma|glioblastoma)\s+cancer\b',
            r'\b(?:breast|lung|prostate|colorectal|gastric|gastroesophageal|esophageal|hepatocellular|renal|bladder|ovarian|cervical|endometrial|melanoma|lymphoma|leukemia|myeloma|sarcoma|glioma|glioblastoma)\s+carcinoma\b',
            r'\b(?:breast|lung|prostate|colorectal|gastric|gastroesophageal|esophageal|hepatocellular|renal|bladder|ovarian|cervical|endometrial|melanoma|lymphoma|leukemia|myeloma|sarcoma|glioma|glioblastoma)\s+tumor\b',
            r'\b(?:NSCLC|SCLC|TNBC|HER2|ER|PR|MSI-H|dMMR|TMB-H)\b',  # Biomarker patterns
            r'\b(?:metastatic|advanced|recurrent|refractory|unresectable)\b',  # Disease stage
            r'\b(?:solid\s+tumors?|hematologic\s+malignancies?)\b',  # General categories
        ]
        
        title_lower = title.lower()
        
        for pattern in cancer_patterns:
            matches = re.findall(pattern, title_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                if match and len(match.strip()) > 2:
                    indications.append(match.strip())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_indications = []
        for indication in indications:
            if indication not in seen:
                seen.add(indication)
                unique_indications.append(indication)
        
        return unique_indications
    
    async def _add_indication_to_drug(self, db: Session, drug: Drug, indication_text: str) -> bool:
        """Add an indication to a drug if it doesn't already exist."""
        try:
            # Check if indication already exists
            existing_indication = db.query(Indication).filter(
                Indication.name.ilike(f"%{indication_text}%")
            ).first()
            
            if not existing_indication:
                # Create new indication
                indication = Indication(
                    name=indication_text,
                    indication_type="cancer" if any(cancer in indication_text.lower() for cancer in ['cancer', 'carcinoma', 'tumor', 'malignancy']) else "other"
                )
                db.add(indication)
                db.flush()  # Get the ID
                existing_indication = indication
                logger.info(f"     📝 Created new indication: {indication_text}")
            
            # Check if drug-indication relationship already exists
            existing_relationship = db.query(DrugIndication).filter(
                DrugIndication.drug_id == drug.id,
                DrugIndication.indication_id == existing_indication.id
            ).first()
            
            if not existing_relationship:
                # Create drug-indication relationship
                drug_indication = DrugIndication(
                    drug_id=drug.id,
                    indication_id=existing_indication.id,
                    approval_status=False,  # Clinical trial indication, not FDA approved
                    source="clinical_trials"
                )
                db.add(drug_indication)
                logger.info(f"     🔗 Linked indication to drug: {indication_text}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"     ❌ Error adding indication '{indication_text}': {e}")
            return False
    
    async def _search_clinical_trials(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search ClinicalTrials.gov for trials related to a search term."""
        try:
            params = {
                "format": "json",
                "query.cond": search_term,
                "pageSize": limit
            }
            
            response = self.session.get(self.base_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                studies = data.get('studies', [])
                
                trials = []
                for study in studies:
                    protocol_section = study.get('protocolSection', {})
                    identification_module = protocol_section.get('identificationModule', {})
                    
                    trial_data = {
                        'nct_id': identification_module.get('nctId', ''),
                        'title': identification_module.get('briefTitle', ''),
                        'status': self._extract_status(study),
                        'phase': self._extract_phase(study)
                    }
                    
                    if trial_data['nct_id']:
                        trials.append(trial_data)
                
                return trials
            else:
                logger.warning(f"API request failed with status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching clinical trials: {e}")
            return []
    
    def _extract_status(self, study: Dict[str, Any]) -> str:
        """Extract trial status from study data."""
        try:
            status_module = study.get('protocolSection', {}).get('statusModule', {})
            return status_module.get('overallStatus', 'Unknown')
        except:
            return 'Unknown'
    
    def _extract_phase(self, study: Dict[str, Any]) -> str:
        """Extract trial phase from study data."""
        try:
            design_module = study.get('protocolSection', {}).get('designModule', {})
            phases = design_module.get('phases', [])
            if phases:
                return phases[0]
            return 'Unknown'
        except:
            return 'Unknown'


async def main():
    """Main function to populate clinical trials."""
    populator = ClinicalTrialsPopulatorV2()
    await populator.populate_all_drug_trials()


if __name__ == "__main__":
    asyncio.run(main())
