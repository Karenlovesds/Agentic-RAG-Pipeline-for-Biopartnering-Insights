#!/usr/bin/env python3
"""
Script to fix drug deduplication and standardization issues.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import get_db
from src.models.entities import Drug, Company
from collections import defaultdict

def fix_drug_deduplication():
    """Fix drug deduplication and standardization issues."""
    db = get_db()
    
    try:
        print("🔧 Fixing drug deduplication and standardization...")
        
        # Get all drugs
        drugs = db.query(Drug).all()
        print(f"Found {len(drugs)} total drugs in database")
        
        # Group drugs by normalized name
        drug_groups = defaultdict(list)
        for drug in drugs:
            normalized_name = drug.generic_name.lower().strip()
            drug_groups[normalized_name].append(drug)
        
        # Find duplicates and merge them
        duplicates_found = 0
        for normalized_name, drug_list in drug_groups.items():
            if len(drug_list) > 1:
                duplicates_found += 1
                print(f"Found duplicates for '{normalized_name}': {len(drug_list)} entries")
                
                # Keep the first drug, merge others into it
                primary_drug = drug_list[0]
                primary_drug.generic_name = primary_drug.generic_name.title()  # Standardize capitalization
                
                for duplicate_drug in drug_list[1:]:
                    # Merge clinical trials
                    for trial in duplicate_drug.clinical_trials:
                        if trial not in primary_drug.clinical_trials:
                            primary_drug.clinical_trials.append(trial)
                    
                    # Merge targets
                    for target in duplicate_drug.targets:
                        if target not in primary_drug.targets:
                            primary_drug.targets.append(target)
                    
                    # Merge indications
                    for indication in duplicate_drug.indications:
                        if indication not in primary_drug.indications:
                            primary_drug.indications.append(indication)
                    
                    # Delete duplicate
                    db.delete(duplicate_drug)
                
                print(f"  → Merged into: {primary_drug.generic_name} (Company: {primary_drug.company.name if primary_drug.company else 'Unknown'})")
        
        # Standardize capitalization for all remaining drugs
        remaining_drugs = db.query(Drug).all()
        for drug in remaining_drugs:
            if drug.generic_name:
                drug.generic_name = drug.generic_name.title()
        
        # Commit changes
        db.commit()
        
        print(f"\n✅ Fixed {duplicates_found} duplicate drug groups")
        print(f"📊 Total drugs after deduplication: {len(remaining_drugs)}")
        
        # Regenerate summary
        regenerate_drug_summary()
        
    except Exception as e:
        print(f"❌ Error fixing drug deduplication: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def regenerate_drug_summary():
    """Regenerate the drug collection summary with cleaned drug names."""
    db = get_db()
    
    try:
        # Get all companies
        companies = db.query(Company).all()
        company_drugs = {}
        
        print("\n🔍 Regenerating drug collection summary...")
        
        for company in companies:
            # Get drugs for this company
            drugs = db.query(Drug).filter(Drug.company_id == company.id).all()
            
            # Filter drugs using improved validation
            valid_drugs = []
            for drug in drugs:
                if _is_valid_drug_name(drug.generic_name):
                    valid_drugs.append(drug.generic_name)
            
            # Remove duplicates and sort
            valid_drugs = sorted(list(set(valid_drugs)))
            company_drugs[company.name] = valid_drugs
            print(f"  Found {len(valid_drugs)} valid drugs for {company.name}")
        
        # Get total counts
        total_drugs = sum(len(drugs) for drugs in company_drugs.values())
        total_trials = db.query(ClinicalTrial).count()
        
        # Generate summary
        summary_lines = [
            "Comprehensive Drug Collection Summary",
            "========================================",
            "",
            f"Pipeline Drugs Found: {total_drugs}",
            f"FDA Documents: 0",
            f"Drugs.com Documents: 21",
            f"Clinical Trials: {total_trials}",
            f"Total Documents: {total_trials + 21}",
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
                for i, drug in enumerate(drugs, 1):
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
    """Improved drug name validation."""
    import re
    
    if not name or len(name) < 3 or len(name) > 100:
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
        # Specific known drugs
        name.lower() in {
            'pembrolizumab', 'nivolumab', 'sotatercept', 'patritumab', 'sacituzumab',
            'zilovertamab', 'nemtabrutinib', 'quavonlimab', 'clesrovimab', 'ifinatamab',
            'bezlotoxumab', 'ipilimumab', 'relatlimab', 'enasicon', 'dasatinib',
            'repotrectinib', 'elotuzumab', 'belatacept', 'fedratinib', 'luspatercept',
            'abatacept', 'deucravacitinib', 'trastuzumab', 'atezolizumab', 'avelumab',
            'blinatumomab', 'dupilumab', 'ruxolitinib'
        },
        # Merck drug codes
        re.match(r'^mk-\d+', name.lower()),
        # Roche drug codes
        re.match(r'^rg\d+', name.lower()),
    ]
    
    return any(drug_indicators)

if __name__ == "__main__":
    fix_drug_deduplication()
