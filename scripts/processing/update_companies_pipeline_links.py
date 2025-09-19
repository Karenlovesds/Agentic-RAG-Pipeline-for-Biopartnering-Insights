#!/usr/bin/env python3
"""
Script to update companies.csv with correct, current pipeline links.
"""

import pandas as pd
import os

def update_companies_pipeline_links():
    """Update companies.csv with correct pipeline links."""
    
    # Top 30 Biopharma companies with correct pipeline links (2024)
    companies_data = [
        ("Johnson & Johnson", "https://investor.jnj.com/pipeline/development-pipeline/default.aspx"),
        ("Pfizer", "https://www.pfizer.com/science/drug-product-pipeline"),
        ("Roche/Genentech", "https://www.roche.com/solutions/pipeline"),
        ("Novartis", "https://www.novartis.com/research-development/novartis-pipeline"),
        ("Merck & Co.", "https://www.merck.com/research/development-pipeline/"),
        ("AbbVie", "https://www.abbvie.com/science/pipeline.html"),
        ("Sanofi", "https://www.sanofi.com/en/our-science/our-pipeline"),
        ("Bristol Myers Squibb", "https://www.bms.com/researchers-and-partners/our-pipeline.html"),
        ("AstraZeneca", "https://www.astrazeneca.com/our-science/pipeline.html"),
        ("Eli Lilly", "https://www.lilly.com/science/research-development/pipeline"),
        ("GlaxoSmithKline (GSK)", "https://www.gsk.com/en-gb/research-and-development/our-pipeline/"),
        ("Bayer", "https://www.bayer.com/en/pharma/development-pipeline"),
        ("Amgen", "https://www.amgen.com/science/clinical-trials/pipeline"),
        ("Takeda Pharmaceutical", "https://www.takeda.com/what-we-do/research-and-development/our-pipeline/"),
        ("Boehringer Ingelheim", "https://www.boehringer-ingelheim.com/research-development/our-pipeline"),
        ("Moderna", "https://www.modernatx.com/research/product-pipeline"),
        ("Regeneron Pharmaceuticals", "https://www.regeneron.com/pipeline"),
        ("CSL", "https://www.csl.com/research/pipeline"),
        ("Biogen", "https://www.biogen.com/science-innovation/pipeline.html"),
        ("Vertex Pharmaceuticals", "https://www.vrtx.com/research-development/pipeline/"),
        ("Gilead Sciences", "https://www.gilead.com/research/pipeline"),
        ("Seagen", "https://www.seagen.com/pipeline"),
        ("BeiGene", "https://www.beigene.com/science/pipeline/"),
        ("Incyte", "https://www.incyte.com/our-science/pipeline"),
        ("Alnylam Pharmaceuticals", "https://www.alnylam.com/our-science/pipeline/"),
        ("Daiichi Sankyo", "https://www.daiichisankyo.com/rd/pipeline/"),
        ("Merck KGaA", "https://www.merckgroup.com/en/research/pipeline.html"),
        ("BioNTech", "https://www.biontech.com/our-science/pipeline/"),
        ("Astellas Pharma", "https://www.astellas.com/en/research-development/pipeline"),
        ("Illumina", "https://www.illumina.com/science/technology/pipeline.html"),
    ]
    
    # Create DataFrame
    df = pd.DataFrame(companies_data, columns=["Company", "PipelineURL"])
    
    # Save to CSV
    csv_path = "data/companies.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"✅ Updated companies.csv with correct pipeline links!")
    print(f"📁 Saved to: {csv_path}")
    print(f"📊 Total companies: {len(df)}")
    
    # Show sample of updated links
    print("\n🔗 Sample of updated pipeline links:")
    for i, row in df.head(5).iterrows():
        print(f"  {i+1:2d}. {row['Company']}: {row['PipelineURL']}")
    
    return csv_path

if __name__ == "__main__":
    update_companies_pipeline_links()
