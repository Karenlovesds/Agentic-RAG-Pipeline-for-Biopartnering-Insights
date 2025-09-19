"""Minimal processing pipeline: heuristic entity extraction and linking.

This is a placeholder implementation to demonstrate flow:
- Extract companies from the configured list and ensure DB rows exist
- Heuristically create drugs if certain keywords appear in documents
- Link trials to companies by sponsor name containment
"""

from __future__ import annotations

from typing import List, Dict, Set
from loguru import logger
from sqlalchemy.orm import Session
import re

from config.config import get_target_companies
from src.models.entities import Company, Drug, ClinicalTrial, Document, Target, DrugTarget, DrugIndication


COMMON_DRUG_KEYWORDS = [
    # Monoclonal antibodies
    "pembrolizumab", "nivolumab", "trastuzumab", "bevacizumab", "rituximab", 
    "ipilimumab", "atezolizumab", "durvalumab", "avelumab", "cemiplimab",
    "elotuzumab", "belatacept", "relatlimab", "quavonlimab", "clesrovimab",
    "ifinatamab", "bezlotoxumab", "patritumab", "sacituzumab", "zilovertamab",
    "nemtabrutinib", "enasicon",
    
    # Kinase inhibitors
    "palbociclib", "olaparib", "dasatinib", "repotrectinib", "fedratinib",
    "deucravacitinib", "rucaparib", "niraparib", "talazoparib", "ribociclib",
    "abemaciclib", "alectinib", "ceritinib", "crizotinib", "lorlatinib",
    
    # Other oncology drugs
    "doxorubicin", "cisplatin", "carboplatin", "paclitaxel", "docetaxel",
    "gemcitabine", "fluorouracil", "methotrexate", "cyclophosphamide",
    "ifosfamide", "etoposide", "vinblastine", "vincristine", "vinorelbine",
    
    # CAR-T and cell therapies
    "tisagenlecleucel", "axicabtagene", "brexucabtagene", "idecabtagene",
    "lisocabtagene", "ciltacabtagene", "yescarta", "kymriah", "carvykti",
    
    # Other targeted therapies
    "sotatercept", "luspatercept", "blinatumomab", "mosunetuzumab",
    "glofitamab", "cevostamab", "polatuzumab", "inavolisib", "giredestrant",
    "codrituzumab", "rg6810"
]

COMMON_TARGETS = [
    # Immune checkpoints
    "PD-1", "PD-L1", "PD-L2", "CTLA-4", "LAG-3", "TIM-3", "TIGIT", "VISTA",
    
    # Growth factor receptors
    "HER2", "EGFR", "VEGFR", "FGFR", "IGF-1R", "MET", "ALK", "ROS1", "RET",
    "c-MET", "AXL", "MERTK", "TAM", "TIE2", "FLT3", "KIT", "PDGFR",
    
    # Kinases
    "JAK1", "JAK2", "JAK3", "TYK2", "BTK", "PI3K", "AKT", "mTOR", "MEK", "ERK",
    "CDK4", "CDK6", "CDK2", "CDK1", "AURORA", "PLK", "WEE1", "CHK1", "ATR",
    
    # Cell surface markers
    "CD19", "CD20", "CD22", "CD30", "CD33", "CD38", "CD52", "CD79b", "CD138",
    "CD3", "CD4", "CD8", "CD25", "CD28", "CD40", "CD80", "CD86", "CD137",
    
    # Apoptosis and cell cycle
    "BCL-2", "BCL-XL", "MCL-1", "p53", "MDM2", "p21", "p27", "RB", "E2F",
    "Caspase", "PARP", "ATM", "ATR", "DNA-PK", "CHK1", "CHK2",
    
    # Angiogenesis
    "VEGF", "VEGFR1", "VEGFR2", "VEGFR3", "Angiopoietin", "TIE2", "Notch",
    "DLL4", "Jagged", "HIF-1α", "HIF-2α",
    
    # Epigenetic targets
    "HDAC", "DNMT", "EZH2", "BRD4", "BET", "KDM", "LSD1", "PRMT", "SETD7",
    
    # Hormone receptors
    "ER", "PR", "AR", "GR", "MR", "TR", "VDR", "RAR", "RXR", "PPAR",
    
    # Other important targets
    "IL-4Rα", "IL-13Rα1", "IL-17A", "IL-23", "TNF-α", "IL-1β", "IL-6",
    "CCR4", "CCR5", "CXCR4", "S1PR", "SMO", "GLI", "WNT", "β-catenin",
    "MYC", "MYCN", "MYCL", "N-MYC", "L-MYC", "MAX", "MAD", "MXI1"
]

# Drug-target mapping for backfilling
DRUG_TARGET_MAPPING = {
    "pembrolizumab": ["PD-1"],
    "nivolumab": ["PD-1"],
    "ipilimumab": ["CTLA-4"],
    "trastuzumab": ["HER2"],
    "bevacizumab": ["VEGF"],
    "rituximab": ["CD20"],
    "atezolizumab": ["PD-L1"],
    "durvalumab": ["PD-L1"],
    "avelumab": ["PD-L1"],
    "cemiplimab": ["PD-1"],
    "tisagenlecleucel": ["CD19"],
    "axicabtagene": ["CD19"],
    "brexucabtagene": ["CD19"],
    "idecabtagene": ["CD19"],
    "lisocabtagene": ["CD19"],
    "ciltacabtagene": ["CD19"],
    "yescarta": ["CD19"],
    "kymriah": ["CD19"],
    "carvykti": ["BCMA"],
    "blinatumomab": ["CD19", "CD3"],
    "sotatercept": ["Activin"],
    "luspatercept": ["Activin"],
    "palbociclib": ["CDK4", "CDK6"],
    "ribociclib": ["CDK4", "CDK6"],
    "abemaciclib": ["CDK4", "CDK6"],
    "olaparib": ["PARP"],
    "rucaparib": ["PARP"],
    "niraparib": ["PARP"],
    "talazoparib": ["PARP"],
    "dasatinib": ["BCR-ABL", "SRC"],
    "crizotinib": ["ALK", "ROS1", "MET"],
    "alectinib": ["ALK"],
    "ceritinib": ["ALK"],
    "lorlatinib": ["ALK"],
    "repotrectinib": ["ALK", "ROS1", "NTRK"],
    "fedratinib": ["JAK2"],
    "deucravacitinib": ["TYK2"],
    "mosunetuzumab": ["CD20", "CD3"],
    "glofitamab": ["CD20", "CD3"],
    "cevostamab": ["FcRH5"],
    "polatuzumab": ["CD79b"],
    "inavolisib": ["PI3K"],
    "giredestrant": ["ER"],
    "codrituzumab": ["MET"],
    "rg6810": ["Unknown"]
}


def ensure_companies(db: Session) -> int:
    count_created = 0
    for name in get_target_companies():
        if not db.query(Company).filter(Company.name == name).first():
            db.add(Company(name=name))
            count_created += 1
    if count_created:
        db.commit()
    return count_created


def extract_drugs_from_documents(db: Session) -> int:
    created = 0
    docs = db.query(Document).all()
    companies = {c.name: c.id for c in db.query(Company).all()}
    for doc in docs:
        text = (doc.content or "").lower()
        for kw in COMMON_DRUG_KEYWORDS:
            if kw in text:
                # Use first company found in doc title/url as a naive owner
                owner_id = None
                for cname, cid in companies.items():
                    if (doc.title and cname.lower() in doc.title.lower()) or cname.lower() in doc.source_url.lower():
                        owner_id = cid
                        break
                # Check if this specific drug-company combination already exists
                existing_drug = db.query(Drug).filter(
                    Drug.generic_name == kw,
                    Drug.company_id == (owner_id or list(companies.values())[0])
                ).first()
                
                if not existing_drug:
                    db.add(Drug(generic_name=kw, company_id=owner_id or list(companies.values())[0]))
                    created += 1
    if created:
        db.commit()
    return created


def link_trials_to_companies(db: Session) -> int:
    updates = 0
    companies = db.query(Company).all()
    trials = db.query(ClinicalTrial).all()
    for t in trials:
        if t.sponsor_id:
            continue
        for c in companies:
            if t.title and c.name.lower() in t.title.lower():
                t.sponsor_id = c.id
                updates += 1
                break
    if updates:
        db.commit()
    return updates


def extract_targets_from_documents(db: Session) -> int:
    """Extract targets from documents and create target entities."""
    targets_created = 0
    docs = db.query(Document).all()
    
    for doc in docs:
        content = doc.content or ""
        found_targets = set()
        
        # Look for targets in the content using regex patterns
        for target in COMMON_TARGETS:
            # Case-insensitive search with word boundaries
            pattern = r'\b' + re.escape(target) + r'\b'
            if re.search(pattern, content, re.IGNORECASE):
                found_targets.add(target)
        
        # Create target entities
        for target_name in found_targets:
            existing_target = db.query(Target).filter(
                Target.name.ilike(f"%{target_name}%")
            ).first()
            
            if not existing_target:
                target = Target(
                    name=target_name,
                    target_type="protein",  # Default type
                    description=f"Target found in document: {doc.title or 'Unknown'}"
                )
                db.add(target)
                targets_created += 1
    
    if targets_created:
        db.commit()
    
    return targets_created


def backfill_drug_targets(db: Session) -> int:
    """Backfill drug-target relationships for existing drugs."""
    relationships_created = 0
    
    # Get all drugs
    drugs = db.query(Drug).all()
    
    for drug in drugs:
        drug_name = drug.generic_name.lower()
        
        # Check if drug has known targets
        if drug_name in DRUG_TARGET_MAPPING:
            target_names = DRUG_TARGET_MAPPING[drug_name]
            
            for target_name in target_names:
                # Find or create target
                target = db.query(Target).filter(
                    Target.name.ilike(f"%{target_name}%")
                ).first()
                
                if not target:
                    target = Target(
                        name=target_name,
                        target_type="protein",
                        description=f"Target for {drug.generic_name}"
                    )
                    db.add(target)
                    db.flush()  # Get the ID
                
                # Check if relationship already exists
                existing_rel = db.query(DrugTarget).filter(
                    DrugTarget.drug_id == drug.id,
                    DrugTarget.target_id == target.id
                ).first()
                
                if not existing_rel:
                    drug_target = DrugTarget(
                        drug_id=drug.id,
                        target_id=target.id,
                        relationship_type="inhibits"  # Default relationship
                    )
                    db.add(drug_target)
                    relationships_created += 1
    
    if relationships_created:
        db.commit()
    
    return relationships_created


def extract_targets_from_drug_names(db: Session) -> int:
    """Extract targets from drug names using pattern matching."""
    targets_created = 0
    drugs = db.query(Drug).all()
    
    for drug in drugs:
        drug_name = drug.generic_name.lower()
        found_targets = set()
        
        # Pattern matching for drug names
        if drug_name.endswith('mab'):
            # Monoclonal antibodies - extract target from name
            if 'pembro' in drug_name or 'keytruda' in drug_name:
                found_targets.add('PD-1')
            elif 'nivo' in drug_name or 'opdivo' in drug_name:
                found_targets.add('PD-1')
            elif 'trastu' in drug_name or 'herceptin' in drug_name:
                found_targets.add('HER2')
            elif 'bevaci' in drug_name or 'avastin' in drug_name:
                found_targets.add('VEGF')
            elif 'rituxi' in drug_name or 'rituxan' in drug_name:
                found_targets.add('CD20')
            elif 'ipili' in drug_name or 'yervoy' in drug_name:
                found_targets.add('CTLA-4')
            elif 'atezo' in drug_name or 'tecentriq' in drug_name:
                found_targets.add('PD-L1')
            elif 'durva' in drug_name or 'imfinzi' in drug_name:
                found_targets.add('PD-L1')
            elif 'avelu' in drug_name or 'bavencio' in drug_name:
                found_targets.add('PD-L1')
        
        elif drug_name.endswith('nib'):
            # Kinase inhibitors
            if 'palbo' in drug_name or 'ibrance' in drug_name:
                found_targets.update(['CDK4', 'CDK6'])
            elif 'ribo' in drug_name or 'kisqali' in drug_name:
                found_targets.update(['CDK4', 'CDK6'])
            elif 'abema' in drug_name or 'verzenio' in drug_name:
                found_targets.update(['CDK4', 'CDK6'])
            elif 'olapa' in drug_name or 'lynparza' in drug_name:
                found_targets.add('PARP')
            elif 'ruca' in drug_name or 'rubraca' in drug_name:
                found_targets.add('PARP')
            elif 'nira' in drug_name or 'zejula' in drug_name:
                found_targets.add('PARP')
            elif 'tala' in drug_name or 'talzenna' in drug_name:
                found_targets.add('PARP')
            elif 'dasa' in drug_name or 'sprycel' in drug_name:
                found_targets.update(['BCR-ABL', 'SRC'])
            elif 'crizo' in drug_name or 'xalkori' in drug_name:
                found_targets.update(['ALK', 'ROS1', 'MET'])
            elif 'alec' in drug_name or 'alecensa' in drug_name:
                found_targets.add('ALK')
            elif 'ceri' in drug_name or 'zykadia' in drug_name:
                found_targets.add('ALK')
            elif 'lorla' in drug_name or 'lorviqua' in drug_name:
                found_targets.add('ALK')
        
        # Create targets and relationships
        for target_name in found_targets:
            target = db.query(Target).filter(
                Target.name.ilike(f"%{target_name}%")
            ).first()
            
            if not target:
                target = Target(
                    name=target_name,
                    target_type="protein",
                    description=f"Target extracted from drug name: {drug.generic_name}"
                )
                db.add(target)
                db.flush()
                targets_created += 1
            
            # Create relationship if it doesn't exist
            existing_rel = db.query(DrugTarget).filter(
                DrugTarget.drug_id == drug.id,
                DrugTarget.target_id == target.id
            ).first()
            
            if not existing_rel:
                drug_target = DrugTarget(
                    drug_id=drug.id,
                    target_id=target.id,
                    relationship_type="inhibits"
                )
                db.add(drug_target)
    
    if targets_created:
        db.commit()
    
    return targets_created


def link_clinical_trials_to_drugs(db: Session) -> int:
    """Link clinical trials to drugs based on drug names in trial titles and content."""
    try:
        from sqlalchemy import func
        
        # Get all drugs and trials
        drugs = db.query(Drug).all()
        trials = db.query(ClinicalTrial).filter(ClinicalTrial.drug_id.is_(None)).all()
        
        linked_count = 0
        
        for trial in trials:
            # Extract drug names from trial title and content
            trial_text = f"{trial.title or ''} {trial.study_population or ''}".lower()
            
            # Find matching drugs
            for drug in drugs:
                drug_name = drug.generic_name.lower()
                
                # Check if drug name appears in trial text
                if drug_name in trial_text:
                    # Link the trial to the drug
                    trial.drug_id = drug.id
                    linked_count += 1
                    logger.debug(f"Linked trial {trial.nct_id} to drug {drug.generic_name}")
                    break  # Only link to the first matching drug
        
        if linked_count > 0:
            db.commit()
            logger.info(f"✅ Linked {linked_count} clinical trials to drugs")
        
        return linked_count
        
    except Exception as e:
        logger.error(f"❌ Error linking clinical trials to drugs: {e}")
        return 0


def deduplicate_drugs_within_company(db: Session) -> dict:
    """Remove duplicate drugs within the same company, but keep same drug across different companies."""
    try:
        from sqlalchemy import func
        
        # Find duplicates within the same company
        duplicates_query = db.query(Drug.generic_name, Drug.company_id).group_by(
            Drug.generic_name, Drug.company_id
        ).having(func.count(Drug.id) > 1).all()
        
        removed_count = 0
        
        for generic_name, company_id in duplicates_query:
            # Get all drugs with this name and company
            drugs = db.query(Drug).filter(
                Drug.generic_name == generic_name,
                Drug.company_id == company_id
            ).all()
            
            if len(drugs) > 1:
                # Keep the first one, remove the rest
                keep_drug = drugs[0]
                
                for drug in drugs[1:]:
                    # Transfer any relationships to the kept drug
                    # Only transfer if the relationship doesn't already exist
                    for target_rel in drug.targets:
                        existing_target_rel = db.query(DrugTarget).filter(
                            DrugTarget.drug_id == keep_drug.id,
                            DrugTarget.target_id == target_rel.target_id
                        ).first()
                        if not existing_target_rel:
                            target_rel.drug_id = keep_drug.id
                        else:
                            db.delete(target_rel)
                    
                    for indication_rel in drug.indications:
                        existing_indication_rel = db.query(DrugIndication).filter(
                            DrugIndication.drug_id == keep_drug.id,
                            DrugIndication.indication_id == indication_rel.indication_id
                        ).first()
                        if not existing_indication_rel:
                            indication_rel.drug_id = keep_drug.id
                        else:
                            db.delete(indication_rel)
                    
                    for trial in drug.clinical_trials:
                        trial.drug_id = keep_drug.id
                    
                    # Remove the duplicate
                    db.delete(drug)
                    removed_count += 1
        
        if removed_count > 0:
            db.commit()
            logger.info(f"✅ Removed {removed_count} duplicate drugs within companies")
        
        return {
            "duplicates_removed": removed_count,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error deduplicating drugs: {e}")
        return {
            "error": str(e),
            "success": False
        }


def generate_csv_exports(db: Session) -> dict:
    """Generate CSV exports automatically after database updates."""
    try:
        from .csv_export import export_basic, export_drug_table
        
        # Generate the main biopharma drugs CSV
        biopharma_csv = export_drug_table(db, "outputs/biopharma_drugs.csv")
        
        # Generate basic export CSV
        basic_csv = export_basic(db, "outputs/basic_export.csv")
        
        # Generate drug collection summary
        summary_content = generate_drug_summary(db)
        with open("outputs/drug_collection_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary_content)
        
        logger.info("✅ CSV exports generated successfully")
        return {
            "biopharma_drugs_csv": biopharma_csv,
            "basic_export_csv": basic_csv,
            "drug_summary_txt": "outputs/drug_collection_summary.txt",
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating CSV exports: {e}")
        return {
            "error": str(e),
            "success": False
        }


def generate_drug_summary(db: Session) -> str:
    """Generate drug collection summary text file."""
    try:
        # Get counts
        total_drugs = db.query(Drug).count()
        total_companies = db.query(Company).count()
        total_trials = db.query(ClinicalTrial).count()
        total_targets = db.query(Target).count()
        
        # Get drugs by company
        companies_with_drugs = db.query(Company).join(Drug).distinct().all()
        
        summary_lines = [
            "Comprehensive Drug Collection Summary",
            "========================================",
            "",
            f"Pipeline Drugs Found: {total_drugs}",
            f"FDA Documents: 0",  # Placeholder
            f"Drugs.com Documents: 0",  # Placeholder
            f"Clinical Trials: {total_trials}",
            f"Targets: {total_targets}",
            f"Total Documents: 0",  # Placeholder
            f"Success: True",
            "",
            "Pipeline Drugs by Company:",
            "==============================",
            ""
        ]
        
        for company in companies_with_drugs:
            company_drugs = db.query(Drug).filter(Drug.company_id == company.id).all()
            if company_drugs:
                summary_lines.append(f"{company.name}:")
                summary_lines.append("-" * len(company.name) + "-")
                for i, drug in enumerate(company_drugs, 1):
                    summary_lines.append(f"    {i}. {drug.generic_name}")
                summary_lines.append("")
        
        return "\n".join(summary_lines)
        
    except Exception as e:
        logger.error(f"Error generating drug summary: {e}")
        return f"Error generating summary: {e}"


def run_processing(db: Session) -> dict:
    logger.info("Processing pipeline start")
    created_companies = ensure_companies(db)
    created_drugs = extract_drugs_from_documents(db)
    linked_trials = link_trials_to_companies(db)
    
    # Extract targets from documents and drug names
    targets_from_docs = extract_targets_from_documents(db)
    targets_from_names = extract_targets_from_drug_names(db)
    
    # Backfill drug-target relationships
    drug_target_relationships = backfill_drug_targets(db)
    
    # Link clinical trials to drugs
    trials_linked_to_drugs = link_clinical_trials_to_drugs(db)
    
    # Remove duplicates within the same company
    deduplication_results = deduplicate_drugs_within_company(db)
    
    # Auto-generate CSV files
    csv_results = generate_csv_exports(db)
    
    logger.info("Processing pipeline done")
    return {
        "companies_created": created_companies,
        "drugs_created": created_drugs,
        "trials_linked": linked_trials,
        "targets_from_docs": targets_from_docs,
        "targets_from_names": targets_from_names,
        "drug_target_relationships": drug_target_relationships,
        "trials_linked_to_drugs": trials_linked_to_drugs,
        "deduplication": deduplication_results,
        "csv_generated": csv_results,
    }


