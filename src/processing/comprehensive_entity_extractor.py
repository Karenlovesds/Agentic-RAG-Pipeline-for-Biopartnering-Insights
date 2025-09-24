"""
Comprehensive entity extraction for populating the biopharma drugs database.
Focuses on extracting: Company name, Generic name, Brand name, FDA approval status,
Drug class, Targets, Mechanism of action, FDA-approved indications, Clinical trials.
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


class ComprehensiveEntityExtractor:
    """Comprehensive entity extraction focused on biopharma drugs data."""
    
    def __init__(self, db: Session):
        self.db = db
        
    def extract_all_entities(self) -> Dict[str, int]:
        """Extract all entities from documents and return counts."""
        logger.info("Starting comprehensive entity extraction...")
        
        # Get all documents
        documents = self.db.query(Document).all()
        logger.info(f"Processing {len(documents)} documents...")
        
        stats = {
            "companies_created": 0,
            "drugs_created": 0,
            "clinical_trials_created": 0,
            "targets_created": 0,
            "indications_created": 0,
            "relationships_created": 0
        }
        
        # Process company documents first
        company_docs = [d for d in documents if d.source_type.startswith("company_")]
        for doc in company_docs:
            try:
                self._extract_company_and_drugs(doc)
                stats["companies_created"] += 1
            except Exception as e:
                logger.error(f"Error processing company document {doc.id}: {e}")
        
        # Process FDA documents
        fda_docs = [d for d in documents if d.source_type.startswith("fda_")]
        for doc in fda_docs:
            try:
                self._extract_fda_drug_data(doc)
                stats["drugs_created"] += 1
            except Exception as e:
                logger.error(f"Error processing FDA document {doc.id}: {e}")
        
        # Process clinical trial documents
        trial_docs = [d for d in documents if d.source_type in ["clinical_trials", "clinical_trial"]]
        for doc in trial_docs:
            try:
                self._extract_clinical_trial_data(doc)
                stats["clinical_trials_created"] += 1
            except Exception as e:
                logger.error(f"Error processing trial document {doc.id}: {e}")
        
        # Create relationships
        self._create_all_relationships()
        stats["relationships_created"] = 1
        
        self.db.commit()
        logger.info(f"Comprehensive entity extraction completed: {stats}")
        return stats
    
    def _extract_company_and_drugs(self, doc: Document):
        """Extract company and drug information from company documents."""
        content = doc.content
        title = doc.title
        
        # Extract company name
        company_name = self._extract_company_name_from_doc(doc)
        if not company_name:
            return
        
        # Get or create company
        company = self._get_or_create_company(company_name, doc.source_url)
        
        # Extract drugs from pipeline documents
        if doc.source_type == "company_pipeline":
            drugs = self._extract_drugs_from_pipeline_content(content, company.id)
            for drug_data in drugs:
                self._create_or_update_drug(drug_data, company.id)
    
    def _extract_fda_drug_data(self, doc: Document):
        """Extract drug data from FDA documents."""
        content = doc.content
        title = doc.title
        
        # Extract drug information
        drug_data = self._parse_fda_document(content, title)
        if not drug_data:
            return
        
        # Find or create company
        company = self._find_company_for_drug(drug_data, doc)
        if not company:
            return
        
        # Create or update drug
        self._create_or_update_drug(drug_data, company.id)
    
    def _extract_clinical_trial_data(self, doc: Document):
        """Extract clinical trial data."""
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
        trial_data = self._parse_clinical_trial_document(content, doc.title)
        if not trial_data:
            return
        
        # Find associated company
        company = self._find_company_for_trial(trial_data, doc)
        
        # Create trial
        trial = ClinicalTrial(
            nct_id=nct_id,
            title=trial_data.get("title", ""),
            status=trial_data.get("status", ""),
            phase=trial_data.get("phase", ""),
            sponsor_id=company.id if company else None,
            created_at=datetime.utcnow()
        )
        self.db.add(trial)
    
    def _extract_company_name_from_doc(self, doc: Document) -> Optional[str]:
        """Extract company name from document."""
        title = doc.title.lower()
        content = doc.content.lower()
        
        # Known company mappings
        if "merck" in title or "merck" in content:
            return "Merck & Co."
        elif "bristol" in title or "bristol" in content or "myers" in title or "myers" in content:
            return "Bristol Myers Squibb"
        elif "roche" in title or "roche" in content:
            return "Roche"
        elif "pfizer" in title or "pfizer" in content:
            return "Pfizer"
        elif "novartis" in title or "novartis" in content:
            return "Novartis"
        elif "gilead" in title or "gilead" in content:
            return "Gilead Sciences"
        elif "regeneron" in title or "regeneron" in content:
            return "Regeneron"
        elif "incyte" in title or "incyte" in content:
            return "Incyte"
        
        # Try to extract from title patterns
        patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Corporation|Company|Co|Ltd|Limited|Pharmaceuticals|Pharma|Biotech|Biotechnology)",
            r"(?:About|Company|Overview)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        
        text = f"{doc.title} {doc.content}"
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and name.lower() not in ["the", "and", "or", "for", "with", "by"]:
                    return name
        
        return None
    
    def _get_or_create_company(self, name: str, website_url: str) -> Company:
        """Get existing company or create new one."""
        company = self.db.query(Company).filter(
            Company.name.ilike(f"%{name}%")
        ).first()
        
        if not company:
            company = Company(
                name=name,
                website=website_url,
                description="",
                created_at=datetime.utcnow()
            )
            self.db.add(company)
            self.db.flush()
        
        return company
    
    def _extract_drugs_from_pipeline_content(self, content: str, company_id: int) -> List[Dict[str, Any]]:
        """Extract drug information from company pipeline content."""
        drugs = []
        
        # Known drug patterns from Merck and BMS pipelines
        drug_patterns = [
            # Monoclonal antibodies
            r"(pembrolizumab|nivolumab|sotatercept|patritumab|sacituzumab|zilovertamab|nemtabrutinib|quavonlimab|clesrovimab|ifinatamab|bezlotoxumab)",
            # Drug conjugates
            r"([a-z]+deruxtecan|[a-z]+vedotin|[a-z]+tirumotecan)",
            # Small molecules
            r"(MK-\d+|RG\d+)",
            # Generic patterns
            r"([A-Z][a-z]+(?:mab|nib|tinib|cept|zumab|ximab))",
        ]
        
        found_drugs = set()
        for pattern in drug_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if self._validate_drug_name(match):
                    found_drugs.add(match)
        
        # Convert to drug data
        for drug_name in found_drugs:
            drug_data = {
                "generic_name": drug_name,
                "brand_name": self._get_brand_name_for_drug(drug_name),
                "drug_class": self._infer_drug_class(drug_name),
                "mechanism_of_action": self._extract_mechanism_for_drug(drug_name, content),
                "fda_approval_status": self._is_fda_approved_drug(drug_name),
                "fda_approval_date": self._get_approval_date_for_drug(drug_name),
                "targets": self._extract_targets_for_drug(drug_name, content),
                "indications": self._extract_indications_for_drug(drug_name, content),
                "nct_codes": self._extract_nct_codes_for_drug(drug_name, content)
            }
            drugs.append(drug_data)
        
        return drugs
    
    def _parse_fda_document(self, content: str, title: str) -> Optional[Dict[str, Any]]:
        """Parse FDA document for drug information."""
        # Extract drug name from title
        drug_name = self._extract_drug_name_from_title(title)
        if not drug_name:
            return None
        
        # Extract FDA approval information
        fda_approved = "approval" in content.lower() or "approved" in content.lower()
        approval_date = self._extract_approval_date(content)
        
        # Extract drug class
        drug_class = self._extract_drug_class_from_content(content)
        
        # Extract mechanism
        mechanism = self._extract_mechanism_from_content(drug_name, content)
        
        # Extract targets
        targets = self._extract_targets_from_content(content)
        
        # Extract indications
        indications = self._extract_indications_from_content(content)
        
        return {
            "generic_name": drug_name,
            "brand_name": self._extract_brand_name_from_content(content),
            "drug_class": drug_class,
            "mechanism_of_action": mechanism,
            "fda_approval_status": fda_approved,
            "fda_approval_date": approval_date,
            "targets": targets,
            "indications": indications,
            "nct_codes": []
        }
    
    def _parse_clinical_trial_document(self, content: str, title: str) -> Optional[Dict[str, Any]]:
        """Parse clinical trial document."""
        return {
            "title": title or "Clinical Trial",
            "status": self._extract_trial_status(content),
            "phase": self._extract_trial_phase(content),
            "interventions": self._extract_trial_interventions(content),
            "conditions": self._extract_trial_conditions(content)
        }
    
    def _create_or_update_drug(self, drug_data: Dict[str, Any], company_id: int):
        """Create or update drug entity."""
        # Check if drug already exists
        existing_drug = self.db.query(Drug).filter(
            Drug.generic_name.ilike(f"%{drug_data['generic_name']}%")
        ).first()
        
        if existing_drug:
            # Update existing drug
            existing_drug.brand_name = drug_data.get("brand_name") or existing_drug.brand_name
            existing_drug.drug_class = drug_data.get("drug_class") or existing_drug.drug_class
            existing_drug.mechanism_of_action = drug_data.get("mechanism_of_action") or existing_drug.mechanism_of_action
            existing_drug.fda_approval_status = drug_data.get("fda_approval_status", existing_drug.fda_approval_status)
            existing_drug.fda_approval_date = drug_data.get("fda_approval_date") or existing_drug.fda_approval_date
            existing_drug.nct_codes = drug_data.get("nct_codes", [])
            existing_drug.company_id = company_id
        else:
            # Create new drug
            drug = Drug(
                generic_name=drug_data["generic_name"],
                brand_name=drug_data.get("brand_name"),
                drug_class=drug_data.get("drug_class"),
                mechanism_of_action=drug_data.get("mechanism_of_action"),
                fda_approval_status=drug_data.get("fda_approval_status", False),
                fda_approval_date=drug_data.get("fda_approval_date"),
                company_id=company_id,
                nct_codes=drug_data.get("nct_codes", []),
                created_at=datetime.utcnow()
            )
            self.db.add(drug)
            self.db.flush()
            
            # Create targets and indications
            self._create_drug_targets(drug.id, drug_data.get("targets", []))
            self._create_drug_indications(drug.id, drug_data.get("indications", []))
    
    def _create_drug_targets(self, drug_id: int, targets: List[str]):
        """Create drug-target relationships."""
        for target_name in targets:
            if not target_name:
                continue
                
            # Get or create target
            target = self.db.query(Target).filter(
                Target.name.ilike(f"%{target_name}%")
            ).first()
            
            if not target:
                target = Target(
                    name=target_name,
                    target_type="protein",
                    created_at=datetime.utcnow()
                )
                self.db.add(target)
                self.db.flush()
            
            # Create relationship
            existing_rel = self.db.query(DrugTarget).filter(
                DrugTarget.drug_id == drug_id,
                DrugTarget.target_id == target.id
            ).first()
            
            if not existing_rel:
                rel = DrugTarget(
                    drug_id=drug_id,
                    target_id=target.id,
                    relationship_type="inhibits"
                )
                self.db.add(rel)
    
    def _create_drug_indications(self, drug_id: int, indications: List[str]):
        """Create drug-indication relationships."""
        for indication_name in indications:
            if not indication_name:
                continue
                
            # Get or create indication
            indication = self.db.query(Indication).filter(
                Indication.name.ilike(f"%{indication_name}%")
            ).first()
            
            if not indication:
                indication = Indication(
                    name=indication_name,
                    indication_type="cancer",
                    created_at=datetime.utcnow()
                )
                self.db.add(indication)
                self.db.flush()
            
            # Create relationship
            existing_rel = self.db.query(DrugIndication).filter(
                DrugIndication.drug_id == drug_id,
                DrugIndication.indication_id == indication.id
            ).first()
            
            if not existing_rel:
                rel = DrugIndication(
                    drug_id=drug_id,
                    indication_id=indication.id,
                    approval_status=True
                )
                self.db.add(rel)
    
    def _create_all_relationships(self):
        """Create all relationships between entities."""
        # Link drugs to clinical trials via NCT codes
        drugs = self.db.query(Drug).all()
        trials = self.db.query(ClinicalTrial).all()
        
        for drug in drugs:
            if drug.nct_codes:
                for nct_code in drug.nct_codes:
                    trial = next((t for t in trials if t.nct_id == nct_code), None)
                    if trial and not any(ct.drug_id == drug.id for ct in drug.clinical_trials):
                        drug.clinical_trials.append(trial)
    
    # Helper methods
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
        
        # Filter out generic protein/antibody terms (but be more specific)
        generic_terms = {
            'ig', 'igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga', 'parp1', 'parp2', 'parp3',
            'tyk2', 'cdh6', 'ror1', 'her3', 'trop2', 'pcsk9', 'ov65'
        }
        
        if name.lower() in generic_terms:
            return False
        
        # Filter out common false positives (but be more specific)
        false_positives = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'must', 'shall', 'accept', 'except', 'decline'
        }
        
        if name.lower() in false_positives:
            return False
        
        # Filter out incomplete drug names (ending with common words)
        incomplete_endings = [' is', ' was', ' being', ' an', ' a', ' the', ' and', ' or']
        if any(name.endswith(ending) for ending in incomplete_endings):
            return False
        
        # Filter out descriptive phrases (but be more specific)
        descriptive_phrases = ['drug conjugate', 'small molecule', 'therapeutic protein', 'bispecific antibody', 'peptide']
        if any(phrase in name.lower() for phrase in descriptive_phrases):
            return False
        
        # More inclusive positive indicators for drug names
        drug_indicators = [
            # Monoclonal antibodies
            name.lower().endswith(('mab', 'zumab', 'ximab')),
            # Kinase inhibitors
            name.lower().endswith(('nib', 'tinib')),
            # Fusion proteins
            name.lower().endswith('cept'),
            # CAR-T therapies
            name.lower().endswith('leucel'),
            # ADCs (Antibody Drug Conjugates) - allow space-separated names
            'deruxtecan' in name.lower(),
            'vedotin' in name.lower(),
            'tirumotecan' in name.lower(),
            # Specific known drugs (expanded list)
            name.lower() in {
                'pembrolizumab', 'nivolumab', 'sotatercept', 'patritumab', 'sacituzumab',
                'zilovertamab', 'nemtabrutinib', 'quavonlimab', 'clesrovimab', 'ifinatamab',
                'bezlotoxumab', 'ipilimumab', 'relatlimab', 'enasicon', 'dasatinib',
                'repotrectinib', 'elotuzumab', 'belatacept', 'fedratinib', 'luspatercept',
                'abatacept', 'deucravacitinib', 'trastuzumab', 'atezolizumab', 'avelumab',
                'blinatumomab', 'dupilumab', 'ruxolitinib', 'tisagenlecleucel', 'yescarta',
                'kymriah', 'carvykti', 'abecma', 'breyanzi'
            },
            # Merck drug codes
            re.match(r'^mk-\d+', name.lower()),
            # Roche drug codes
            re.match(r'^rg\d+', name.lower()),
            # Allow drug names with spaces (like "Patritumab Deruxtecan")
            len(name.split()) >= 2 and any(word.endswith(('mab', 'nib', 'tinib', 'cept', 'leucel')) for word in name.split()),
        ]
        
        return any(drug_indicators)
    
    def _get_brand_name_for_drug(self, generic_name: str) -> Optional[str]:
        """Get brand name for known drugs."""
        brand_mapping = {
            "pembrolizumab": "KEYTRUDA",
            "nivolumab": "OPDIVO",
            "sotatercept": "SOTATERCEPT",
            "patritumab": "PATRITUMAB",
            "sacituzumab": "SACITUZUMAB",
            "zilovertamab": "ZILOVERTAMAB",
            "nemtabrutinib": "NEMTABRUTINIB",
            "quavonlimab": "QUAVONLIMAB",
            "clesrovimab": "CLESROVIMAB",
            "ifinatamab": "IFINATAMAB",
            "bezlotoxumab": "BEZLOTOXUMAB",
        }
        return brand_mapping.get(generic_name.lower())
    
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
    
    def _is_fda_approved_drug(self, drug_name: str) -> bool:
        """Check if drug is FDA approved."""
        fda_approved_drugs = {
            "pembrolizumab", "nivolumab", "sotatercept", "patritumab", 
            "sacituzumab", "zilovertamab", "nemtabrutinib", "quavonlimab",
            "clesrovimab", "ifinatamab", "bezlotoxumab"
        }
        return drug_name.lower() in fda_approved_drugs
    
    def _get_approval_date_for_drug(self, drug_name: str) -> Optional[datetime]:
        """Get approval date for known drugs."""
        approval_dates = {
            "pembrolizumab": datetime(2014, 9, 1),
            "nivolumab": datetime(2014, 12, 1),
            "sotatercept": datetime(2023, 3, 1),
        }
        return approval_dates.get(drug_name.lower())
    
    def _extract_mechanism_for_drug(self, drug_name: str, content: str) -> Optional[str]:
        """Extract mechanism of action for a specific drug."""
        # Known mechanisms
        mechanisms = {
            "pembrolizumab": "Monoclonal antibody that binds to the PD-1 receptor and blocks its interaction with PD-L1 and PD-L2",
            "nivolumab": "Monoclonal antibody that binds to the PD-1 receptor and blocks its interaction with PD-L1 and PD-L2",
            "sotatercept": "Activin signaling inhibitor",
            "patritumab": "Anti-HER3 antibody-drug conjugate",
            "sacituzumab": "Anti-TROP2 antibody-drug conjugate",
            "zilovertamab": "Anti-ROR1 antibody-drug conjugate",
            "nemtabrutinib": "Bruton's tyrosine kinase (BTK) inhibitor",
            "quavonlimab": "Anti-CTLA-4 monoclonal antibody",
            "clesrovimab": "Anti-IL-4Rα monoclonal antibody",
            "ifinatamab": "Anti-B7-H3 antibody-drug conjugate",
            "bezlotoxumab": "Anti-C. difficile toxin B monoclonal antibody",
        }
        return mechanisms.get(drug_name.lower())
    
    def _extract_targets_for_drug(self, drug_name: str, content: str) -> List[str]:
        """Extract targets for a specific drug."""
        target_mapping = {
            "pembrolizumab": ["PD-1"],
            "nivolumab": ["PD-1"],
            "sotatercept": ["Activin"],
            "patritumab": ["HER3"],
            "sacituzumab": ["TROP2"],
            "zilovertamab": ["ROR1"],
            "nemtabrutinib": ["BTK"],
            "quavonlimab": ["CTLA-4"],
            "clesrovimab": ["IL-4Rα"],
            "ifinatamab": ["B7-H3"],
            "bezlotoxumab": ["C. difficile toxin B"],
        }
        return target_mapping.get(drug_name.lower(), [])
    
    def _extract_indications_for_drug(self, drug_name: str, content: str) -> List[str]:
        """Extract indications for a specific drug."""
        indication_mapping = {
            "pembrolizumab": ["Melanoma", "Non-small cell lung cancer", "Head and neck cancer", "Hodgkin lymphoma"],
            "nivolumab": ["Melanoma", "Non-small cell lung cancer", "Renal cell carcinoma", "Hodgkin lymphoma"],
            "sotatercept": ["Pulmonary arterial hypertension"],
            "patritumab": ["Breast cancer", "Non-small cell lung cancer"],
            "sacituzumab": ["Triple-negative breast cancer", "Urothelial cancer"],
            "zilovertamab": ["Non-Hodgkin lymphoma"],
            "nemtabrutinib": ["Chronic lymphocytic leukemia", "Mantle cell lymphoma"],
            "quavonlimab": ["Melanoma", "Renal cell carcinoma"],
            "clesrovimab": ["Atopic dermatitis"],
            "ifinatamab": ["Esophageal cancer", "Prostate cancer", "Small cell lung cancer"],
            "bezlotoxumab": ["Clostridium difficile infection"],
        }
        return indication_mapping.get(drug_name.lower(), [])
    
    def _extract_nct_codes_for_drug(self, drug_name: str, content: str) -> List[str]:
        """Extract NCT codes associated with a drug."""
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
    
    # Additional helper methods for FDA and trial parsing
    def _extract_drug_name_from_title(self, title: str) -> Optional[str]:
        """Extract drug name from document title."""
        if not title or len(title) > 200:
            return None
        return title.strip()
    
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
                    return datetime(year, 1, 1)
                except ValueError:
                    continue
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
        """Extract mechanism of action from content."""
        # Look for mechanism patterns near the drug name
        drug_pos = content.lower().find(drug_name.lower())
        if drug_pos == -1:
            return None
        
        start = max(0, drug_pos - 200)
        end = min(len(content), drug_pos + 200)
        context = content[start:end]
        
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
    
    def _extract_brand_name_from_content(self, content: str) -> Optional[str]:
        """Extract brand name from content."""
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
    
    def _extract_targets_from_content(self, content: str) -> List[str]:
        """Extract targets from content."""
        targets = []
        target_patterns = [
            r"targets?\s+([A-Z][a-z0-9-]+)",
            r"inhibits?\s+([A-Z][a-z0-9-]+)",
            r"blocks?\s+([A-Z][a-z0-9-]+)",
        ]
        
        for pattern in target_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            targets.extend(matches)
        
        return list(set(targets))[:5]  # Limit to 5 targets
    
    def _extract_indications_from_content(self, content: str) -> List[str]:
        """Extract indications from content."""
        indications = []
        indication_patterns = [
            r"indication[:\s]+([^.\n]{5,100})",
            r"treats?\s+([^.\n]{5,100})",
            r"for\s+([^.\n]{5,100})",
        ]
        
        for pattern in indication_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            indications.extend(matches)
        
        return list(set(indications))[:5]  # Limit to 5 indications
    
    def _extract_nct_id(self, content: str) -> Optional[str]:
        """Extract NCT ID from content."""
        pattern = r"NCT\d{8}"
        match = re.search(pattern, content)
        return match.group(0) if match else None
    
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
        patterns = [
            r"intervention[:\s]+([^\n]{5,100})",
            r"drug[:\s]+([^\n]{5,100})",
            r"treatment[:\s]+([^\n]{5,100})",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            interventions.extend(matches)
        
        return interventions[:5]
    
    def _extract_trial_conditions(self, content: str) -> List[str]:
        """Extract trial conditions from content."""
        conditions = []
        patterns = [
            r"condition[:\s]+([^\n]{5,100})",
            r"disease[:\s]+([^\n]{5,100})",
            r"cancer[:\s]+([^\n]{5,100})",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            conditions.extend(matches)
        
        return conditions[:5]
    
    def _find_company_for_drug(self, drug_data: Dict[str, Any], doc: Document) -> Optional[Company]:
        """Find company for a drug."""
        # Try to extract company name from document
        company_name = self._extract_company_name_from_doc(doc)
        if not company_name:
            # Default companies based on drug names
            drug_name = drug_data["generic_name"].lower()
            if "keytruda" in drug_name or "pembrolizumab" in drug_name:
                company_name = "Merck & Co."
            elif "opdivo" in drug_name or "nivolumab" in drug_name:
                company_name = "Bristol Myers Squibb"
            else:
                return None
        
        return self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()
    
    def _find_company_for_trial(self, trial_data: Dict[str, Any], doc: Document) -> Optional[Company]:
        """Find company for a clinical trial."""
        company_name = self._extract_company_name_from_doc(doc)
        if not company_name:
            return None
        
        return self.db.query(Company).filter(
            Company.name.ilike(f"%{company_name}%")
        ).first()


def run_comprehensive_entity_extraction():
    """Run comprehensive entity extraction on all documents."""
    db = get_db()
    try:
        extractor = ComprehensiveEntityExtractor(db)
        stats = extractor.extract_all_entities()
        
        print("Comprehensive Entity Extraction Results:")
        print("=" * 50)
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    run_comprehensive_entity_extraction()

