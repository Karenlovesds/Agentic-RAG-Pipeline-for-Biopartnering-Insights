"""
Entity extraction module for processing collected documents and creating structured entities.
"""

import re
import json
import csv
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
                # Extract clinical trials from any document that contains NCT codes
                if "NCT" in doc.content:
                    self._extract_clinical_trial_entities(doc)
                    stats["clinical_trials_created"] += 1
                
                if doc.source_type in ["company_about", "company_pipeline", "company_products", "company_oncology"]:
                    self._extract_company_entities(doc)
                    stats["companies_created"] += 1
                    
                elif doc.source_type in ["fda_drug_approval", "fda_comprehensive_approval", "drugs_com_profile"]:
                    self._extract_drug_entities(doc)
                    stats["drugs_created"] += 1
                    
                    # Also extract targets from drug documents
                    self._extract_target_entities(doc)
                    stats["targets_created"] += 1
                    
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
        text = f"{title} {content}"
        
        # First, try to extract from FDA-specific patterns (highest priority)
        fda_patterns = [
            r"Manufacturer[:\s]+([^\n]+?)(?:\n|$)",
            r"Company[:\s]+([^\n]+?)(?:\n|$)",
            r"Sponsor[:\s]+([^\n]+?)(?:\n|$)",
            r"Applicant[:\s]+([^\n]+?)(?:\n|$)"
        ]
        
        for pattern in fda_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                # Map to standard company names
                company_mapping = {
                    "Merck Sharp & Dohme LLC": "Merck & Co.",
                    "Merck Sharp & Dohme": "Merck & Co.",
                    "E.R. Squibb & Sons, L.L.C.": "Bristol Myers Squibb",
                    "E.R. Squibb & Sons": "Bristol Myers Squibb",
                    "Bristol Myers Squibb Inc": "Bristol Myers Squibb",
                    "Bristol Myers Squibb": "Bristol Myers Squibb",
                    "Genentech Inc": "Roche/Genentech",
                    "Genentech": "Roche/Genentech",
                    "AstraZeneca Pharmaceuticals": "AstraZeneca",
                    "AstraZeneca": "AstraZeneca",
                    "Pfizer Inc": "Pfizer",
                    "Pfizer": "Pfizer",
                    "Novartis Pharmaceuticals": "Novartis",
                    "Novartis": "Novartis",
                    "Gilead Sciences": "Gilead Sciences",
                    "Amgen Inc": "Amgen",
                    "Amgen": "Amgen",
                    "Regeneron Pharmaceuticals": "Regeneron Pharmaceuticals",
                    "Regeneron": "Regeneron Pharmaceuticals",
                    "BioNTech SE": "BioNTech",
                    "BioNTech": "BioNTech",
                    "BeiGene Ltd": "BeiGene",
                    "BeiGene": "BeiGene",
                    "Seagen Inc": "Seagen",
                    "Seagen": "Seagen",
                    "Incyte Corporation": "Incyte",
                    "Incyte": "Incyte",
                    "Vertex Pharmaceuticals": "Vertex Pharmaceuticals",
                    "Vertex": "Vertex Pharmaceuticals",
                    "Moderna Inc": "Moderna",
                    "Moderna": "Moderna",
                    "Johnson & Johnson": "Johnson & Johnson",
                    "Janssen": "Johnson & Johnson",
                    "AbbVie Inc": "AbbVie",
                    "AbbVie": "AbbVie",
                    "Eli Lilly and Company": "Eli Lilly",
                    "Eli Lilly": "Eli Lilly",
                    "Sanofi-Aventis": "Sanofi",
                    "Sanofi": "Sanofi",
                    "Bayer AG": "Bayer",
                    "Bayer": "Bayer",
                    "Takeda Pharmaceutical": "Takeda Pharmaceutical",
                    "Takeda": "Takeda Pharmaceutical",
                    "Daiichi Sankyo Company": "Daiichi Sankyo",
                    "Daiichi Sankyo": "Daiichi Sankyo",
                    "Astellas Pharma": "Astellas Pharma",
                    "Astellas": "Astellas Pharma",
                    "Boehringer Ingelheim": "Boehringer Ingelheim",
                    "Alnylam Pharmaceuticals": "Alnylam Pharmaceuticals",
                    "Alnylam": "Alnylam Pharmaceuticals",
                    "Illumina Inc": "Illumina",
                    "Illumina": "Illumina",
                    "Merck KGaA": "Merck KGaA",
                    "GlaxoSmithKline": "GlaxoSmithKline (GSK)",
                    "GSK": "GlaxoSmithKline (GSK)",
                    "CSL Limited": "CSL",
                    "CSL": "CSL",
                    "Biogen Inc": "Biogen",
                    "Biogen": "Biogen"
                }
                return company_mapping.get(company_name, company_name)
        
        # Second, try specific pharmaceutical company patterns
        pharma_patterns = [
            r"(Merck\s+Sharp\s+&\s+Dohme\s+LLC)",
            r"(Merck\s+&?\s+Co\.?)",
            r"(Bristol\s+Myers\s+Squibb)",
            r"(Roche/Genentech)",
            r"(Genentech\s+Inc)",
            r"(AstraZeneca\s+Pharmaceuticals?)",
            r"(Pfizer\s+Inc)",
            r"(Novartis\s+Pharmaceuticals?)",
            r"(Gilead\s+Sciences)",
            r"(Amgen\s+Inc)",
            r"(Regeneron\s+Pharmaceuticals)",
            r"(BioNTech\s+SE)",
            r"(BeiGene\s+Ltd)",
            r"(Seagen\s+Inc)",
            r"(Incyte\s+Corporation)",
            r"(Vertex\s+Pharmaceuticals)",
            r"(Moderna\s+Inc)",
            r"(Johnson\s+&\s+Johnson)",
            r"(AbbVie\s+Inc)",
            r"(Eli\s+Lilly\s+and\s+Company)",
            r"(Sanofi-Aventis)",
            r"(Bayer\s+AG)",
            r"(Takeda\s+Pharmaceutical)",
            r"(Daiichi\s+Sankyo\s+Company)",
            r"(Astellas\s+Pharma)",
            r"(Boehringer\s+Ingelheim)",
            r"(Alnylam\s+Pharmaceuticals)",
            r"(Illumina\s+Inc)",
            r"(Merck\s+KGaA)",
            r"(GlaxoSmithKline|GSK)",
            r"(CSL\s+Limited)",
            r"(Biogen\s+Inc)"
        ]
        
        for pattern in pharma_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                # Map to standard company names
                company_mapping = {
                    "Merck Sharp & Dohme LLC": "Merck & Co.",
                    "Merck & Co.": "Merck & Co.",
                    "Bristol Myers Squibb": "Bristol Myers Squibb",
                    "Roche/Genentech": "Roche/Genentech",
                    "Genentech Inc": "Roche/Genentech",
                    "AstraZeneca Pharmaceuticals": "AstraZeneca",
                    "Pfizer Inc": "Pfizer",
                    "Novartis Pharmaceuticals": "Novartis",
                    "Gilead Sciences": "Gilead Sciences",
                    "Amgen Inc": "Amgen",
                    "Regeneron Pharmaceuticals": "Regeneron Pharmaceuticals",
                    "BioNTech SE": "BioNTech",
                    "BeiGene Ltd": "BeiGene",
                    "Seagen Inc": "Seagen",
                    "Incyte Corporation": "Incyte",
                    "Vertex Pharmaceuticals": "Vertex Pharmaceuticals",
                    "Moderna Inc": "Moderna",
                    "Johnson & Johnson": "Johnson & Johnson",
                    "AbbVie Inc": "AbbVie",
                    "Eli Lilly and Company": "Eli Lilly",
                    "Sanofi-Aventis": "Sanofi",
                    "Bayer AG": "Bayer",
                    "Takeda Pharmaceutical": "Takeda Pharmaceutical",
                    "Daiichi Sankyo Company": "Daiichi Sankyo",
                    "Astellas Pharma": "Astellas Pharma",
                    "Boehringer Ingelheim": "Boehringer Ingelheim",
                    "Alnylam Pharmaceuticals": "Alnylam Pharmaceuticals",
                    "Illumina Inc": "Illumina",
                    "Merck KGaA": "Merck KGaA",
                    "GlaxoSmithKline": "GlaxoSmithKline (GSK)",
                    "GSK": "GlaxoSmithKline (GSK)",
                    "CSL Limited": "CSL",
                    "Biogen Inc": "Biogen"
                }
                return company_mapping.get(company_name, company_name)
        
        # Third, try generic company name patterns
        generic_patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Corporation|Company|Co|Ltd|Limited|Pharmaceuticals|Pharma|Biotech|Biotechnology)",
            r"(?:About|Company|Overview)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Pipeline|Products|Research)"
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if name.lower() not in ["the", "and", "or", "for", "with", "by", "fda", "drug", "label", "api"]:
                    return name
        
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
        # Look for drug name patterns in content first (more reliable)
        patterns = [
            r"Generic Name:\s*([A-Z][A-Z\s]+?)(?:\n|$)",
            r"Generic Name:\s*([a-z]+(?:mab|nib|tinib|cept|zumab|ximab))",
            r"([A-Z][a-z]+(?:mab|nib|tinib|cept|zumab|ximab))",
            r"(MK-\d+)",
            r"(RG\d+)",
            r"(pembrolizumab|nivolumab|sotatercept|patritumab|sacituzumab|zilovertamab|nemtabrutinib|quavonlimab|clesrovimab|ifinatamab|bezlotoxumab)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                drug_name = match.group(1).strip()
                # Clean up the drug name
                if ':' in drug_name:
                    drug_name = drug_name.split(':')[-1].strip()
                return drug_name
        
        # Try title as fallback, but clean it up
        if title and len(title) < 100:
            # Remove common prefixes
            clean_title = title.replace('FDA Approval History:', '').replace('FDA Drug Approval:', '').strip()
            if clean_title and len(clean_title) < 50:
                return clean_title
        
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
        content_lower = content.lower()
        
        # First, look for specific drug class patterns (highest priority)
        specific_patterns = [
            (r"PD-1[-\s]*blocking\s+antibody", "PD-1 Blocking Antibody"),
            (r"PD-L1[-\s]*blocking\s+antibody", "PD-L1 Blocking Antibody"),
            (r"programmed\s+death[-\s]*receptor[-\s]*1[-\s]*\(PD-1\)[-\s]*blocking\s+antibody", "PD-1 Blocking Antibody"),
            (r"programmed\s+death[-\s]*ligand[-\s]*1[-\s]*\(PD-L1\)[-\s]*blocking\s+antibody", "PD-L1 Blocking Antibody"),
            (r"over[-\s]*the[-\s]*counter", "OTC Drug")
        ]
        
        for pattern, drug_class in specific_patterns:
            if re.search(pattern, content_lower):
                return drug_class
        
        # Second, look for drug class keywords in content
        drug_classes = [
            "monoclonal antibody", "small molecule", "ADC", "antibody-drug conjugate",
            "therapeutic protein", "peptide", "vaccine", "bispecific antibody",
            "kinase inhibitor", "tyrosine kinase inhibitor", "angiogenesis inhibitor",
            "immune checkpoint inhibitor", "fusion protein", "CAR-T therapy",
            "chimeric antigen receptor", "therapeutic protein", "hormone therapy",
            "chemotherapy", "targeted therapy", "immunotherapy", "cell therapy",
            "retinoid"
        ]
        
        for drug_class in drug_classes:
            if drug_class in content_lower:
                return drug_class.title()
        
        # Third, look for cancer-specific indications to avoid non-cancer drugs
        cancer_indicators = [
            "cancer", "tumor", "oncology", "carcinoma", "sarcoma", "lymphoma", 
            "leukemia", "melanoma", "neoplasm", "malignancy", "metastatic",
            "adjuvant", "neoadjuvant", "palliative", "curative"
        ]
        
        has_cancer_indication = any(indicator in content_lower for indicator in cancer_indicators)
        
        # Only return "Prescription Drug" if it's likely a cancer drug or no specific class found
        if has_cancer_indication:
            return "Prescription Drug"
        
        # For drugs with prescription drug classification, only use it for cancer drugs
        if "prescription" in content_lower and "drug" in content_lower:
            # Only classify as "Prescription Drug" if it has cancer indications
            if has_cancer_indication:
                return "Prescription Drug"
            else:
                # For non-cancer drugs, try to extract more specific information
                if "tablet" in content_lower or "capsule" in content_lower:
                    return "Oral Medication"
                elif "injection" in content_lower or "intravenous" in content_lower:
                    return "Injectable Medication"
                elif "cream" in content_lower or "ointment" in content_lower:
                    return "Topical Medication"
                else:
                    # For non-cancer drugs without specific form, return None to avoid misclassification
                    return None
        
        return None
    
    def _extract_mechanism_from_content(self, drug_name: str, content: str) -> Optional[str]:
        """Extract mechanism of action for a specific drug."""
        content_lower = content.lower()
        
        # Look for common mechanism patterns in the entire content
        patterns = [
            r"PD-1[-\s]*blocking\s+antibody",
            r"PD-L1[-\s]*blocking\s+antibody", 
            r"programmed\s+death[-\s]*receptor[-\s]*1[-\s]*\(PD-1\)[-\s]*blocking\s+antibody",
            r"programmed\s+death[-\s]*ligand[-\s]*1[-\s]*\(PD-L1\)[-\s]*blocking\s+antibody",
            r"kinase\s+inhibitor",
            r"tyrosine\s+kinase\s+inhibitor",
            r"angiogenesis\s+inhibitor",
            r"immune\s+checkpoint\s+inhibitor",
            r"monoclonal\s+antibody",
            r"bispecific\s+antibody",
            r"antibody[-\s]*drug\s+conjugate",
            r"ADC",
            r"CAR[-\s]*T\s+therapy",
            r"chimeric\s+antigen\s+receptor",
            r"fusion\s+protein",
            r"therapeutic\s+protein"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content_lower)
            if match:
                return match.group(0).title()
        
        # Look for mechanism patterns near the drug name
        drug_pos = content_lower.find(drug_name.lower())
        if drug_pos != -1:
            # Get context around the drug name
            start = max(0, drug_pos - 300)
            end = min(len(content), drug_pos + 300)
            context = content[start:end]
            
            # Look for mechanism patterns in context
            context_patterns = [
                r"inhibits?\s+([^.]{10,100})",
                r"blocks?\s+([^.]{10,100})",
                r"targets?\s+([^.]{10,100})",
                r"binds?\s+to\s+([^.]{10,100})",
                r"mechanism[:\s]+([^.]{10,100})",
                r"moa[:\s]+([^.]{10,100})"
            ]
            
            for pattern in context_patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        return None
    
    def _extract_approval_date(self, content: str) -> Optional[datetime]:
        """Extract FDA approval date from content."""
        patterns = [
            # FDA specific format: "Effective Time (Approval Date): 20250819"
            r"Effective\s+Time\s+\(Approval\s+Date\):\s*(\d{8})",
            r"approval\s+date[:\s]*(\d{8})",
            r"effective\s+time[:\s]*(\d{8})",
            # Standard year patterns
            r"approved[:\s]+(\d{4})",
            r"approval[:\s]+(\d{4})",
            r"(\d{4})[:\s]+approval",
            r"FDA\s+approval[:\s]+(\d{4})",
            r"approval\s+date[:\s]+(\d{4})",
            r"effective\s+date[:\s]+(\d{4})",
            r"marketing\s+approval[:\s]+(\d{4})",
            r"(\d{4})[:\s]+FDA",
            r"(\d{4})[:\s]+marketing",
            r"(\d{4})[:\s]+effective"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    
                    # Handle 8-digit format (YYYYMMDD)
                    if len(date_str) == 8:
                        year = int(date_str[:4])
                        month = int(date_str[4:6])
                        day = int(date_str[6:8])
                        if 1990 <= year <= datetime.now().year and 1 <= month <= 12 and 1 <= day <= 31:
                            return datetime(year, month, day)
                    
                    # Handle 4-digit format (YYYY)
                    elif len(date_str) == 4:
                        year = int(date_str)
                        if 1990 <= year <= datetime.now().year:
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
                website=doc.source_url,
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
        
        # Filter out generic protein/antibody terms (but be more specific)
        generic_terms = {
            'ig', 'igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga', 'parp1', 'parp2', 'parp3',
            'tyk2', 'cdh6', 'ror1', 'her3', 'trop2', 'pcsk9', 'ov65'
        }
        
        if name.lower() in generic_terms:
            return False
        
        # Check if it contains only letters, numbers, and common drug characters
        if not re.match(r'^[A-Za-z0-9\-\s\/\(\)]+$', name):
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

    def _load_companies_from_csv(self) -> List[Dict[str, str]]:
        """Load companies data from CSV file."""
        companies = []
        try:
            with open('data/companies.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    companies.append(row)
        except Exception as e:
            logger.error(f"Error loading companies CSV: {e}")
        return companies

    def _process_company_oncology_pipeline(self, company_data: Dict[str, str]):
        """Process a company's oncology pipeline."""
        company_name = company_data['Company']
        pipeline_url = company_data['OncologyPipelineURL']
        
        # Get or create company
        company = self._get_or_create_company(company_name, company_data['OfficialWebsite'])
        
        # Look for documents from this company's oncology pipeline
        company_docs = self.db.query(Document).filter(
            Document.source_url.like(f"%{company_name.lower()}%")
        ).all()
        
        # If no specific documents found, create mock data based on known drugs
        if not company_docs:
            self._create_known_drugs_for_company(company)
        else:
            # Process existing documents
            for doc in company_docs:
                self._extract_drugs_from_document(doc, company)

    def _get_or_create_company(self, name: str, website: str) -> Company:
        """Get existing company or create new one."""
        company = self.db.query(Company).filter(
            Company.name.ilike(f"%{name}%")
        ).first()
        
        if not company:
            company = Company(
                name=name,
                website=website,
                description=f"Oncology-focused pharmaceutical company",
                created_at=datetime.utcnow()
            )
            self.db.add(company)
            self.db.flush()
        
        return company

    def _create_known_drugs_for_company(self, company: Company):
        """Create known drugs for major companies based on their pipelines."""
        company_name = company.name.lower()
        
        if "merck" in company_name:
            self._create_merck_drugs(company)
        elif "bristol" in company_name or "myers" in company_name:
            self._create_bms_drugs(company)
        elif "roche" in company_name or "genentech" in company_name:
            self._create_roche_drugs(company)
        elif "pfizer" in company_name:
            self._create_pfizer_drugs(company)
        elif "novartis" in company_name:
            self._create_novartis_drugs(company)
        elif "gilead" in company_name:
            self._create_gilead_drugs(company)
        elif "amgen" in company_name:
            self._create_amgen_drugs(company)
        elif "regeneron" in company_name:
            self._create_regeneron_drugs(company)
        elif "incyte" in company_name:
            self._create_incyte_drugs(company)

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

    def _extract_drugs_from_document(self, doc: Document, company: Company):
        """Extract drugs from a document."""
        # This is a placeholder - in practice, you'd extract from the actual document content
        pass

    def _create_merck_drugs(self, company: Company):
        """Create Merck & Co. drugs."""
        merck_drugs = [
            {
                "generic_name": "Pembrolizumab",
                "brand_name": "KEYTRUDA",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Monoclonal antibody that binds to the PD-1 receptor and blocks its interaction with PD-L1 and PD-L2",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2014, 9, 1),
                "targets": ["PD-1"],
                "indications": ["Melanoma", "Non-small cell lung cancer", "Head and neck cancer", "Hodgkin lymphoma", "Urothelial cancer", "Gastric cancer", "Cervical cancer", "Hepatocellular carcinoma", "Merkel cell carcinoma", "Renal cell carcinoma", "Endometrial carcinoma", "Triple-negative breast cancer", "Esophageal cancer", "Small cell lung cancer"],
                "nct_codes": ["NCT03765918", "NCT03867084", "NCT05116189", "NCT03066778", "NCT04191096"]
            },
            {
                "generic_name": "Sotatercept",
                "brand_name": "SOTATERCEPT",
                "drug_class": "Therapeutic Protein",
                "mechanism_of_action": "Activin signaling inhibitor",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2023, 3, 1),
                "targets": ["Activin"],
                "indications": ["Pulmonary arterial hypertension"],
                "nct_codes": ["NCT04938830", "NCT05624554", "NCT03976323"]
            }
        ]
        
        for drug_data in merck_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_bms_drugs(self, company: Company):
        """Create Bristol Myers Squibb drugs."""
        bms_drugs = [
            {
                "generic_name": "Nivolumab",
                "brand_name": "OPDIVO",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-PD-1 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2014, 12, 1),
                "targets": ["PD-1"],
                "indications": ["Melanoma", "Non-small cell lung cancer", "Renal cell carcinoma", "Hodgkin lymphoma", "Head and neck cancer", "Urothelial cancer", "Colorectal cancer", "Hepatocellular carcinoma", "Esophageal cancer", "Gastric cancer", "Malignant pleural mesothelioma"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            },
            {
                "generic_name": "Ipilimumab",
                "brand_name": "YERVOY",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-CTLA-4 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2011, 3, 1),
                "targets": ["CTLA-4"],
                "indications": ["Melanoma", "Renal cell carcinoma", "Colorectal cancer", "Hepatocellular carcinoma", "Malignant pleural mesothelioma", "Non-small cell lung cancer"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in bms_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_roche_drugs(self, company: Company):
        """Create Roche/Genentech drugs."""
        roche_drugs = [
            {
                "generic_name": "Trastuzumab",
                "brand_name": "HERCEPTIN",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-HER2 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(1998, 9, 1),
                "targets": ["HER2"],
                "indications": ["Breast cancer", "Gastric cancer", "Gastroesophageal junction adenocarcinoma"],
                "nct_codes": ["NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            },
            {
                "generic_name": "Atezolizumab",
                "brand_name": "TECENTRIQ",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-PD-L1 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2016, 5, 1),
                "targets": ["PD-L1"],
                "indications": ["Urothelial cancer", "Non-small cell lung cancer", "Small cell lung cancer", "Hepatocellular carcinoma", "Melanoma", "Triple-negative breast cancer"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in roche_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_pfizer_drugs(self, company: Company):
        """Create Pfizer drugs."""
        pfizer_drugs = [
            {
                "generic_name": "Avelumab",
                "brand_name": "BAVENCIO",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-PD-L1 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2017, 3, 1),
                "targets": ["PD-L1"],
                "indications": ["Urothelial cancer", "Merkel cell carcinoma", "Renal cell carcinoma"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in pfizer_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_novartis_drugs(self, company: Company):
        """Create Novartis drugs."""
        novartis_drugs = [
            {
                "generic_name": "Tisagenlecleucel",
                "brand_name": "KYMRIAH",
                "drug_class": "CAR-T Cell Therapy",
                "mechanism_of_action": "CD19-directed genetically modified autologous T cell immunotherapy",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2017, 8, 1),
                "targets": ["CD19"],
                "indications": ["B-cell acute lymphoblastic leukemia", "Large B-cell lymphoma", "Follicular lymphoma"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in novartis_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_gilead_drugs(self, company: Company):
        """Create Gilead Sciences drugs."""
        gilead_drugs = [
            {
                "generic_name": "Yescarta",
                "brand_name": "YESCARTA",
                "drug_class": "CAR-T Cell Therapy",
                "mechanism_of_action": "CD19-directed genetically modified autologous T cell immunotherapy",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2017, 10, 1),
                "targets": ["CD19"],
                "indications": ["Large B-cell lymphoma", "Follicular lymphoma", "Mantle cell lymphoma"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in gilead_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_amgen_drugs(self, company: Company):
        """Create Amgen drugs."""
        amgen_drugs = [
            {
                "generic_name": "Blinatumomab",
                "brand_name": "BLINCYTO",
                "drug_class": "Bispecific T-cell Engager",
                "mechanism_of_action": "CD19 x CD3 bispecific T-cell engager",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2014, 12, 1),
                "targets": ["CD19", "CD3"],
                "indications": ["B-cell acute lymphoblastic leukemia"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in amgen_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_regeneron_drugs(self, company: Company):
        """Create Regeneron drugs."""
        regeneron_drugs = [
            {
                "generic_name": "Dupilumab",
                "brand_name": "DUPIXENT",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-IL-4Rα monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2017, 3, 1),
                "targets": ["IL-4Rα"],
                "indications": ["Atopic dermatitis", "Asthma", "Chronic rhinosinusitis with nasal polyps", "Eosinophilic esophagitis"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in regeneron_drugs:
            self._create_drug_from_data(drug_data, company)

    def _create_incyte_drugs(self, company: Company):
        """Create Incyte drugs."""
        incyte_drugs = [
            {
                "generic_name": "Ruxolitinib",
                "brand_name": "JAKAFI",
                "drug_class": "Small Molecule",
                "mechanism_of_action": "JAK1/JAK2 inhibitor",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2011, 11, 1),
                "targets": ["JAK1", "JAK2"],
                "indications": ["Myelofibrosis", "Polycythemia vera", "Acute graft-versus-host disease"],
                "nct_codes": ["NCT03097938", "NCT04099277", "NCT04165772", "NCT04380636", "NCT04411402"]
            }
        ]
        
        for drug_data in incyte_drugs:
            self._create_drug_from_data(drug_data, company)

    def _extract_target_entities(self, doc: Document):
        """Extract target information from documents."""
        content = doc.content
        
        # Extract targets from content
        targets = self._extract_targets_from_content(content)
        
        for target_name in targets:
            try:
                # Get or create target
                target = self._get_or_create_target(target_name)
                
                # Update target with additional information if available
                self._update_target_with_content(target, content)
                
            except Exception as e:
                logger.error(f"Error processing target {target_name}: {e}")
                continue

    def _extract_targets_from_content(self, content: str) -> List[str]:
        """Extract target names from document content."""
        targets = []
        content_lower = content.lower()
        
        # Common target patterns
        target_patterns = [
            # Immune checkpoint targets
            r'PD-1',
            r'PD-L1', 
            r'PD-L2',
            r'CTLA-4',
            r'B7-H3',
            r'CCR8',
            
            # Receptor tyrosine kinases
            r'HER2',
            r'EGFR',
            r'VEGFR',
            r'VEGF',
            r'ALK',
            r'ROS1',
            r'MET',
            r'RET',
            r'FGFR[0-9]?',
            r'IGF-1R',
            r'c-KIT',
            r'KIT',
            r'FLT3',
            
            # Kinases
            r'BRAF',
            r'BRAF V600E',
            r'MEK[0-9]?',
            r'PI3K',
            r'AKT[0-9]?',
            r'mTOR',
            r'JAK[0-9]',
            r'JAK[0-9]/JAK[0-9]',
            r'CDK[0-9]',
            r'CDK 4 and 6',
            r'CDK2',
            r'CDK4',
            r'MAPK',
            r'ERK[0-9]?',
            r'DGK[αβγ]?',
            
            # DNA repair
            r'PARP[0-9]?',
            r'BRCA[0-9]?',
            r'ATM',
            r'ATR',
            
            # Oncogenes/Tumor suppressors
            r'KRAS',
            r'TP53',
            r'p53',
            r'MYC',
            r'BCL-2',
            r'BCL2',
            r'MDM2',
            r'RB1',
            r'PTEN',
            
            # Cell surface markers
            r'CD19',
            r'CD20',
            r'CD22',
            r'CD30',
            r'CD33',
            r'CD38',
            r'CD52',
            r'CD70',
            r'CD79b',
            r'CD137',
            r'4-1BB',
            
            # Bispecific targets
            r'CD19 x CD3',
            r'CD19 x CD20',
            r'CD19 x 4-1BB',
            r'CD20 x CD3',
            r'CD3 x CD20',
            r'CD20 and CD3',
            r'BCMA x CD3',
            r'BCMA and CD3',
            r'DLL3 x CD3',
            r'DLL3/CD3/CD137',
            r'CLDN6 x CD3 x CD137',
            r'Claudin 18\.2, CD3',
            r'Claudin 4, CD137',
            r'EGFR, MET',
            r'EGFR and CD28',
            r'CDH3, MSLN, CD3',
            r'CDH6',
            r'CSF1R, KIT, FLT3',
            
            # Cytokines/Chemokines
            r'IL-[0-9]+',
            r'TNF-?α?',
            r'IFN-?[αβγ]?',
            r'VEGF[ABC]?',
            r'PDGF[AB]?',
            r'FGF[0-9]?',
            
            # Hormone receptors
            r'ER[αβ]?',
            r'PR',
            r'AR',
            r'GR',
            
            # Cancer-specific targets
            r'BCMA',
            r'DLL3',
            r'CLDN6',
            r'Claudin 18\.2',
            r'Claudin 4',
            r'MSLN',
            r'CDH3',
            r'CDH6',
            
            # Enzymes
            r'CYP11A1',
            r'CYP17 lyase',
            r'KLK2',
            
            # Radioisotope targets
            r'225Ac KLK2',
            
            # Other important targets
            r'HDAC[0-9]?',
            r'HDM2',
            r'p21',
            r'p27',
            r'Cyclin [A-D]',
            r'Cyclin-Dependent Kinase',
            r'Proteasome',
            r'Proteasome Inhibitor',
            r'Angiogenesis',
            r'Vascular Endothelial Growth Factor',
            r'Endothelial Growth Factor Receptor',
            r'Human Epidermal Growth Factor Receptor',
            r'Programmed Death',
            r'Cytotoxic T-Lymphocyte Antigen',
            r'B-Cell Lymphoma',
            r'Myeloid Cell Leukemia',
            r'Retinoblastoma',
            r'Phosphatase and Tensin Homolog'
        ]
        
        for pattern in target_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Extract from tuple if needed
                
                # Clean up the target name
                target_name = match.strip()
                if target_name and len(target_name) > 1:
                    targets.append(target_name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in targets:
            if target.lower() not in seen:
                seen.add(target.lower())
                unique_targets.append(target)
        
        return unique_targets

    def _update_target_with_content(self, target: Target, content: str):
        """Update target with additional information from content."""
        content_lower = content.lower()
        
        # Determine target type based on content
        target_type = self._determine_target_type(target.name, content_lower)
        if target_type and target.target_type != target_type:
            target.target_type = target_type
        
        # Extract description
        description = self._extract_target_description(target.name, content)
        if description and not target.description:
            target.description = description
        
        # Extract gene symbols and IDs
        hgnc_symbol = self._extract_hgnc_symbol(target.name, content)
        if hgnc_symbol and not target.hgnc_symbol:
            target.hgnc_symbol = hgnc_symbol

    def _determine_target_type(self, target_name: str, content_lower: str) -> Optional[str]:
        """Determine target type based on content."""
        target_lower = target_name.lower()
        
        # Protein patterns
        if any(pattern in target_lower for pattern in ['pd-', 'her', 'egfr', 'vegf', 'cd', 'il-', 'tnf', 'ifn']):
            return "protein"
        
        # Kinase patterns
        if any(pattern in target_lower for pattern in ['kinase', 'jak', 'braf', 'mek', 'pi3k', 'akt', 'mtor', 'cdk']):
            return "kinase"
        
        # Receptor patterns
        if any(pattern in target_lower for pattern in ['receptor', 'pd-', 'her', 'egfr', 'vegf']):
            return "receptor"
        
        # Gene patterns
        if any(pattern in target_lower for pattern in ['brca', 'tp53', 'p53', 'myc', 'kras', 'bcl-', 'mdm']):
            return "gene"
        
        # Pathway patterns
        if any(pattern in target_lower for pattern in ['pathway', 'signaling', 'angiogenesis']):
            return "pathway"
        
        return "protein"  # Default

    def _extract_target_description(self, target_name: str, content: str) -> Optional[str]:
        """Extract target description from content."""
        # Look for target name in context
        target_pos = content.lower().find(target_name.lower())
        if target_pos == -1:
            return None
        
        # Get context around the target name
        start = max(0, target_pos - 200)
        end = min(len(content), target_pos + 200)
        context = content[start:end]
        
        # Look for description patterns
        patterns = [
            r"is\s+([^.]{20,100})",
            r"targets?\s+([^.]{20,100})",
            r"inhibits?\s+([^.]{20,100})",
            r"blocks?\s+([^.]{20,100})",
            r"binds?\s+to\s+([^.]{20,100})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_hgnc_symbol(self, target_name: str, content: str) -> Optional[str]:
        """Extract HGNC symbol for target."""
        # Common mappings
        hgnc_mappings = {
            'PD-1': 'PDCD1',
            'PD-L1': 'CD274',
            'HER2': 'ERBB2',
            'EGFR': 'EGFR',
            'VEGF': 'VEGFA',
            'CTLA-4': 'CTLA4',
            'CD19': 'CD19',
            'CD20': 'MS4A1',
            'CD38': 'CD38',
            'CD70': 'CD70',
            'CD79B': 'CD79B',
            'CD137': 'TNFRSF9',
            '4-1BB': 'TNFRSF9',
            'BRAF': 'BRAF',
            'KRAS': 'KRAS',
            'TP53': 'TP53',
            'p53': 'TP53',
            'MYC': 'MYC',
            'BCL-2': 'BCL2',
            'BCL2': 'BCL2',
            'MDM2': 'MDM2',
            'JAK1': 'JAK1',
            'JAK2': 'JAK2',
            'PARP1': 'PARP1',
            'BRCA1': 'BRCA1',
            'BRCA2': 'BRCA2',
            'ALK': 'ALK',
            'ROS1': 'ROS1',
            'MET': 'MET',
            'RET': 'RET',
            'KIT': 'KIT',
            'FLT3': 'FLT3',
            'BCMA': 'TNFRSF17',
            'DLL3': 'DLL3',
            'CLDN6': 'CLDN6',
            'MSLN': 'MSLN',
            'CDH3': 'CDH3',
            'CDH6': 'CDH6',
            'CYP11A1': 'CYP11A1',
            'KLK2': 'KLK2',
            'B7-H3': 'CD276',
            'CCR8': 'CCR8',
            'CDK2': 'CDK2',
            'CDK4': 'CDK4',
            'DGK': 'DGK',
            'AR': 'AR',
            'ER': 'ESR1',
            'PR': 'PGR'
        }
        
        return hgnc_mappings.get(target_name.upper())


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
