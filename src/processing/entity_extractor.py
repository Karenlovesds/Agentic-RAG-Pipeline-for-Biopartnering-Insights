"""
Entity extraction module for processing collected documents and creating structured entities.
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from ..models.entities import (
    Document, Drug, Company, ClinicalTrial, Target, 
    DrugTarget, DrugIndication, Indication
)
from ..models.database import get_db


class EntityExtractor:
    """Extracts structured entities from collected documents."""
    
    def __init__(self, db: Session):
        self.db = db
        
    def extract_all_entities(self) -> Dict[str, int]:
        """Extract all entities from documents and return counts."""
        logger.info("Starting entity extraction from all documents...")
        
        # Get all documents
        documents = self.db.query(Document).all()
        logger.info(f"Processing {len(documents)} documents...")
        
        stats = {
            "companies_created": 0,
            "drugs_created": 0,
            "clinical_trials_created": 0,
            "targets_created": 0,
            "relationships_created": 0
        }
        
        for doc in documents:
            try:
                if doc.source_type in ["company_about", "company_pipeline", "company_products", "company_oncology"]:
                    self._extract_company_entities(doc)
                    stats["companies_created"] += 1
                    
                elif doc.source_type in ["fda_drug_approval", "fda_comprehensive_approval", "drugs_com_profile"]:
                    self._extract_drug_entities(doc)
                    stats["drugs_created"] += 1
                    
                elif doc.source_type in ["clinical_trials", "clinical_trial", "company_clinical_trials"]:
                    self._extract_clinical_trial_entities(doc)
                    stats["clinical_trials_created"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing document {doc.id}: {e}")
                continue
        
        # Create relationships between entities
        self._create_relationships()
        stats["relationships_created"] = 1
        
        self.db.commit()
        logger.info(f"Entity extraction completed: {stats}")
        return stats
    
    def _extract_company_entities(self, doc: Document):
        """Extract company information from company documents."""
        content = doc.content.lower()
        title = doc.title.lower()
        
        # Extract company name from title or content
        company_name = self._extract_company_name(doc.title, doc.content)
        if not company_name:
            return
            
        # Check if company already exists
        existing_company = self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
        
        if existing_company:
            company = existing_company
        else:
            # Create new company
            company = Company(
                name=company_name,
                website_url=doc.source_url,
                description=self._extract_company_description(doc.content),
                created_at=datetime.utcnow()
            )
            self.db.add(company)
            self.db.flush()  # Get the ID
        
        # Extract drugs from company pipeline documents
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
        """Extract clinical trial information."""
        content = doc.content
        
        # Extract NCT ID
        nct_id = self._extract_nct_id(content)
        if not nct_id:
            return
            
        # Check if trial already exists
        existing_trial = self.db.query(ClinicalTrial).filter(
            ClinicalTrial.nct_id == nct_id
        ).first()
        
        if existing_trial:
            return
            
        # Extract trial information
        trial_info = self._parse_clinical_trial_document(doc)
        if trial_info:
            # Find associated company
            company = self._find_company_for_trial(trial_info, doc)
            
            trial = ClinicalTrial(
                nct_id=nct_id,
                title=trial_info.get("title", ""),
                status=trial_info.get("status", ""),
                phase=trial_info.get("phase", ""),
                interventions=trial_info.get("interventions", []),
                conditions=trial_info.get("conditions", []),
                company_id=company.id if company else None,
                created_at=datetime.utcnow()
            )
            self.db.add(trial)
    
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
        
        # Fallback: extract from URL
        if "merck" in content.lower():
            return "Merck & Co."
        elif "bristol" in content.lower() or "myers" in content.lower():
            return "Bristol Myers Squibb"
        elif "roche" in content.lower():
            return "Roche"
        elif "pfizer" in content.lower():
            return "Pfizer"
        
        return None
    
    def _extract_company_description(self, content: str) -> str:
        """Extract company description from content."""
        # Look for description patterns
        sentences = content.split('.')
        for sentence in sentences[:5]:  # Check first 5 sentences
            if len(sentence) > 50 and any(word in sentence.lower() for word in 
                ["pharmaceutical", "biotechnology", "company", "develops", "research", "therapeutic"]):
                return sentence.strip()[:500]  # Limit length
        return ""
    
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
    
    def _parse_clinical_trial_document(self, doc: Document) -> Optional[Dict[str, Any]]:
        """Parse clinical trial information from documents."""
        content = doc.content
        
        # Extract title
        title = doc.title
        if not title or len(title) < 10:
            title = self._extract_trial_title_from_content(content)
        
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
            # Update existing drug
            existing_drug.brand_name = drug_info.get("brand_name") or existing_drug.brand_name
            existing_drug.drug_class = drug_info.get("drug_class") or existing_drug.drug_class
            existing_drug.mechanism_of_action = drug_info.get("mechanism_of_action") or existing_drug.mechanism_of_action
            existing_drug.fda_approval_status = drug_info.get("fda_approval_status", existing_drug.fda_approval_status)
            existing_drug.fda_approval_date = drug_info.get("fda_approval_date") or existing_drug.fda_approval_date
            existing_drug.nct_codes = drug_info.get("nct_codes", [])
            existing_drug.company_id = company_id
        else:
            # Create new drug
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
        """Extract NCT ID from content."""
        pattern = r"NCT\d{8}"
        match = re.search(pattern, content)
        return match.group(0) if match else None
    
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
    
    def _extract_trial_title_from_content(self, content: str) -> str:
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
        """Find or create company for a drug."""
        # Try to extract company name from document
        company_name = self._extract_company_name(doc.title, doc.content)
        if not company_name:
            # Default companies based on drug names
            drug_name = drug_info["generic_name"].lower()
            if "keytruda" in drug_name or "pembrolizumab" in drug_name:
                company_name = "Merck & Co."
            elif "opdivo" in drug_name or "nivolumab" in drug_name:
                company_name = "Bristol Myers Squibb"
            else:
                return None
        
        # Find existing company
        company = self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
        
        if not company:
            # Create new company
            company = Company(
                name=company_name,
                website_url=doc.source_url,
                description="",
                created_at=datetime.utcnow()
            )
            self.db.add(company)
            self.db.flush()
        
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
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Filter out clinical trial IDs
        if re.match(r'^NCT\d+', name.upper()):
            return False
        
        # Filter out study names and codes
        if re.match(r'^(Lung|Breast|PanTumor|Prostate|GI|Ovarian|Esophageal)\d+$', name):
            return False
        
        # Filter out generic protein/antibody terms
        generic_terms = {
            'ig', 'igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga', 'parp1', 'parp2', 'parp3',
            'tyk2', 'cdh6', 'ror1', 'her3', 'trop2', 'pcsk9', 'ov65'
        }
        
        if name.lower() in generic_terms:
            return False
        
        # Check if it contains only letters, numbers, and common drug characters
        if not re.match(r'^[A-Za-z0-9\-\s\/\(\)]+$', name):
            return False
        
        # Filter out common false positives
        false_positives = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'must', 'shall', 'accept', 'except', 'decline', 'drug', 'conjugate',
            'small', 'molecule', 'therapeutic', 'protein', 'bispecific', 'antibody',
            'dose', 'combination', 'acquired', 'noted', 'except', 'as', 'was', 'is',
            'being', 'an', 'a', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'
        }
        
        if name.lower() in false_positives:
            return False
        
        # Filter out incomplete drug names (ending with common words)
        incomplete_endings = [' is', ' was', ' being', ' an', ' a', ' the', ' and', ' or']
        if any(name.endswith(ending) for ending in incomplete_endings):
            return False
        
        # Filter out descriptive phrases
        descriptive_phrases = ['drug conjugate', 'small molecule', 'therapeutic protein', 'bispecific antibody', 'peptide']
        if any(phrase in name.lower() for phrase in descriptive_phrases):
            return False
        
        # Positive indicators for drug names
        drug_indicators = [
            name.lower().endswith(('mab', 'nib', 'tinib', 'cept', 'zumab', 'ximab')),
            re.match(r'^mk-\d+', name.lower()),
            re.match(r'^rg\d+', name.lower()),
            len(name.split()) > 1 and any(word.endswith(('mab', 'nib', 'tinib', 'cept')) for word in name.split()),
        ]
        
        return any(drug_indicators)
    
    def _infer_drug_class(self, drug_name: str) -> str:
        """Infer drug class from drug name."""
        name_lower = drug_name.lower()
        
        if name_lower.endswith(('mab', 'zumab', 'ximab')):
            return "Monoclonal Antibody"
        elif name_lower.endswith(('nib', 'tinib')):
            return "Small Molecule"
        elif 'deruxtecan' in name_lower or 'vedotin' in name_lower:
            return "ADC"
        elif name_lower.startswith('mk-') or name_lower.startswith('rg'):
            return "Small Molecule"
        else:
            return "Unknown"


def run_entity_extraction():
    """Run entity extraction on all documents."""
    db = get_db()
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


if __name__ == "__main__":
    run_entity_extraction()
