#!/usr/bin/env python3
"""
Script to regenerate the drug collection summary with improved drug validation.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import get_db
from src.models.entities import Drug, Company, ClinicalTrial, Document
from src.processing.entity_extractor import EntityExtractor
from datetime import datetime

def regenerate_drug_summary():
    """Regenerate the drug collection summary with cleaned drug names."""
    db = get_db()
    
    try:
        # Get all companies
        companies = db.query(Company).all()
        company_drugs = {}
        
        print("🔍 Regenerating drug collection summary with improved validation...")
        
        for company in companies:
            print(f"Processing {company.name}...")
            
            # Get drugs for this company
            drugs = db.query(Drug).filter(Drug.company_id == company.id).all()
            
            # Filter drugs using improved validation
            valid_drugs = []
            for drug in drugs:
                if _is_valid_drug_name(drug.generic_name):
                    valid_drugs.append(drug.generic_name)
            
            company_drugs[company.name] = valid_drugs
            print(f"  Found {len(valid_drugs)} valid drugs for {company.name}")
        
        # Get total counts
        total_drugs = sum(len(drugs) for drugs in company_drugs.values())
        total_trials = db.query(ClinicalTrial).count()
        total_documents = db.query(Document).count()
        
        # Count documents by type
        fda_docs = db.query(Document).filter(Document.source_type.like('%fda%')).count()
        clinical_trial_docs = db.query(Document).filter(Document.source_type.like('%clinical%')).count()
        company_docs = db.query(Document).filter(Document.source_type.like('%company%')).count()
        
        # Generate summary
        summary_lines = [
            "Comprehensive Drug Collection Summary",
            "========================================",
            "",
            f"Pipeline Drugs Found: {total_drugs}",
            f"FDA Documents: {fda_docs}",
            f"Clinical Trial Documents: {clinical_trial_docs}",
            f"Company Documents: {company_docs}",
            f"Clinical Trials (Extracted): {total_trials}",
            f"Total Documents: {total_documents}",
            f"Success: True",
            "",
            "Pipeline Drugs by Company:",
            "==============================",
            ""
        ]
        
        for company_name, drugs in company_drugs.items():
            if drugs:
                summary_lines.append(f"{company_name}:")
                summary_lines.append("-" * (len(company_name) + 1))
                for i, drug in enumerate(sorted(drugs), 1):
                    summary_lines.append(f"  {i:3d}. {drug}")
                summary_lines.append("")
        
        # Add summary by company
        summary_lines.extend([
            "",
            "Summary by Company:",
            "===================="
        ])
        
        for company_name, drugs in company_drugs.items():
            summary_lines.append(f"  {company_name}: {len(drugs)} drugs")
        
        # Write to file
        output_path = "outputs/drug_collection_summary.txt"
        with open(output_path, 'w') as f:
            f.write('\n'.join(summary_lines))
        
        print(f"\n✅ Drug collection summary regenerated!")
        print(f"📁 Saved to: {output_path}")
        print(f"📊 Total valid drugs: {total_drugs}")
        
        # Show sample of cleaned drugs
        print("\n🧹 Sample of cleaned drug names:")
        all_drugs = []
        for drugs in company_drugs.values():
            all_drugs.extend(drugs)
        
        for i, drug in enumerate(sorted(all_drugs)[:10], 1):
            print(f"  {i:2d}. {drug}")
        
        if len(all_drugs) > 10:
            print(f"  ... and {len(all_drugs) - 10} more")
            
    except Exception as e:
        print(f"❌ Error regenerating drug summary: {e}")
        raise
    finally:
        db.close()

def _is_valid_drug_name(name: str) -> bool:
    """Improved drug name validation (same logic as in the extractors)."""
    import re
    
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
    
    # Positive indicators for actual drug names
    drug_indicators = [
        # Monoclonal antibodies
        name.lower().endswith(('mab', 'zumab', 'ximab')),
        # Kinase inhibitors
        name.lower().endswith(('nib', 'tinib')),
        # Fusion proteins
        name.lower().endswith('cept'),
        # PARP inhibitors
        name.lower().endswith('parib'),
        # CDK inhibitors
        name.lower().endswith('ciclib'),
        # Specific known drugs
        name.lower() in {
            'pembrolizumab', 'nivolumab', 'sotatercept', 'patritumab', 'sacituzumab',
            'zilovertamab', 'nemtabrutinib', 'quavonlimab', 'clesrovimab', 'ifinatamab',
            'bezlotoxumab', 'ipilimumab', 'relatlimab', 'enasicon', 'dasatinib',
            'repotrectinib', 'elotuzumab', 'belatacept', 'fedratinib', 'luspatercept',
            'abatacept', 'deucravacitinib', 'olaparib', 'palbociclib', 'rucaparib',
            'niraparib', 'talazoparib', 'ribociclib', 'abemaciclib'
        },
        # Merck drug codes
        re.match(r'^mk-\d+', name.lower()),
        # Roche drug codes
        re.match(r'^rg\d+', name.lower()),
    ]
    
    return any(drug_indicators)

if __name__ == "__main__":
    regenerate_drug_summary()
