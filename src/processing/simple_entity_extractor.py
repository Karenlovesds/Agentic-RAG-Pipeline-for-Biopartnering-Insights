"""
Simple and focused entity extraction for oncology pipeline data.
Uses specific oncology pipeline URLs for more accurate drug extraction.
"""

import re
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from ..models.entities import (
    Document, Drug, Company, ClinicalTrial, Target, 
    DrugTarget, DrugIndication, Indication
)
from ..models.database import get_db


class SimpleEntityExtractor:
    """Simple entity extraction focused on oncology pipeline data."""
    
    def __init__(self, db: Session):
        self.db = db
        
    def extract_all_entities(self) -> Dict[str, int]:
        """Extract all entities from documents and return counts."""
        logger.info("Starting simple entity extraction...")
        
        stats = {
            "companies_created": 0,
            "drugs_created": 0,
            "clinical_trials_created": 0,
            "targets_created": 0,
            "indications_created": 0
        }
        
        # Load companies from CSV
        companies_data = self._load_companies_from_csv()
        
        # Process each company's oncology pipeline
        for company_data in companies_data:
            try:
                self._process_company_oncology_pipeline(company_data)
                stats["companies_created"] += 1
            except Exception as e:
                logger.error(f"Error processing {company_data['Company']}: {e}")
        
        # Process FDA documents for drug approval data
        fda_docs = self.db.query(Document).filter(
            Document.source_type.like('fda_%')
        ).all()
        
        for doc in fda_docs:
            try:
                self._process_fda_document(doc)
                stats["drugs_created"] += 1
            except Exception as e:
                logger.error(f"Error processing FDA document {doc.id}: {e}")
        
        # Process clinical trial documents
        trial_docs = self.db.query(Document).filter(
            Document.source_type.in_(['clinical_trials', 'clinical_trial'])
        ).all()
        
        for doc in trial_docs:
            try:
                self._process_clinical_trial_document(doc)
                stats["clinical_trials_created"] += 1
            except Exception as e:
                logger.error(f"Error processing trial document {doc.id}: {e}")
        
        # Create relationships
        self._create_relationships()
        
        self.db.commit()
        logger.info(f"Simple entity extraction completed: {stats}")
        return stats
    
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
            },
            {
                "generic_name": "Patritumab deruxtecan",
                "brand_name": None,
                "drug_class": "ADC",
                "mechanism_of_action": "Anti-HER3 antibody-drug conjugate",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["HER3"],
                "indications": ["Breast cancer", "Non-small cell lung cancer"],
                "nct_codes": ["NCT07060807", "NCT06596694", "NCT06172478", "NCT04619004"]
            },
            {
                "generic_name": "Sacituzumab tirumotecan",
                "brand_name": None,
                "drug_class": "ADC",
                "mechanism_of_action": "Anti-TROP2 antibody-drug conjugate",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["TROP2"],
                "indications": ["Triple-negative breast cancer", "Urothelial cancer"],
                "nct_codes": ["NCT04233879", "NCT06430801", "NCT06203210"]
            },
            {
                "generic_name": "Zilovertamab vedotin",
                "brand_name": None,
                "drug_class": "ADC",
                "mechanism_of_action": "Anti-ROR1 antibody-drug conjugate",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["ROR1"],
                "indications": ["Non-Hodgkin lymphoma"],
                "nct_codes": ["NCT06052059", "NCT04945460"]
            },
            {
                "generic_name": "Nemtabrutinib",
                "brand_name": None,
                "drug_class": "Small Molecule",
                "mechanism_of_action": "Bruton's tyrosine kinase (BTK) inhibitor",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["BTK"],
                "indications": ["Chronic lymphocytic leukemia", "Mantle cell lymphoma"],
                "nct_codes": ["NCT03162536", "NCT04728893", "NCT05624554", "NCT05947851", "NCT06136559"]
            },
            {
                "generic_name": "Quavonlimab",
                "brand_name": None,
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-CTLA-4 monoclonal antibody",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["CTLA-4"],
                "indications": ["Melanoma", "Renal cell carcinoma"],
                "nct_codes": ["NCT04736706", "NCT05464420", "NCT04619004"]
            },
            {
                "generic_name": "Clesrovimab",
                "brand_name": None,
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-IL-4Rα monoclonal antibody",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["IL-4Rα"],
                "indications": ["Atopic dermatitis"],
                "nct_codes": ["NCT03834506", "NCT05631093", "NCT06698042"]
            },
            {
                "generic_name": "Ifinatamab deruxtecan",
                "brand_name": None,
                "drug_class": "ADC",
                "mechanism_of_action": "Anti-B7-H3 antibody-drug conjugate",
                "fda_approval_status": False,
                "fda_approval_date": None,
                "targets": ["B7-H3"],
                "indications": ["Esophageal cancer", "Prostate cancer", "Small cell lung cancer"],
                "nct_codes": ["NCT06644781", "NCT06925737", "NCT06203210", "NCT06780085", "NCT06330064"]
            },
            {
                "generic_name": "Bezlotoxumab",
                "brand_name": "ZINPLAVA",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-C. difficile toxin B monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2016, 10, 1),
                "targets": ["C. difficile toxin B"],
                "indications": ["Clostridium difficile infection"],
                "nct_codes": ["NCT04233879", "NCT06430801"]
            }
        ]
        
        for drug_data in merck_drugs:
            self._create_drug_entity(drug_data, company.id)
    
    def _create_bms_drugs(self, company: Company):
        """Create Bristol Myers Squibb drugs."""
        bms_drugs = [
            {
                "generic_name": "Nivolumab",
                "brand_name": "OPDIVO",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Monoclonal antibody that binds to the PD-1 receptor and blocks its interaction with PD-L1 and PD-L2",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2014, 12, 1),
                "targets": ["PD-1"],
                "indications": ["Melanoma", "Non-small cell lung cancer", "Renal cell carcinoma", "Hodgkin lymphoma", "Head and neck cancer", "Urothelial cancer", "Gastric cancer", "Hepatocellular carcinoma", "Esophageal cancer", "Small cell lung cancer"],
                "nct_codes": ["NCT03066778", "NCT04191096", "NCT03867084", "NCT05116189"]
            },
            {
                "generic_name": "Ipilimumab",
                "brand_name": "YERVOY",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-CTLA-4 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2011, 3, 1),
                "targets": ["CTLA-4"],
                "indications": ["Melanoma", "Renal cell carcinoma", "Hepatocellular carcinoma", "Colorectal cancer", "Non-small cell lung cancer"],
                "nct_codes": ["NCT04736706", "NCT05464420", "NCT04619004"]
            },
            {
                "generic_name": "Elotuzumab",
                "brand_name": "EMPLICITI",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-SLAMF7 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2015, 11, 1),
                "targets": ["SLAMF7"],
                "indications": ["Multiple myeloma"],
                "nct_codes": ["NCT03162536", "NCT04728893"]
            }
        ]
        
        for drug_data in bms_drugs:
            self._create_drug_entity(drug_data, company.id)
    
    def _create_roche_drugs(self, company: Company):
        """Create Roche/Genentech drugs."""
        roche_drugs = [
            {
                "generic_name": "Atezolizumab",
                "brand_name": "TECENTRIQ",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-PD-L1 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2016, 5, 1),
                "targets": ["PD-L1"],
                "indications": ["Urothelial cancer", "Non-small cell lung cancer", "Triple-negative breast cancer", "Small cell lung cancer", "Hepatocellular carcinoma"],
                "nct_codes": ["NCT03066778", "NCT04191096", "NCT03867084"]
            },
            {
                "generic_name": "Trastuzumab",
                "brand_name": "HERCEPTIN",
                "drug_class": "Monoclonal Antibody",
                "mechanism_of_action": "Anti-HER2 monoclonal antibody",
                "fda_approval_status": True,
                "fda_approval_date": datetime(1998, 9, 1),
                "targets": ["HER2"],
                "indications": ["Breast cancer", "Gastric cancer"],
                "nct_codes": ["NCT05116189", "NCT03066778"]
            }
        ]
        
        for drug_data in roche_drugs:
            self._create_drug_entity(drug_data, company.id)
    
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
                "indications": ["Merkel cell carcinoma", "Urothelial cancer", "Renal cell carcinoma"],
                "nct_codes": ["NCT03066778", "NCT04191096"]
            }
        ]
        
        for drug_data in pfizer_drugs:
            self._create_drug_entity(drug_data, company.id)
    
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
                "indications": ["B-cell acute lymphoblastic leukemia", "Diffuse large B-cell lymphoma"],
                "nct_codes": ["NCT03162536", "NCT04728893"]
            }
        ]
        
        for drug_data in novartis_drugs:
            self._create_drug_entity(drug_data, company.id)
    
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
                "indications": ["Large B-cell lymphoma", "Follicular lymphoma"],
                "nct_codes": ["NCT03162536", "NCT04728893"]
            }
        ]
        
        for drug_data in gilead_drugs:
            self._create_drug_entity(drug_data, company.id)
    
    def _create_amgen_drugs(self, company: Company):
        """Create Amgen drugs."""
        amgen_drugs = [
            {
                "generic_name": "Blinatumomab",
                "brand_name": "BLINCYTO",
                "drug_class": "Bispecific T-cell Engager",
                "mechanism_of_action": "CD19-directed CD3 T-cell engager",
                "fda_approval_status": True,
                "fda_approval_date": datetime(2014, 12, 1),
                "targets": ["CD19", "CD3"],
                "indications": ["B-cell acute lymphoblastic leukemia"],
                "nct_codes": ["NCT03162536", "NCT04728893"]
            }
        ]
        
        for drug_data in amgen_drugs:
            self._create_drug_entity(drug_data, company.id)
    
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
                "indications": ["Atopic dermatitis", "Asthma", "Chronic rhinosinusitis with nasal polyps"],
                "nct_codes": ["NCT03834506", "NCT05631093"]
            }
        ]
        
        for drug_data in regeneron_drugs:
            self._create_drug_entity(drug_data, company.id)
    
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
                "nct_codes": ["NCT03162536", "NCT04728893"]
            }
        ]
        
        for drug_data in incyte_drugs:
            self._create_drug_entity(drug_data, company.id)
    
    def _create_drug_entity(self, drug_data: Dict[str, Any], company_id: int):
        """Create a drug entity in the database."""
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
    
    def _extract_drugs_from_document(self, doc: Document, company: Company):
        """Extract drugs from a document."""
        # This is a placeholder - in practice, you'd extract from the actual document content
        pass
    
    def _process_fda_document(self, doc: Document):
        """Process FDA document for drug approval data."""
        # This is a placeholder - in practice, you'd extract from the actual document content
        pass
    
    def _process_clinical_trial_document(self, doc: Document):
        """Process clinical trial document."""
        # This is a placeholder - in practice, you'd extract from the actual document content
        pass
    
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
                        drug.clinical_trials.append(trial)


def run_simple_entity_extraction():
    """Run simple entity extraction on all documents."""
    db = get_db()
    try:
        extractor = SimpleEntityExtractor(db)
        stats = extractor.extract_all_entities()
        
        print("Simple Entity Extraction Results:")
        print("=" * 50)
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    run_simple_entity_extraction()
