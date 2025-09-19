#!/usr/bin/env python3
"""
Script to populate the database with comprehensive drug data from the example CSV.
This will create a rich dataset similar to the biopharma_pipeline_output_example.csv.
"""

import pandas as pd
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.database import get_db
from src.models.entities import Company, Drug, ClinicalTrial, Target, Indication, DrugTarget, DrugIndication

def populate_from_example():
    """Populate database with comprehensive drug data from example CSV."""
    print("🚀 Populating database with comprehensive drug data from example...")
    
    # Read the example data
    example_file = "data/biopharma_pipeline_output_example.csv"
    if not os.path.exists(example_file):
        print(f"❌ Example file not found: {example_file}")
        return
    
    df = pd.read_csv(example_file)
    print(f"📊 Loaded {len(df)} drugs from example data")
    
    db = get_db()
    
    try:
        # Create or get Roche/Genentech company (since the example data is from Roche)
        company = db.query(Company).filter(Company.name == "Roche/Genentech").first()
        if not company:
            company = Company(
                name="Roche/Genentech",
                website_url="https://www.roche.com",
                pipeline_url="https://www.roche.com/solutions/pipeline",
                description="Roche is a global pioneer in pharmaceuticals and diagnostics"
            )
            db.add(company)
            db.commit()
            print(f"✅ Created company: {company.name}")
        else:
            print(f"✅ Found existing company: {company.name}")
        
        # Process each drug from the example data
        created_drugs = 0
        for _, row in df.iterrows():
            if pd.isna(row['Generic name']) or row['Generic name'].strip() == '':
                continue
                
            # Check if drug already exists
            existing_drug = db.query(Drug).filter(
                Drug.generic_name == row['Generic name'].strip(),
                Drug.company_id == company.id
            ).first()
            
            if existing_drug:
                print(f"⏭️  Skipping existing drug: {row['Generic name']}")
                continue
            
            # Create drug
            drug = Drug(
                generic_name=row['Generic name'].strip(),
                brand_name=row['Brand name'] if pd.notna(row['Brand name']) else None,
                drug_class=row['Drug Class'] if pd.notna(row['Drug Class']) else None,
                fda_approval_status=row['FDA Approval'] if pd.notna(row['FDA Approval']) else None,
                fda_approval_date=row['FDA Approval'] if pd.notna(row['FDA Approval']) else None,
                mechanism_of_action=row['Mechanism'] if pd.notna(row['Mechanism']) else None,
                company_id=company.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(drug)
            db.flush()  # Flush to get the drug ID
            
            # Create target if specified
            if pd.notna(row['Target']) and row['Target'].strip():
                target = db.query(Target).filter(Target.name == row['Target'].strip()).first()
                if not target:
                    target = Target(
                        name=row['Target'].strip(),
                        description=f"Target for {drug.generic_name}",
                        created_at=datetime.utcnow()
                    )
                    db.add(target)
                    db.flush()
                
                # Create drug-target relationship
                drug_target = DrugTarget(
                    drug_id=drug.id,
                    target_id=target.id,
                    created_at=datetime.utcnow()
                )
                db.add(drug_target)
            
            # Create indication if specified
            if pd.notna(row['Indication Approved']) and row['Indication Approved'].strip():
                indication = db.query(Indication).filter(Indication.name == row['Indication Approved'].strip()).first()
                if not indication:
                    indication = Indication(
                        name=row['Indication Approved'].strip(),
                        description=f"Indication for {drug.generic_name}",
                        created_at=datetime.utcnow()
                    )
                    db.add(indication)
                    db.flush()
                
                # Create drug-indication relationship
                drug_indication = DrugIndication(
                    drug_id=drug.id,
                    indication_id=indication.id,
                    approval_status=True,
                    created_at=datetime.utcnow()
                )
                db.add(drug_indication)
            
            created_drugs += 1
            print(f"✅ Created drug: {drug.generic_name} (Brand: {drug.brand_name or 'N/A'})")
        
        db.commit()
        print(f"🎉 Successfully created {created_drugs} drugs from example data!")
        
        # Show summary
        total_drugs = db.query(Drug).count()
        total_companies = db.query(Company).count()
        print(f"📊 Database now contains {total_drugs} drugs across {total_companies} companies")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error populating database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    populate_from_example()

