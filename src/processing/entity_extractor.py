"""
Entity extraction module for processing collected documents and creating structured entities.
"""

import re
import json
import asyncio
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from ..models.entities import (
    Document, Drug, Company, ClinicalTrial, Target, 
    DrugTarget, DrugIndication, Indication
)
from ..models.database import get_db
from ..data_collection.config import APIConfig


class EntityExtractor:
    """Extracts structured entities from collected documents."""
    
    def __init__(self, db: Session):
        self.db = db
        
    def extract_all_entities(self) -> Dict[str, int]:
        """Extract all entities from documents and return counts."""
        logger.info("Starting entity extraction from all documents...")
        
        # Get all documents and initialize stats
        documents = self.db.query(Document).all()
        logger.info(f"Processing {len(documents)} documents...")
        
        stats = self._initialize_extraction_stats()
        
        # Process each document
        for doc in documents:
            try:
                self._process_single_document(doc, stats)
            except Exception as e:
                logger.error(f"Error processing document {doc.id}: {e}")
                continue
        
        # Create relationships and finalize
        self._finalize_extraction(stats)
        
        return stats
    
    def _initialize_extraction_stats(self) -> Dict[str, int]:
        """Initialize extraction statistics."""
        return {
            "drugs_created": 0,
            "clinical_trials_created": 0,
            "targets_created": 0,
            "relationships_created": 0
        }
        
    def _process_single_document(self, doc: Document, stats: Dict[str, int]) -> None:
        """Process a single document for entity extraction."""
                # Extract clinical trials from any document that contains NCT codes
                if "NCT" in doc.content:
                    self._extract_clinical_trial_entities(doc)
                    stats["clinical_trials_created"] += 1
                
        # Extract entities based on document type (only for existing seed companies)
                if doc.source_type in ["company_about", "company_pipeline", "company_products", "company_oncology"]:
            self._extract_company_entities(doc)  # Only extracts drugs from pipeline docs for seed companies
                elif doc.source_type in ["fda_drug_approval", "fda_comprehensive_approval", "drugs_com_profile"]:
                    self._extract_drug_entities(doc)
                    stats["drugs_created"] += 1
                    
    def _finalize_extraction(self, stats: Dict[str, int]) -> None:
        """Finalize the extraction process."""
        # Create relationships between entities
        self._create_relationships()
        stats["relationships_created"] = 1
        
        self.db.commit()
        logger.info(f"Entity extraction completed: {stats}")
    
    def _extract_company_entities(self, doc: Document):
        """Extract drugs from company pipeline documents for existing seed companies only."""
        # Find existing company from seed data
        company_name = self._extract_company_name(doc.title, doc.content)
        if not company_name:
            return
            
        company = self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
        
        if not company:
            logger.debug(f"Skipping document for unknown company: {company_name}")
            return
        
        # Extract drugs from company pipeline documents only
        if doc.source_type == "company_pipeline":
            drugs = self._extract_drugs_from_company_pipeline(doc.content, company.id)
            for drug_info in drugs:
                self._create_drug_entity(drug_info, company.id)
    
    def _extract_drug_entities(self, doc: Document):
        """Extract drug information from FDA and Drugs.com documents."""
        content = doc.content
        
        # Extract drug information
        drug_info = self._parse_drug_document(doc)
        if drug_info:
            # Find or create company
            company = self._find_or_create_company_for_drug(drug_info, doc)
            if company:
                self._create_drug_entity(drug_info, company.id)
    
    def _extract_clinical_trial_entities(self, doc: Document):
        """Extract clinical trial information from documents containing NCT codes."""
        content = doc.content
        
        # Extract all NCT IDs from the document
        nct_ids = self._extract_all_nct_ids(content)
        if not nct_ids:
            return
            
        logger.info(f"Found {len(nct_ids)} NCT codes in document {doc.id}")
        
        for nct_id in nct_ids:
            try:
                # Check if trial already exists
                existing_trial = self.db.query(ClinicalTrial).filter(
                    ClinicalTrial.nct_id == nct_id
                ).first()
                
                if existing_trial:
                    logger.debug(f"Trial {nct_id} already exists, skipping")
                    continue
                    
                # Extract trial information
                trial_info = self._parse_clinical_trial_document(doc, nct_id)
                if trial_info:
                    # Find associated company
                    company = self._find_company_for_trial(trial_info, doc)
                    
                    trial = ClinicalTrial(
                        nct_id=nct_id,
                        title=trial_info.get("title", ""),
                        status=trial_info.get("status", ""),
                        phase=trial_info.get("phase", ""),
                        sponsor_id=company.id if company else None,
                        study_population=json.dumps(trial_info.get("conditions", [])),
                        primary_endpoints=json.dumps(trial_info.get("interventions", []))
                    )
                    self.db.add(trial)
                    logger.info(f"Created clinical trial: {nct_id}")
                    
            except Exception as e:
                logger.error(f"Error processing NCT {nct_id}: {e}")
                continue
    
    def _extract_company_name(self, title: str, content: str) -> Optional[str]:
        """Extract company name from title or content."""
        # Common company name patterns
        patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Corporation|Company|Co|Ltd|Limited|Pharmaceuticals|Pharma|Biotech|Biotechnology)",
            r"(?:About|Company|Overview)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Pipeline|Products|Research)"
        ]
        
        text = f"{title} {content}"
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if name.lower() not in ["the", "and", "or", "for", "with", "by"]:
                    return name
        
        # Fallback: extract from URL using dictionary mapping
        content_lower = content.lower()
        company_mappings = {
            "merck": "Merck & Co.",
            "bristol": "Bristol Myers Squibb",
            "myers": "Bristol Myers Squibb", 
            "roche": "Roche",
            "pfizer": "Pfizer"
        }
        
        for keyword, company_name in company_mappings.items():
            if keyword in content_lower:
                return company_name
        
        return None
    
    def _extract_drugs_from_company_pipeline(self, content: str, company_id: int) -> List[Dict[str, Any]]:
        """Extract drug information from company pipeline content."""
        drugs = []
        
        # Known drug patterns from our previous extraction
        drug_patterns = [
            r"([A-Z][a-z]+(?:mab|nib|tinib|cept|zumab|ximab))",
            r"(MK-\d+)",
            r"(RG\d+)",
            r"([A-Z][a-z]+(?:deruxtecan|vedotin|tirumotecan))",
            r"(pembrolizumab|nivolumab|sotatercept|patritumab|sacituzumab|zilovertamab|nemtabrutinib|quavonlimab|clesrovimab|ifinatamab|bezlotoxumab)",
        ]
        
        found_drugs = set()
        for pattern in drug_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if self._validate_drug_name(match):
                    found_drugs.add(match)
        
        # Convert to drug info dictionaries
        for drug_name in found_drugs:
            drugs.append({
                "generic_name": drug_name,
                "brand_name": None,
                "drug_class": self._infer_drug_class(drug_name),
                "mechanism_of_action": self._extract_mechanism_from_content(drug_name, content),
                "fda_approval_status": False,
                "fda_approval_date": None,
                "nct_codes": self._extract_nct_codes_for_drug(drug_name, content)
            })
        
        return drugs
    
    def _parse_drug_document(self, doc: Document) -> Optional[Dict[str, Any]]:
        """Parse drug information from FDA or Drugs.com documents."""
        content = doc.content
        
        # Extract drug name from title or content
        drug_name = self._extract_drug_name_from_content(content, doc.title)
        if not drug_name:
            return None
        
        # Extract FDA approval information
        fda_approved = "approval" in content.lower() or "approved" in content.lower()
        approval_date = self._extract_approval_date(content)
        
        # Extract drug class
        drug_class = self._extract_drug_class_from_content(content)
        
        # Extract mechanism of action
        mechanism = self._extract_mechanism_from_content(drug_name, content)
        
        return {
            "generic_name": drug_name,
            "brand_name": self._extract_brand_name(content),
            "drug_class": drug_class,
            "mechanism_of_action": mechanism,
            "fda_approval_status": fda_approved,
            "fda_approval_date": approval_date,
            "nct_codes": []
        }
    
    def _parse_clinical_trial_document(self, doc: Document, nct_id: str = None) -> Optional[Dict[str, Any]]:
        """Parse clinical trial information from documents."""
        content = doc.content
        
        # Extract title
        title = doc.title
        if not title or len(title) < 10:
            title = self._extract_trial_title_from_content(content, nct_id)
        
        # Extract status
        status = self._extract_trial_status(content)
        
        # Extract phase
        phase = self._extract_trial_phase(content)
        
        # Extract interventions
        interventions = self._extract_trial_interventions(content)
        
        # Extract conditions
        conditions = self._extract_trial_conditions(content)
        
        return {
            "title": title,
            "status": status,
            "phase": phase,
            "interventions": interventions,
            "conditions": conditions
        }
    
    def _create_drug_entity(self, drug_info: Dict[str, Any], company_id: int):
        """Create a drug entity in the database."""
        # Check if drug already exists
        existing_drug = self.db.query(Drug).filter(
            Drug.generic_name.ilike(f"%{drug_info['generic_name']}%")
        ).first()
        
        if existing_drug:
            self._update_existing_drug(existing_drug, drug_info, company_id)
        else:
            self._create_new_drug(drug_info, company_id)
    
    def _update_existing_drug(self, existing_drug: Drug, drug_info: Dict[str, Any], company_id: int):
        """Update an existing drug with new information."""
            existing_drug.brand_name = drug_info.get("brand_name") or existing_drug.brand_name
            existing_drug.drug_class = drug_info.get("drug_class") or existing_drug.drug_class
            existing_drug.mechanism_of_action = drug_info.get("mechanism_of_action") or existing_drug.mechanism_of_action
            existing_drug.fda_approval_status = drug_info.get("fda_approval_status", existing_drug.fda_approval_status)
            existing_drug.fda_approval_date = drug_info.get("fda_approval_date") or existing_drug.fda_approval_date
            existing_drug.nct_codes = drug_info.get("nct_codes", [])
            existing_drug.company_id = company_id
    
    def _create_new_drug(self, drug_info: Dict[str, Any], company_id: int):
        """Create a new drug entity."""
            drug = Drug(
                generic_name=drug_info["generic_name"],
                brand_name=drug_info.get("brand_name"),
                drug_class=drug_info.get("drug_class"),
                mechanism_of_action=drug_info.get("mechanism_of_action"),
                fda_approval_status=drug_info.get("fda_approval_status", False),
                fda_approval_date=drug_info.get("fda_approval_date"),
                company_id=company_id,
                nct_codes=drug_info.get("nct_codes", []),
                created_at=datetime.utcnow()
            )
            self.db.add(drug)
    
    def _create_relationships(self):
        """Create relationships between entities."""
        # Link drugs to clinical trials via NCT codes
        drugs = self.db.query(Drug).all()
        trials = self.db.query(ClinicalTrial).all()
        
        for drug in drugs:
            if drug.nct_codes:
                for nct_code in drug.nct_codes:
                    trial = next((t for t in trials if t.nct_id == nct_code), None)
                    if trial and not any(ct.drug_id == drug.id for ct in drug.clinical_trials):
                        # Create relationship
                        drug.clinical_trials.append(trial)
    
    # Helper methods for extraction
    def _extract_drug_name_from_content(self, content: str, title: str) -> Optional[str]:
        """Extract drug name from content or title."""
        # Try title first
        if title and len(title) < 100:
            return title.strip()
        
        # Look for drug name patterns in content
        patterns = [
            r"([A-Z][a-z]+(?:mab|nib|tinib|cept|zumab|ximab))",
            r"(MK-\d+)",
            r"(RG\d+)",
            r"(pembrolizumab|nivolumab|sotatercept|patritumab|sacituzumab|zilovertamab|nemtabrutinib|quavonlimab|clesrovimab|ifinatamab|bezlotoxumab)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_brand_name(self, content: str) -> Optional[str]:
        """Extract brand name from content."""
        # Look for brand name patterns
        patterns = [
            r"brand name[:\s]+([A-Z][a-z]+)",
            r"trademark[:\s]+([A-Z][a-z]+)",
            r"commercially known as[:\s]+([A-Z][a-z]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_drug_class_from_content(self, content: str) -> Optional[str]:
        """Extract drug class from content."""
        drug_classes = [
            "monoclonal antibody", "small molecule", "ADC", "antibody-drug conjugate",
            "therapeutic protein", "peptide", "vaccine", "bispecific antibody"
        ]
        
        content_lower = content.lower()
        for drug_class in drug_classes:
            if drug_class in content_lower:
                return drug_class.title()
        
        return None
    
    def _extract_mechanism_from_content(self, drug_name: str, content: str) -> Optional[str]:
        """Extract mechanism of action for a specific drug."""
        # Look for mechanism patterns near the drug name
        drug_pos = content.lower().find(drug_name.lower())
        if drug_pos == -1:
            return None
        
        # Get context around the drug name
        start = max(0, drug_pos - 200)
        end = min(len(content), drug_pos + 200)
        context = content[start:end]
        
        # Look for mechanism patterns
        patterns = [
            r"inhibits?\s+([^.]{10,100})",
            r"blocks?\s+([^.]{10,100})",
            r"targets?\s+([^.]{10,100})",
            r"binds?\s+to\s+([^.]{10,100})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_approval_date(self, content: str) -> Optional[datetime]:
        """Extract FDA approval date from content."""
        patterns = [
            r"approved[:\s]+(\d{4})",
            r"approval[:\s]+(\d{4})",
            r"(\d{4})[:\s]+approval",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    year = int(match.group(1))
                    return datetime(year, 1, 1)  # Use January 1st as default
                except ValueError:
                    continue
        
        return None
    
    def _extract_nct_id(self, content: str) -> Optional[str]:
        """Extract first NCT ID from content."""
        pattern = r"NCT\d{8}"
        match = re.search(pattern, content)
        return match.group(0) if match else None
    
    def _extract_all_nct_ids(self, content: str) -> List[str]:
        """Extract all NCT IDs from content."""
        pattern = r"NCT\d{8}"
        matches = re.findall(pattern, content)
        return list(set(matches))  # Remove duplicates
    
    def _extract_nct_codes_for_drug(self, drug_name: str, content: str) -> List[str]:
        """Extract NCT codes associated with a specific drug."""
        nct_codes = []
        pattern = r"NCT\d{8}"
        matches = re.findall(pattern, content)
        
        # Find NCT codes near the drug name
        drug_pos = content.lower().find(drug_name.lower())
        if drug_pos != -1:
            for match in matches:
                nct_pos = content.find(match)
                if abs(nct_pos - drug_pos) < 500:  # Within 500 characters
                    nct_codes.append(match)
        
        return list(set(nct_codes))
    
    def _extract_trial_title_from_content(self, content: str, nct_id: str = None) -> str:
        """Extract trial title from content."""
        # Look for title patterns
        patterns = [
            r"title[:\s]+([^\n]{10,200})",
            r"study[:\s]+([^\n]{10,200})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If we have an NCT ID, create a more descriptive title
        if nct_id:
            return f"Clinical Trial {nct_id}"
        
        return "Clinical Trial"
    
    def _extract_trial_status(self, content: str) -> str:
        """Extract trial status from content."""
        statuses = ["recruiting", "completed", "active", "suspended", "terminated", "withdrawn"]
        content_lower = content.lower()
        
        for status in statuses:
            if status in content_lower:
                return status.title()
        
        return "Unknown"
    
    def _extract_trial_phase(self, content: str) -> str:
        """Extract trial phase from content."""
        patterns = [
            r"phase\s+([12])",
            r"phase\s+([12])\s+clinical",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return f"Phase {match.group(1)}"
        
        return "Unknown"
    
    def _extract_trial_interventions(self, content: str) -> List[str]:
        """Extract trial interventions from content."""
        interventions = []
        
        # Look for intervention patterns
        patterns = [
            r"intervention[:\s]+([^\n]{5,100})",
            r"drug[:\s]+([^\n]{5,100})",
            r"treatment[:\s]+([^\n]{5,100})",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                interventions.append(match.strip())
        
        return interventions[:5]  # Limit to 5 interventions
    
    def _extract_trial_conditions(self, content: str) -> List[str]:
        """Extract trial conditions from content."""
        conditions = []
        
        # Look for condition patterns
        patterns = [
            r"condition[:\s]+([^\n]{5,100})",
            r"disease[:\s]+([^\n]{5,100})",
            r"cancer[:\s]+([^\n]{5,100})",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                conditions.append(match.strip())
        
        return conditions[:5]  # Limit to 5 conditions
    
    def _find_or_create_company_for_drug(self, drug_info: Dict[str, Any], doc: Document) -> Optional[Company]:
        """Find existing company for a drug. Only uses companies from seed data - does not create new ones."""
        # Try to extract company name from document
        company_name = self._extract_company_name(doc.title, doc.content)
        if not company_name:
            # Default companies based on drug names
            drug_name = drug_info["generic_name"].lower()
            if "keytruda" in drug_name or "pembrolizumab" in drug_name:
                company_name = "Merck & Co"  # Must match seed data
            elif "opdivo" in drug_name or "nivolumab" in drug_name:
                company_name = "Bristol Myers Squibb"
            else:
                return None
        
        # Only find existing company from seed data - do not create new ones
        company = self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
        
        if not company:
            logger.debug(f"Skipping drug {drug_info.get('generic_name')} - company {company_name} not in seed data")
        
        return company
    
    def _find_company_for_trial(self, trial_info: Dict[str, Any], doc: Document) -> Optional[Company]:
        """Find company for a clinical trial."""
        # Try to extract company name from document
        company_name = self._extract_company_name(doc.title, doc.content)
        if not company_name:
            return None
        
        return self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
    
    def _validate_drug_name(self, name: str) -> bool:
        """Validate if a name is likely a drug name."""
        # Basic validation checks
        if not self._basic_name_validation(name):
            return False
        
        # Exclusion pattern checks
        if self._matches_exclusion_patterns(name):
            return False
        
        # Positive drug indicators
        return self._has_drug_indicators(name)
    
    def _basic_name_validation(self, name: str) -> bool:
        """Perform basic name validation checks."""
        # Length check
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Character validation
        if not re.match(r'^[A-Za-z0-9\-\s\/\(\)]+$', name):
            return False
        
        return True
    
    def _matches_exclusion_patterns(self, name: str) -> bool:
        """Check if name matches exclusion patterns."""
        # Clinical trial IDs
        if re.match(r'^NCT\d+', name.upper()):
            return True
        
        # Study names and codes
        if re.match(r'^(Lung|Breast|PanTumor|Prostate|GI|Ovarian|Esophageal)\d+$', name):
            return True
        
        # Generic protein/antibody terms
        generic_terms = {
            'ig', 'igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga', 'parp1', 'parp2', 'parp3',
            'tyk2', 'cdh6', 'ror1', 'her3', 'trop2', 'pcsk9', 'ov65'
        }
        if name.lower() in generic_terms:
            return True
        
        # Common false positives
        false_positives = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'must', 'shall', 'accept', 'except', 'decline'
        }
        if name.lower() in false_positives:
            return True
        
        # Incomplete endings
        incomplete_endings = [' is', ' was', ' being', ' an', ' a', ' the', ' and', ' or']
        if any(name.endswith(ending) for ending in incomplete_endings):
            return True
        
        # Descriptive phrases
        descriptive_phrases = ['drug conjugate', 'small molecule', 'therapeutic protein', 'bispecific antibody', 'peptide']
        if any(phrase in name.lower() for phrase in descriptive_phrases):
            return True
        
            return False
        
    def _has_drug_indicators(self, name: str) -> bool:
        """Check if name has positive drug indicators."""
        drug_indicators = [
            # Monoclonal antibodies
            name.lower().endswith(('mab', 'zumab', 'ximab')),
            # Kinase inhibitors
            name.lower().endswith(('nib', 'tinib')),
            # Fusion proteins
            name.lower().endswith('cept'),
            # CAR-T therapies
            name.lower().endswith('leucel'),
            # ADCs (Antibody Drug Conjugates)
            any(adc in name.lower() for adc in ['deruxtecan', 'vedotin', 'tirumotecan']),
            # Specific known drugs
            name.lower() in {
                'pembrolizumab', 'nivolumab', 'sotatercept', 'patritumab', 'sacituzumab',
                'zilovertamab', 'nemtabrutinib', 'quavonlimab', 'clesrovimab', 'ifinatamab',
                'bezlotoxumab', 'ipilimumab', 'relatlimab', 'enasicon', 'dasatinib',
                'repotrectinib', 'elotuzumab', 'belatacept', 'fedratinib', 'luspatercept',
                'abatacept', 'deucravacitinib', 'trastuzumab', 'atezolizumab', 'avelumab',
                'blinatumomab', 'dupilumab', 'ruxolitinib', 'tisagenlecleucel', 'yescarta',
                'kymriah', 'carvykti', 'abecma', 'breyanzi'
            },
            # Company drug codes
            re.match(r'^mk-\d+', name.lower()) or re.match(r'^rg\d+', name.lower()),
            # Multi-word drug names
            len(name.split()) >= 2 and any(word.endswith(('mab', 'nib', 'tinib', 'cept', 'leucel')) for word in name.split()),
        ]
        
        return any(drug_indicators)
    
    def _infer_drug_class(self, drug_name: str) -> str:
        """Infer drug class from drug name."""
        name_lower = drug_name.lower()
        
        # Define drug class mappings
        class_mappings = {
            # Monoclonal Antibodies
            ('mab', 'zumab', 'ximab'): "Monoclonal Antibody",
            # Small Molecules
            ('nib', 'tinib'): "Small Molecule",
            # ADCs
            ('deruxtecan', 'vedotin'): "ADC",
            # Company codes
            ('mk-', 'rg'): "Small Molecule"
        }
        
        # Check suffixes first
        for suffixes, drug_class in class_mappings.items():
            if any(name_lower.endswith(suffix) for suffix in suffixes):
                return drug_class
        
        # Check prefixes
        if name_lower.startswith(('mk-', 'rg')):
            return "Small Molecule"
        
        # Check for specific patterns
        if any(pattern in name_lower for pattern in ['deruxtecan', 'vedotin']):
            return "ADC"
        
        return "Unknown"


    def _create_drug_from_data(self, drug_data: Dict[str, Any], company: Company) -> Drug:
        """Create a drug entity from structured data."""
        drug = Drug(
            generic_name=drug_data["generic_name"],
            brand_name=drug_data.get("brand_name"),
            drug_class=drug_data["drug_class"],
            mechanism_of_action=drug_data["mechanism_of_action"],
            fda_approval_status=drug_data["fda_approval_status"],
            fda_approval_date=drug_data.get("fda_approval_date"),
            company_id=company.id,
            created_at=datetime.utcnow()
        )
        self.db.add(drug)
        self.db.flush()
        
        # Add targets
        for target_name in drug_data.get("targets", []):
            target = self._get_or_create_target(target_name)
            drug_target = DrugTarget(drug_id=drug.id, target_id=target.id)
            self.db.add(drug_target)
        
        # Add indications
        for indication_name in drug_data.get("indications", []):
            indication = self._get_or_create_indication(indication_name)
            drug_indication = DrugIndication(drug_id=drug.id, indication_id=indication.id)
            self.db.add(drug_indication)
        
        # Add NCT codes
        if drug_data.get("nct_codes"):
            drug.nct_codes = ",".join(drug_data["nct_codes"])
        
        return drug

    def _get_or_create_target(self, target_name: str) -> Target:
        """Get existing target or create new one."""
        target = self.db.query(Target).filter(
            Target.name.ilike(f"%{target_name}%")
        ).first()
        
        if not target:
            target = Target(
                name=target_name,
                created_at=datetime.utcnow()
            )
            self.db.add(target)
            self.db.flush()
        
        return target

    def _get_or_create_indication(self, indication_name: str) -> Indication:
        """Get existing indication or create new one."""
        indication = self.db.query(Indication).filter(
            Indication.name.ilike(f"%{indication_name}%")
        ).first()
        
        if not indication:
            indication = Indication(
                name=indication_name,
                created_at=datetime.utcnow()
            )
            self.db.add(indication)
            self.db.flush()
        
        return indication

    async def extract_fda_indications_for_drugs(self, drug_names: Optional[List[str]] = None) -> Dict[str, int]:
        """Extract FDA approved indications for drugs and update database.
        
        Args:
            drug_names: Optional list of drug names to process. If None, processes all drugs in database.
            
        Returns:
            Dictionary with extraction statistics.
        """
        logger.info("Starting FDA indication extraction...")
        
        # Get drugs to process
        if drug_names:
            drugs = self.db.query(Drug).filter(Drug.generic_name.in_(drug_names)).all()
        else:
            # Get all unique drugs from database
            drugs = self.db.query(Drug).distinct(Drug.generic_name).all()
        
        logger.info(f"📊 Found {len(drugs)} drugs to process")
        
        stats = {
            "drugs_processed": 0,
            "indications_extracted": 0,
            "indications_created": 0,
            "relationships_created": 0
        }
        
        # Process each drug
        for drug in drugs:
            try:
                indications = await self._extract_fda_indications_for_drug(drug.generic_name)
                if indications:
                    created, relationships = self._update_drug_indications(drug, indications)
                    stats["indications_extracted"] += len(indications)
                    stats["indications_created"] += created
                    stats["relationships_created"] += relationships
                    stats["drugs_processed"] += 1
            except Exception as e:
                logger.error(f"Error extracting FDA indications for {drug.generic_name}: {e}")
                continue
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        self.db.commit()
        logger.info(f"✅ FDA indication extraction completed: {stats}")
        return stats
    
    async def _extract_fda_indications_for_drug(self, drug_name: str) -> List[str]:
        """Extract approved indications for a single drug from FDA API."""
        indications = []
        
        try:
            # Search FDA API by generic name
            fda_data = await self._search_fda_database(f'openfda.generic_name:"{drug_name}"')
            
            if not fda_data:
                # Try brand name
                fda_data = await self._search_fda_database(f'openfda.brand_name:"{drug_name}"')
            
            if not fda_data:
                # Try substance name
                fda_data = await self._search_fda_database(f'openfda.substance_name:"{drug_name}"')
            
            if not fda_data:
                logger.debug(f"No FDA data found for {drug_name}")
                return indications
            
            # Extract indications from all FDA results
            for result in fda_data:
                drug_indications = self._parse_fda_approval_indications(result, drug_name)
                indications.extend(drug_indications)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_indications = []
            for ind in indications:
                ind_lower = ind.lower().strip()
                if ind_lower and ind_lower not in seen:
                    seen.add(ind_lower)
                    unique_indications.append(ind)
            
            if unique_indications:
                logger.info(f"✅ Extracted {len(unique_indications)} indications for {drug_name}")
            
            return unique_indications
            
        except Exception as e:
            logger.error(f"Error extracting indications for {drug_name}: {e}")
            return []
    
    def _parse_fda_approval_indications(self, fda_result: Dict[str, Any], drug_name: str) -> List[str]:
        """Parse FDA result to extract indication approved text."""
        indications = []
        drug_name_lower = drug_name.lower()
        
        # Get all text fields from FDA result
        text_fields = [
            fda_result.get("description", []),
            fda_result.get("indications_and_usage", []),
            fda_result.get("recent_major_changes", []),
            fda_result.get("purpose", []),
        ]
        
        # Check openfda section for brand/generic names
        openfda = fda_result.get("openfda", {})
        brand_names = openfda.get("brand_name", []) if openfda else []
        generic_names = openfda.get("generic_name", []) if openfda else []
        
        # Flatten text fields
        all_text = []
        for field in text_fields:
            if isinstance(field, list):
                all_text.extend(field)
            elif isinstance(field, str):
                all_text.append(field)
        
        # Search for FDA approval patterns
        for text in all_text:
            if not text or not isinstance(text, str):
                continue
            
            text_lower = text.lower()
            
            # Check if drug name is mentioned
            if drug_name_lower not in text_lower:
                brand_match = any(name.lower() in text_lower for name in brand_names if name)
                generic_match = any(name.lower() in text_lower for name in generic_names if name)
                if not (brand_match or generic_match):
                    continue
            
            # Pattern 1: "FDA approves [drug] for [indication]"
            pattern1 = rf"FDA\s+approves\s+(?:{re.escape(drug_name)}\s+and\s+[\w\s-]+|{re.escape(drug_name)})\s+for\s+([^.,;]+?)(?:\.|,|;|$)"
            matches = re.finditer(pattern1, text, re.IGNORECASE)
            for match in matches:
                indication = match.group(1).strip()
                indication = re.sub(r'\s+', ' ', indication).strip(',;:')
                if indication and 5 < len(indication) < 200:
                    indications.append(indication)
            
            # Pattern 2: "FDA approves [drug]" followed by "for [indication]"
            pattern2 = rf"FDA\s+approves\s+{re.escape(drug_name)}[^.]*?for\s+([^.,;]+?)(?:\.|,|;|$)"
            matches = re.finditer(pattern2, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                indication = match.group(1).strip()
                indication = re.sub(r'\s+', ' ', indication).strip(',;:')
                if indication and 5 < len(indication) < 200:
                    indications.append(indication)
            
            # Pattern 3: Extract from structured indication fields
            if "indication" in text_lower[:100]:
                indication_patterns = [
                    r"for\s+the\s+treatment\s+of\s+([^.,;]+?)(?:\.|,|;|$)",
                    r"for\s+treatment\s+of\s+([^.,;]+?)(?:\.|,|;|$)",
                    r"indicated\s+for\s+([^.,;]+?)(?:\.|,|;|$)",
                    r"approved\s+for\s+([^.,;]+?)(?:\.|,|;|$)",
                ]
                
                for pattern in indication_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        indication = match.group(1).strip()
                        indication = re.sub(r'\s+', ' ', indication).strip(',;:')
                        if (indication and 5 < len(indication) < 200 and
                            not any(word in indication.lower() for word in ['see', 'refer', 'section', 'package'])):
                            indications.append(indication)
        
        return indications
    
    async def _search_fda_database(self, search_query: str) -> List[Dict[str, Any]]:
        """Search FDA drug label database."""
        try:
            url = f"{APIConfig.FDA_BASE_URL}{APIConfig.FDA_ENDPOINTS['drug_label']}"
            params = {
                "limit": 10,
                "search": search_query,
                "sort": "effective_time:desc"
            }
            
            response = await self._make_async_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                logger.debug(f"FDA API request failed: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching FDA database: {e}")
            return []
    
    async def _make_async_request(self, url: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        """Make asynchronous HTTP request."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params=params, timeout=30)
            )
            return response
        except Exception as e:
            logger.error(f"Error making async request to {url}: {e}")
            return None
    
    def _update_drug_indications(self, drug: Drug, indications: List[str]) -> tuple:
        """Update database with extracted FDA indications.
        
        Returns:
            Tuple of (indications_created, relationships_created)
        """
        created = 0
        relationships = 0
        
        for indication_text in indications:
            # Find or create indication
            indication = self.db.query(Indication).filter(
                Indication.name.ilike(f"%{indication_text}%")
            ).first()
            
            if not indication:
                indication = Indication(
                    name=indication_text,
                    created_at=datetime.utcnow()
                )
                self.db.add(indication)
                self.db.flush()
                created += 1
            
            # Check if DrugIndication relationship already exists
            existing = self.db.query(DrugIndication).filter(
                DrugIndication.drug_id == drug.id,
                DrugIndication.indication_id == indication.id
            ).first()
            
            if not existing:
                # Create DrugIndication relationship
                drug_indication = DrugIndication(
                    drug_id=drug.id,
                    indication_id=indication.id,
                    approval_status=True,  # From FDA, so approved
                    approval_date=datetime.utcnow()
                )
                self.db.add(drug_indication)
                relationships += 1
        
        # Update drug's FDA approval status if we found indications
        if not drug.fda_approval_status:
            drug.fda_approval_status = True
            drug.fda_approval_date = datetime.utcnow()
        
        return created, relationships


def run_entity_extraction():
    """Run entity extraction on all documents."""
    db = next(get_db())
    try:
        extractor = EntityExtractor(db)
        stats = extractor.extract_all_entities()
        
        print("Entity Extraction Results:")
        print("=" * 40)
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        return stats
    finally:
        db.close()


async def extract_fda_indications_for_all_drugs(drug_names: Optional[List[str]] = None):
    """Extract FDA indications for all drugs in database.
    
    Args:
        drug_names: Optional list of specific drug names to process.
                    If None, processes all drugs in database.
    
    Example:
        # Extract for all drugs
        asyncio.run(extract_fda_indications_for_all_drugs())
        
        # Extract for specific drugs
        asyncio.run(extract_fda_indications_for_all_drugs(["pembrolizumab", "nivolumab"]))
    """
    db = next(get_db())
    try:
        extractor = EntityExtractor(db)
        stats = await extractor.extract_fda_indications_for_drugs(drug_names)
        
        print("FDA Indication Extraction Results:")
        print("=" * 40)
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    run_entity_extraction()
