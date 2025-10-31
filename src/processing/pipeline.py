"""Comprehensive processing pipeline: entity extraction, linking, and data management.

This implementation provides:
- Extract companies from the configured list and ensure DB rows exist
- Heuristically create drugs if certain keywords appear in documents
- Link trials to companies by sponsor name containment
- Extract and link targets to drugs
- Deduplicate drugs within companies
- Generate comprehensive CSV exports and summaries
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session
import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

from config.config import get_target_companies
from config.validation_config import GROUND_TRUTH_PATH
from src.models.entities import Company, Drug, ClinicalTrial, Document, Target, DrugTarget, DrugIndication


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


def get_common_drug_keywords_from_ground_truth() -> List[str]:
    """Load all unique drug names (generic + brand) from Ground Truth.
    
    Returns:
        List of unique drug names (lowercased) from Ground Truth.
        Includes both generic and brand names, with compound names split.
        Example: ['pembrolizumab', 'keytruda', 'rg6810', 'gdc-7035', ...]
    """
    drug_names = set()
    
    try:
        df = pd.read_excel(GROUND_TRUTH_PATH, usecols=['Generic name', 'Brand name'])
        
        # Extract generic names (handle compound names like "RG6620 / GDC-7035")
        for name in df['Generic name'].dropna():
            name_str = str(name).strip()
            # Split compound names by "/"
            parts = re.split(r'\s*/\s*', name_str)
            for part in parts:
                part_clean = part.strip()
                if part_clean:
                    drug_names.add(part_clean.lower())
        
        # Extract brand names
        for name in df['Brand name'].dropna():
            name_str = str(name).strip()
            if name_str:
                drug_names.add(name_str.lower())
        
        logger.info(f"Loaded {len(drug_names)} unique drug names from Ground Truth")
    except Exception as e:
        logger.error(f"Failed to load drug keywords from Ground Truth: {e}")
        return []
    
    return sorted(list(drug_names))


def get_unique_seed_targets_from_ground_truth() -> List[str]:
    """Load all unique target names from Ground Truth Excel file.
    
    Returns:
        List of unique target names from Ground Truth.
        Handles formats like "PD-L1", "CD20 x CD3", "KRAS G12D", etc.
        Example: ['PD-L1', 'CD20', 'CD3', 'KRAS G12D', ...]
    """
    targets = set()
    
    try:
        df = pd.read_excel(GROUND_TRUTH_PATH, usecols=['Target'])
        
        # Extract targets from Target column
        for target_string in df['Target'].dropna():
            target_string = str(target_string).strip()
            if target_string:
                # Parse targets (handles "x" separators like "CD20 x CD3")
                target_names = _parse_target_string(target_string)
                for target_name in target_names:
                    target_clean = target_name.strip()
                    if target_clean:
                        targets.add(target_clean)  # Keep original case
        
        logger.info(f"Loaded {len(targets)} unique targets from Ground Truth")
    except Exception as e:
        logger.error(f"Failed to load targets from Ground Truth: {e}")
        return []
    
    return sorted(list(targets))


def ensure_companies(db: Session) -> int:
    count_created = 0
    for name in get_target_companies():
        if not db.query(Company).filter(Company.name == name).first():
            db.add(Company(name=name))
            count_created += 1
    if count_created:
        db.commit()
    return count_created


def seed_drugs_from_ground_truth(db: Session) -> Dict[str, int]:
    """Seed drugs from Ground Truth Excel file with company assignments."""
    logger.info("Seeding drugs from Ground Truth data...")
    
    try:
        # Load Ground Truth data
        usecols = ['Generic name', 'Brand name', 'Company', 'Target', 'Mechanism', 
                   'Drug Class', 'Indication Approved', 'Current Clinical Trials', 'FDA Approval']
        df = pd.read_excel(GROUND_TRUTH_PATH, usecols=usecols)
        logger.info(f"Loaded {len(df)} records from Ground Truth")
    except Exception as e:
        logger.error(f"Failed to load Ground Truth data: {e}")
        return {"drugs_created": 0, "drugs_updated": 0}
    
    # Get company mappings (normalize names for matching)
    companies = db.query(Company).all()
    company_map = {}  # normalized_company_name -> Company.id
    company_name_map = {}  # normalized_company_name -> original_company_name
    
    for company in companies:
        normalized = company.name.lower().strip()
        company_map[normalized] = company.id
        company_name_map[normalized] = company.name
    
    # Company name normalization helper
    def normalize_company_name(name: str) -> str:
        """Normalize company name for matching."""
        if pd.isna(name):
            return ""
        name_lower = str(name).lower().strip()
        # Handle common variations
        name_lower = name_lower.replace("&", "and").replace("/", " ").replace(",", "")
        return " ".join(name_lower.split())
    
    # Enhanced company matching with common aliases
    company_aliases = {
        'roche': ['roche', 'genentech', 'roche/genentech', 'hoffmann-la roche'],
        'merck': ['merck', 'merck & co', 'msd'],
        'pfizer': ['pfizer', 'pfizer laboratories'],
        'jnj': ['jnj', 'johnson & johnson', 'j&j', 'janssen'],
        'bristol myers squibb': ['bristol myers squibb', 'bms', 'bristol-myers'],
        'abbvie': ['abbvie', 'abbvie inc'],
        'eli lilly': ['eli lilly', 'lilly'],
        'novartis': ['novartis', 'novartis ag'],
        'astrazeneca': ['astrazeneca', 'az'],
        'gilead': ['gilead', 'gilead sciences'],
        'amgen': ['amgen', 'amgen inc'],
        'regeneron': ['regeneron', 'regeneron pharmaceuticals'],
        'bayer': ['bayer', 'bayer ag'],
        'takeda': ['takeda', 'takeda pharmaceutical'],
        'daiichi sankyo': ['daiichi sankyo', 'daiichi'],
        'astellas': ['astellas', 'astellas pharma'],
    }
    
    # Build reverse alias lookup
    alias_to_seed = {}
    for seed_name, aliases in company_aliases.items():
        for alias in aliases:
            alias_to_seed[normalize_company_name(alias)] = seed_name
    
    drugs_created = 0
    drugs_updated = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('Generic name')):
            continue
            
        generic_name_full = str(row['Generic name']).strip()
        if not generic_name_full:
            continue
        
        # Handle compound names separated by "/" (e.g., "RG6620 / GDC-7035")
        # Use the first part as primary name, but also create entries for each part
        generic_names = [g.strip() for g in re.split(r'\s*/\s*', generic_name_full)]
        generic_name = generic_names[0]  # Primary name
        
        # Normalize company name and find matching seed company
        company_name_gt = normalize_company_name(row.get('Company', ''))
        company_id = None
        
        # Strategy 1: Check alias mapping
        if company_name_gt in alias_to_seed:
            seed_name = alias_to_seed[company_name_gt]
            seed_normalized = normalize_company_name(seed_name)
            if seed_normalized in company_map:
                company_id = company_map[seed_normalized]
        
        # Strategy 2: Try exact match
        if not company_id and company_name_gt in company_map:
            company_id = company_map[company_name_gt]
        
        # Strategy 3: Try partial matching
        if not company_id:
            for normalized_name, cid in company_map.items():
                # Check if any part matches
                gt_words = set(company_name_gt.split())
                seed_words = set(normalized_name.split())
                if gt_words.intersection(seed_words) or (normalized_name in company_name_gt or company_name_gt in normalized_name):
                    company_id = cid
                    break
        
        # If no company match found, skip (we only use seed companies)
        if not company_id:
            logger.debug(f"Skipping drug {generic_name} - company '{row.get('Company')}' not in seed companies")
            continue
        
        # Check if drug already exists for this company (check all name variants)
        existing_drug = None
        for name_variant in generic_names:
            existing_drug = db.query(Drug).filter(
                Drug.generic_name.ilike(f"%{name_variant}%"),
                Drug.company_id == company_id
            ).first()
            if existing_drug:
                break
        
        if existing_drug:
            # Update existing drug with Ground Truth data
            # Update generic name to include all variants if compound name
            if len(generic_names) > 1:
                existing_drug.generic_name = generic_name_full
            if pd.notna(row.get('Brand name')):
                existing_drug.brand_name = str(row['Brand name']).strip()
            if pd.notna(row.get('Drug Class')):
                existing_drug.drug_class = str(row['Drug Class']).strip()
            if pd.notna(row.get('Mechanism')):
                existing_drug.mechanism_of_action = str(row['Mechanism']).strip()
            if pd.notna(row.get('FDA Approval')):
                existing_drug.fda_approval_status = True
            drugs_updated += 1
            drug = existing_drug
        else:
            # Create new drug from Ground Truth (use full name if compound)
            drug = Drug(
                generic_name=generic_name_full if len(generic_names) > 1 else generic_name,
                brand_name=str(row['Brand name']).strip() if pd.notna(row.get('Brand name')) else None,
                drug_class=str(row['Drug Class']).strip() if pd.notna(row.get('Drug Class')) else None,
                mechanism_of_action=str(row['Mechanism']).strip() if pd.notna(row.get('Mechanism')) else None,
                fda_approval_status=pd.notna(row.get('FDA Approval')),
                fda_approval_date=datetime.utcnow() if pd.notna(row.get('FDA Approval')) else None,
                company_id=company_id,
                created_at=datetime.utcnow()
            )
            db.add(drug)
            db.flush()  # Flush to get drug.id for target relationships
            drugs_created += 1
        
        # Process targets from Ground Truth
        if pd.notna(row.get('Target')):
            target_string = str(row['Target']).strip()
            if target_string:
                # Parse targets (can be single target, multiple with "x", or comma-separated)
                # Handle formats like: "PD-L1", "CD20 x CD3", "KRAS G12D", "FcRH5 x CD3"
                target_names = _parse_target_string(target_string)
                
                for target_name in target_names:
                    # Get or create target entity
                    target = _get_or_create_target(db, target_name, drug.generic_name)
                    
                    # Create drug-target relationship if it doesn't exist
                    existing_rel = db.query(DrugTarget).filter(
                        DrugTarget.drug_id == drug.id,
                        DrugTarget.target_id == target.id
                    ).first()
                    
                    if not existing_rel:
                        drug_target = DrugTarget(
                            drug_id=drug.id,
                            target_id=target.id,
                            relationship_type="targets"  # Default relationship type
                        )
                        db.add(drug_target)
        
        # Process clinical trials from Ground Truth
        if pd.notna(row.get('Current Clinical Trials')):
            trials_string = str(row['Current Clinical Trials']).strip()
            if trials_string:
                # Extract NCT IDs from the trials string
                nct_ids = _parse_nct_ids_from_trials_string(trials_string)
                
                for nct_id in nct_ids:
                    # Get or create clinical trial entity and link to drug/company
                    trial = _get_or_create_clinical_trial(
                        db=db,
                        nct_id=nct_id,
                        drug_id=drug.id,
                        company_id=company_id,
                        title=f"{drug.generic_name} - Clinical Trial"
                    )
    
    if drugs_created > 0 or drugs_updated > 0:
        db.commit()
        logger.info(f"✅ Seeded {drugs_created} drugs and updated {drugs_updated} drugs from Ground Truth")
    
    return {"drugs_created": drugs_created, "drugs_updated": drugs_updated}


def learn_drug_patterns_from_seeds(db: Session) -> Tuple[Set[str], Dict[str, List[str]]]:
    """Learn drug patterns from seeded drugs (names and suffixes/prefixes)."""
    logger.info("Learning drug patterns from seed drugs...")
    
    seed_drugs = db.query(Drug).all()
    seed_drug_names = set()
    patterns = {
        'suffixes': set(),  # -mab, -nib, -cept, etc.
        'prefixes': set(),  # RG, MK-, etc.
        'structures': set()  # Common word structures
    }
    
    for drug in seed_drugs:
        name_lower = drug.generic_name.lower().strip()
        seed_drug_names.add(name_lower)
        
        # Extract suffixes (common drug name endings)
        if name_lower.endswith(('mab', 'zumab', 'ximab', 'umab')):
            patterns['suffixes'].add('mab')
        if name_lower.endswith(('nib', 'tinib', 'cib')):
            patterns['suffixes'].add('nib')
        if name_lower.endswith('cept'):
            patterns['suffixes'].add('cept')
        if name_lower.endswith('leucel'):
            patterns['suffixes'].add('leucel')
        if name_lower.endswith(('vedotin', 'deruxtecan', 'tirumotecan')):
            patterns['suffixes'].add('vedotin')
        
        # Extract prefixes (company codes) - requires numbers after prefix
        # Company-specific drug code prefixes
        prefix_patterns = {
            'rg': r'^rg\d+',      # Roche/Genentech (RG123)
            'mk': r'^mk-\d+',     # Merck (MK-1234)
            'gdc': r'^gdc-\d+',   # Genentech Development (GDC-1234)
            'amg': r'^amg\s*\d+', # Amgen (AMG 123 or AMG123)
            'azd': r'^azd\d+',    # AstraZeneca (AZD1234)
            'bay': r'^bay\s*\d+', # Bayer (BAY 123 or BAY123)
            'abbv': r'^abbv\d+',  # AbbVie (ABBV123)
            'bms': r'^bms-\d+',   # Bristol Myers Squibb (BMS-123)
            'ds': r'^ds-\d+',     # Daiichi Sankyo (DS-123)
            'gs': r'^gs-\d+',     # Gilead Sciences (GS-1234)
            'iov': r'^iov\d+',    # Iovance (IOV123)
            'jnj': r'^jnj\d+',    # Johnson & Johnson (JNJ123)
            'nvl': r'^nvl\d+',    # Nuvalent (NVL123)
            'regn': r'^regn\d+',  # Regeneron (REGN123)
            'pf': r'^pf-\d+',     # Pfizer (PF-1234)
            'a2b': r'^a2b\d+',    # A2 Bio (A2B123)
            'aaa': r'^aaa\d+',    # AAA drugs (AAA601, AAA603)
            'abp': r'^abp\s*\d+', # ABP drugs (ABP 206, ABP 234)
            'asp': r'^asp\d+',    # ASP drugs (ASP1570, ASP2138)
            'ln': r'^ln-\d+',     # LN drugs (LN-144, LN-145)
            'vvd': r'^vvd-\d+',   # VVD drugs (VVD-130037, VVD-214)
            'byl': r'^byl\d+',    # BYL drugs (BYL719)
            'mrna': r'^mrna-\d+', # mRNA- drugs (mRNA-1234)
        }
        
        for prefix_key, pattern in prefix_patterns.items():
            if re.match(pattern, name_lower):
                patterns['prefixes'].add(prefix_key)
    
    logger.info(f"Learned {len(seed_drug_names)} seed drug names and patterns: {patterns}")
    
    # Convert sets to lists for return
    return seed_drug_names, {
        'suffixes': list(patterns['suffixes']),
        'prefixes': list(patterns['prefixes']),
        'structures': list(patterns['structures'])
    }


def _extract_brand_name_from_context(drug_name: str, text: str, match_position: int) -> Optional[str]:
    """Extract brand name from text context around a drug mention.
    
    Looks for brand names in common patterns:
    - "pembrolizumab (KEYTRUDA)"
    - "KEYTRUDA (pembrolizumab)"
    - "pembrolizumab, brand name: KEYTRUDA"
    - "pembrolizumab (also known as KEYTRUDA)"
    
    Args:
        drug_name: The generic drug name that was found
        text: The full document text
        match_position: Character position where drug_name was found
        
    Returns:
        Extracted brand name or None if not found
    """
    # Get context around the drug mention (200 chars before and after)
    start = max(0, match_position - 200)
    end = min(len(text), match_position + len(drug_name) + 200)
    context = text[start:end]
    
    drug_name_escaped = re.escape(drug_name)
    
    # Pattern 1: "generic_name (BRAND)"
    pattern1 = rf'{drug_name_escaped}\s*\(([A-Z][A-Za-z0-9\s-]+)\)'
    match1 = re.search(pattern1, context, re.IGNORECASE)
    if match1:
        brand = match1.group(1).strip()
        # Validate it looks like a brand name (must start with uppercase and be >=5 characters)
        if len(brand) >= 5 and brand[0].isupper():
            return brand
    
    # Pattern 2: "BRAND (generic_name)"
    pattern2 = rf'\(([A-Z][A-Za-z0-9\s-]+)\)\s*{drug_name_escaped}|([A-Z][A-Za-z0-9\s-]+)\s*\({drug_name_escaped}'
    match2 = re.search(pattern2, context, re.IGNORECASE)
    if match2:
        brand = (match2.group(1) or match2.group(2)).strip()
        if len(brand) >= 5 and brand[0].isupper() and brand.upper() != drug_name.upper():
            return brand
    
    # Pattern 3: "generic_name, brand name: BRAND" or "brand name: BRAND"
    pattern3 = rf'(?:{drug_name_escaped}[,\s]+)?(?:brand name|trademark|commercially known as)[:\s]+([A-Z][A-Za-z0-9\s-]+)'
    match3 = re.search(pattern3, context, re.IGNORECASE)
    if match3:
        brand = match3.group(1).strip()
        if len(brand) >= 5 and brand[0].isupper():
            return brand
    
    # Pattern 4: "generic_name, also known as BRAND" or "BRAND, also known as generic_name"
    pattern4 = rf'(?:{drug_name_escaped}[,\s]+)?(?:also known as|aka|a\.k\.a\.)[:\s]+([A-Z][A-Za-z0-9\s-]+)'
    match4 = re.search(pattern4, context, re.IGNORECASE)
    if match4:
        brand = match4.group(1).strip()
        if len(brand) >= 5 and brand[0].isupper() and brand.upper() != drug_name.upper():
            return brand
    
    return None


def _extract_mechanism_from_context(drug_name: str, text: str, match_position: int) -> Optional[str]:
    """Extract mechanism of action from text context around a drug mention.
    
    Looks for mechanism descriptions using common patterns:
    - "pembrolizumab inhibits PD-1"
    - "drug blocks HER2 signaling"
    - "drug targets KRAS G12C"
    - "drug binds to PD-L1"
    
    Args:
        drug_name: The generic drug name that was found
        text: The full document text
        match_position: Character position where drug_name was found
        
    Returns:
        Extracted mechanism description or None if not found
    """
    # Get context around the drug mention (300 chars before and after for mechanism)
    start = max(0, match_position - 300)
    end = min(len(text), match_position + len(drug_name) + 300)
    context = text[start:end]
    
    drug_name_escaped = re.escape(drug_name)
    drug_name_lower = drug_name.lower()
    
    # Look for mechanism patterns near the drug name
    # Pattern 1: "drug inhibits X" or "drug blocks X"
    pattern1 = rf'{drug_name_escaped}\s+(?:inhibits?|blocks?|targets?|binds?\s+to)\s+([A-Z][^.]{{10,150}})'
    match1 = re.search(pattern1, context, re.IGNORECASE)
    if match1:
        mechanism = match1.group(1).strip()
        # Clean up and validate
        mechanism = re.sub(r'\s+', ' ', mechanism)  # Normalize whitespace
        if len(mechanism) >= 10 and len(mechanism) <= 200:  # Reasonable length
            return mechanism
    
    # Pattern 2: "inhibits X" or "blocks X" within 50 chars after drug name
    pattern2 = r'(?:inhibits?|blocks?|targets?|binds?\s+to)\s+([A-Z][^.]{10,150})'
    drug_pos_in_context = context.lower().find(drug_name_lower)
    if drug_pos_in_context != -1:
        # Look for mechanism in the text after the drug mention
        after_drug = context[drug_pos_in_context + len(drug_name):drug_pos_in_context + len(drug_name) + 200]
        match2 = re.search(pattern2, after_drug, re.IGNORECASE)
        if match2:
            mechanism = match2.group(1).strip()
            mechanism = re.sub(r'\s+', ' ', mechanism)
            if len(mechanism) >= 10 and len(mechanism) <= 200:
                return mechanism
    
    # Pattern 3: Look for sentences containing both drug name and mechanism keywords
    sentences = re.split(r'[.!?]\s+', context)
    for sentence in sentences:
        if drug_name_lower in sentence.lower():
            # Check if sentence contains mechanism keywords
            mechanism_keywords = ['inhibits', 'blocks', 'targets', 'binds to', 'activates', 'modulates', 
                                 'antibody', 'inhibitor', 'antagonist', 'agonist', 'monoclonal']
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in mechanism_keywords):
                # Extract relevant part (limit length)
                mechanism = sentence.strip()
                # Try to extract just the mechanism part
                if len(mechanism) > 200:
                    # Try to find mechanism keywords and extract from there
                    for keyword in mechanism_keywords:
                        if keyword in mechanism.lower():
                            idx = mechanism.lower().find(keyword)
                            mechanism = mechanism[idx:idx+200].strip()
                            break
                if 10 <= len(mechanism) <= 300:
                    mechanism = re.sub(r'\s+', ' ', mechanism)
                    return mechanism
    
    return None


def _infer_drug_class_from_name(drug_name: str) -> Optional[str]:
    """Infer drug class from drug name using suffix/prefix patterns.
    
    Args:
        drug_name: Drug name to analyze
        
    Returns:
        Inferred drug class or None if unable to determine
    """
    name_lower = drug_name.lower()
    
    # Define drug class mappings based on suffixes and patterns
    # Monoclonal Antibodies
    if any(name_lower.endswith(suffix) for suffix in ['mab', 'zumab', 'ximab', 'umab', 'omab']):
        return "Monoclonal Antibody"
    
    # Small Molecule Kinase Inhibitors
    if any(name_lower.endswith(suffix) for suffix in ['nib', 'tinib', 'cib', 'lib']):
        return "Small Molecule"
    
    # ADCs (Antibody-Drug Conjugates)
    if any(pattern in name_lower for pattern in ['deruxtecan', 'vedotin', 'tirumotecan']):
        return "ADC"
    
    # CAR-T and Cell Therapies
    if any(pattern in name_lower for pattern in ['leucel', 'tucel', 'cabtagene']):
        return "Cell Therapy"
    
    # Fusion Proteins
    if name_lower.endswith('cept'):
        return "Fusion Protein"
    
    # Company code prefixes that are typically small molecules
    if any(name_lower.startswith(prefix) for prefix in ['mk-', 'rg', 'azd', 'bay', 'byl']):
        # Check if it's a company code pattern (typically followed by numbers)
        import re
        if re.match(r'^(mk-|rg|azd|bay|byl)\d+', name_lower):
            return "Small Molecule"
    
    # mRNA vaccines
    if name_lower.startswith('mrna-'):
        return "mRNA"
    
    # Default to None if unable to infer
    return None


def extract_drugs_from_documents(db: Session, batch_size: int = 100) -> int:
    """Extract drugs from documents using seed drugs and learned patterns.
    
    Uses a three-tier approach for comprehensive drug extraction:
    1. Exact drug names: Ground Truth keywords (324+ unique drug names) + DB seeds
    2. Learned suffix patterns: Dynamically learned from seed drugs (e.g., -mab, -nib, -cept)
    3. Learned prefix patterns: Company drug codes (e.g., RG123, MK-3475, AMG 193)
    
    This combination ensures:
    - All known drugs from Ground Truth are matched exactly
    - New drugs following known patterns are discovered (e.g., "newdrugimab")
    - Company drug codes are recognized (e.g., "RG9999", "MK-9999")
    """
    created = 0
    
    # Step 1: Get seed drug names and learned patterns from database
    # This learns patterns (suffixes/prefixes) from drugs already seeded from Ground Truth
    seed_drug_names, patterns = learn_drug_patterns_from_seeds(db)
    
    # Step 2: Get all drug keywords directly from Ground Truth (source of truth)
    # This ensures we catch all 324+ drugs even if not yet seeded in DB
    ground_truth_keywords = set(get_common_drug_keywords_from_ground_truth())
    
    # Step 3: Combine exact drug names from both sources
    # The seed_drug_names from DB should be a subset of Ground Truth
    all_drug_keywords = seed_drug_names.union(ground_truth_keywords)
    logger.info(f"📊 Drug extraction setup:")
    logger.info(f"   - Exact drug names: {len(all_drug_keywords)} total ({len(seed_drug_names)} from DB + {len(ground_truth_keywords)} from Ground Truth)")
    logger.info(f"   - Learned patterns: {patterns}")
    
    # Load Ground Truth for company matching (handle compound names like "RG6620 / GDC-7035")
    ground_truth_drugs = {}
    try:
        df = pd.read_excel(GROUND_TRUTH_PATH, usecols=['Generic name', 'Company'])
        for _, row in df.iterrows():
            if pd.notna(row.get('Generic name')) and pd.notna(row.get('Company')):
                generic_name_full = str(row['Generic name']).strip()
                company_name = str(row['Company']).strip()
                
                # Handle compound names separated by "/" or " / "
                drug_names = re.split(r'\s*/\s*', generic_name_full)
                for drug_name_part in drug_names:
                    drug_name_clean = drug_name_part.strip().lower()
                    if drug_name_clean:
                        ground_truth_drugs[drug_name_clean] = company_name
                        # Also store the full name
                        ground_truth_drugs[generic_name_full.lower()] = company_name
    except Exception as e:
        logger.warning(f"Could not load Ground Truth for company matching: {e}")
    
    # Get company mappings
    companies = db.query(Company).all()
    company_map = {c.name.lower().strip(): c.id for c in companies}
    company_id_map = {c.id: c.name for c in companies}
    
    # Helper to normalize company name
    def normalize_company_name(name: str) -> str:
        name_lower = str(name).lower().strip()
        name_lower = name_lower.replace("&", "and").replace("/", " ").replace(",", "")
        return " ".join(name_lower.split())
    
    # Company aliases (same as in seed_drugs_from_ground_truth)
    company_aliases = {
        'roche': ['roche', 'genentech', 'roche/genentech', 'hoffmann-la roche'],
        'merck': ['merck', 'merck & co', 'msd'],
        'pfizer': ['pfizer', 'pfizer laboratories'],
        'jnj': ['jnj', 'johnson & johnson', 'j&j', 'janssen'],
        'bristol myers squibb': ['bristol myers squibb', 'bms', 'bristol-myers'],
        'abbvie': ['abbvie', 'abbvie inc'],
        'eli lilly': ['eli lilly', 'lilly'],
        'novartis': ['novartis', 'novartis ag'],
        'astrazeneca': ['astrazeneca', 'az'],
        'gilead': ['gilead', 'gilead sciences'],
        'amgen': ['amgen', 'amgen inc'],
        'regeneron': ['regeneron', 'regeneron pharmaceuticals'],
        'bayer': ['bayer', 'bayer ag'],
        'takeda': ['takeda', 'takeda pharmaceutical'],
        'daiichi sankyo': ['daiichi sankyo', 'daiichi'],
        'astellas': ['astellas', 'astellas pharma'],
    }
    
    # Build reverse alias lookup
    alias_to_seed = {}
    for seed_name, aliases in company_aliases.items():
        for alias in aliases:
            alias_to_seed[normalize_company_name(alias)] = seed_name
    
    # Helper to find company ID from name (using aliases)
    def find_company_id(company_name: str) -> int:
        normalized = normalize_company_name(company_name)
        
        # Strategy 1: Check alias mapping
        if normalized in alias_to_seed:
            seed_name = alias_to_seed[normalized]
            seed_normalized = normalize_company_name(seed_name)
            if seed_normalized in company_map:
                return company_map[seed_normalized]
        
        # Strategy 2: Try exact match
        if normalized in company_map:
            return company_map[normalized]
        
        # Strategy 3: Try partial matching
        for cname, cid in company_map.items():
            gt_words = set(normalized.split())
            seed_words = set(cname.split())
            if gt_words.intersection(seed_words) or (normalized in cname or cname in normalized):
                return cid
        
        return None
    
    # Get total count for progress tracking
    total_docs = db.query(Document).count()
    logger.info(f"Processing {total_docs} documents in batches of {batch_size}")
    logger.info(f"Using {len(all_drug_keywords)} total drug keywords and patterns: {patterns}")
    
    # Build regex patterns for drug extraction
    drug_patterns = []
    
    # Pattern 1: Exact drug names from Ground Truth (with word boundaries)
    # Use the comprehensive Ground Truth list for better coverage
    for drug_name in all_drug_keywords:
        # Escape special characters and add word boundaries
        escaped = re.escape(drug_name)
        drug_patterns.append((rf'\b{escaped}\b', 'seed', drug_name))
    
    # Pattern 2: Learned suffix patterns (e.g., -mab, -nib, -cept)
    for suffix in patterns.get('suffixes', []):
        if suffix == 'mab':
            drug_patterns.append((r'\b([A-Za-z]+(?:mab|zumab|ximab|umab))\b', 'suffix', suffix))
        elif suffix == 'nib':
            drug_patterns.append((r'\b([A-Za-z]+(?:nib|tinib|cib))\b', 'suffix', suffix))
        elif suffix == 'cept':
            drug_patterns.append((r'\b([A-Za-z]+cept)\b', 'suffix', suffix))
        elif suffix == 'leucel':
            drug_patterns.append((r'\b([A-Za-z]+leucel)\b', 'suffix', suffix))
        elif suffix == 'vedotin':
            drug_patterns.append((r'\b([A-Za-z]+(?:vedotin|deruxtecan|tirumotecan))\b', 'suffix', suffix))
    
    # Pattern 3: Learned prefix patterns (company drug codes with numbers)
    # Note: Requiring numbers prevents false positives from generic abbreviations
    prefix_patterns_map = {
        'rg': r'\b(RG\d+[A-Za-z0-9]*)\b',
        'mk': r'\b(MK-\d+[A-Za-z0-9]*)\b',
        'gdc': r'\b(GDC-\d+[A-Za-z0-9]*)\b',
        'amg': r'\b(AMG\s*\d+[A-Za-z0-9]*)\b',
        'azd': r'\b(AZD\d+[A-Za-z0-9]*)\b',
        'bay': r'\b(BAY\s*\d+[A-Za-z0-9]*)\b',
        'abbv': r'\b(ABBV\d+[A-Za-z0-9]*)\b',
        'bms': r'\b(BMS-\d+[A-Za-z0-9]*)\b',
        'ds': r'\b(DS-\d+[A-Za-z0-9]*)\b',
        'gs': r'\b(GS-\d+[A-Za-z0-9]*)\b',
        'iov': r'\b(IOV\d+[A-Za-z0-9]*)\b',
        'jnj': r'\b(JNJ\d+[A-Za-z0-9]*)\b',
        'nvl': r'\b(NVL\d+[A-Za-z0-9]*)\b',
        'regn': r'\b(REGN\d+[A-Za-z0-9]*)\b',
        'pf': r'\b(PF-\d+[A-Za-z0-9]*)\b',
        'a2b': r'\b(A2B\d+[A-Za-z0-9]*)\b',
        'aaa': r'\b(AAA\d+[A-Za-z0-9]*)\b',    # AAA601, AAA603
        'abp': r'\b(ABP\s*\d+[A-Za-z0-9]*)\b',  # ABP 206, ABP 234
        'asp': r'\b(ASP\d+[A-Za-z0-9]*)\b',     # ASP1570, ASP2138
        'ln': r'\b(LN-\d+[A-Za-z0-9-]*)\b',     # LN-144, LN-145-S1
        'vvd': r'\b(VVD-\d+[A-Za-z0-9]*)\b',    # VVD-130037, VVD-214
        'byl': r'\b(BYL\d+[A-Za-z0-9]*)\b',     # BYL719
        'mrna': r'\b(mRNA-\d+[A-Za-z0-9]*)\b',  # mRNA-1234
    }
    
    for prefix in patterns.get('prefixes', []):
        if prefix in prefix_patterns_map:
            drug_patterns.append((prefix_patterns_map[prefix], 'prefix', prefix))
    
    # Process documents in batches
    offset = 0
    while offset < total_docs:
        docs = db.query(Document).offset(offset).limit(batch_size).all()
        if not docs:
            break
            
        logger.info(f"Processing batch {offset//batch_size + 1}: documents {offset+1}-{min(offset+batch_size, total_docs)}")
        
        for doc in docs:
            text = doc.content or ""
            text_lower = text.lower()
            found_drugs = set()  # (drug_name_lower, drug_name_clean, company_id, brand_name, mechanism)
            
            # Extract drugs using all patterns
            for pattern, pattern_type, pattern_value in drug_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    drug_name = match.group(1) if match.groups() else match.group(0)
                    drug_name_clean = drug_name.strip()
                    drug_name_lower = drug_name_clean.lower()
                    match_position = match.start()  # Position where drug was found
                    
                    # Skip if already found or too short
                    if len(drug_name_clean) < 3 or len(drug_name_clean) > 100:
                        continue
                    
                    # Extract brand name from context around this drug mention
                    brand_name = _extract_brand_name_from_context(drug_name_clean, text, match_position)
                    
                    # Extract mechanism of action from context around this drug mention
                    mechanism = _extract_mechanism_from_context(drug_name_clean, text, match_position)
                    
                    # Determine company assignment
                    company_id = None
                    
                    # Priority 1: Use Ground Truth company if available
                    if drug_name_lower in ground_truth_drugs:
                        gt_company = ground_truth_drugs[drug_name_lower]
                        company_id = find_company_id(gt_company)
                    
                    # Priority 2: Use company from document title/URL
                    if not company_id:
                        for cname, cid in company_map.items():
                            if (doc.title and cname in doc.title.lower()) or cname in doc.source_url.lower():
                                company_id = cid
                                break
                    
                    # Priority 3: Use first seed company as default (only for seed drugs)
                    if not company_id and pattern_type == 'seed':
                        company_id = list(company_map.values())[0] if company_map else None
                    
                    if company_id:
                        found_drugs.add((drug_name_lower, drug_name_clean, company_id, brand_name, mechanism))
            
            # Create drug entities for found drugs
            for drug_tuple in found_drugs:
                # Unpack tuple (handle backwards compatibility: 3-tuple, 4-tuple with brand, 5-tuple with brand+mechanism)
                if len(drug_tuple) == 5:
                    drug_name_lower, drug_name_clean, company_id, brand_name, mechanism = drug_tuple
                elif len(drug_tuple) == 4:
                    drug_name_lower, drug_name_clean, company_id, brand_name = drug_tuple
                    mechanism = None
                else:
                    drug_name_lower, drug_name_clean, company_id = drug_tuple
                    brand_name = None
                    mechanism = None
                
                # Check if this drug-company combination already exists
                existing_drug = db.query(Drug).filter(
                    Drug.generic_name.ilike(f"%{drug_name_clean}%"),
                    Drug.company_id == company_id
                ).first()
                
                if not existing_drug:
                    # Infer drug class from name
                    inferred_drug_class = _infer_drug_class_from_name(drug_name_clean)
                    
                    db.add(Drug(
                        generic_name=drug_name_clean,
                        brand_name=brand_name,  # Add extracted brand name
                        company_id=company_id,
                        drug_class=inferred_drug_class,  # Add inferred drug class
                        mechanism_of_action=mechanism,  # Add extracted mechanism of action
                        created_at=datetime.utcnow()
                    ))
                    created += 1
        
        # Commit batch and clear memory
        if created > 0:
            db.commit()
            logger.info(f"Created {created} drugs in this batch")
        
        offset += batch_size
    
    logger.info(f"Total drugs created from documents: {created}")
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


def extract_targets_from_documents(db: Session, batch_size: int = 100) -> int:
    """Extract targets from documents, create target entities, and link to drugs.
    
    This function:
    1. Searches documents for targets using COMMON_TARGETS (includes Ground Truth targets)
    2. Creates Target entities when found
    3. Links targets to drugs mentioned in the same document
    """
    targets_created = 0
    relationships_created = 0
    
    # Get total count for progress tracking
    total_docs = db.query(Document).count()
    logger.info(f"Processing {total_docs} documents for target extraction in batches of {batch_size}")
    
    # Load all drug names for matching (from database and Ground Truth)
    all_drugs = db.query(Drug).all()
    drug_name_to_drug = {}  # drug_name_lower -> Drug object
    for drug in all_drugs:
        drug_name_lower = drug.generic_name.lower().strip()
        drug_name_to_drug[drug_name_lower] = drug
        if drug.brand_name:
            brand_lower = drug.brand_name.lower().strip()
            drug_name_to_drug[brand_lower] = drug
    
    # Also get Ground Truth drug keywords for matching
    ground_truth_keywords = set(get_common_drug_keywords_from_ground_truth())
    
    # Process documents in batches
    offset = 0
    while offset < total_docs:
        docs = db.query(Document).offset(offset).limit(batch_size).all()
        if not docs:
            break
            
        logger.info(f"Processing batch {offset//batch_size + 1}: documents {offset+1}-{min(offset+batch_size, total_docs)}")
        
        for doc in docs:
            content = doc.content or ""
            content_lower = content.lower()
            found_targets = set()
            
            # Step 1: Look for targets in the content using COMMON_TARGETS
            # (COMMON_TARGETS includes hardcoded + Ground Truth targets added by backfill_drug_targets)
            for target in COMMON_TARGETS:
                # Case-insensitive search with word boundaries
                pattern = r'\b' + re.escape(target) + r'\b'
                if re.search(pattern, content, re.IGNORECASE):
                    found_targets.add(target)
            
            # Step 2: Find drugs mentioned in this document
            drugs_in_doc = []
            for drug_name, drug_obj in drug_name_to_drug.items():
                # Search for drug name in document content
                if len(drug_name) >= 3 and drug_name in content_lower:
                    # Use word boundaries for more precise matching
                    pattern = r'\b' + re.escape(drug_name) + r'\b'
                    if re.search(pattern, content_lower):
                        drugs_in_doc.append(drug_obj)
            
            # Also check Ground Truth keywords
            for drug_keyword in ground_truth_keywords:
                if len(drug_keyword) >= 3 and drug_keyword in content_lower:
                    pattern = r'\b' + re.escape(drug_keyword) + r'\b'
                    if re.search(pattern, content_lower):
                        # Try to find matching drug in database
                        matching_drug = db.query(Drug).filter(
                            Drug.generic_name.ilike(f"%{drug_keyword}%")
                        ).first()
                        if matching_drug and matching_drug not in drugs_in_doc:
                            drugs_in_doc.append(matching_drug)
            
            # Step 3: Create target entities and link to drugs found in document
            for target_name in found_targets:
                # Get or create target entity
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
                    db.flush()  # Get target.id
                    targets_created += 1
                    existing_target = target
                
                # Step 4: Link targets to drugs mentioned in the same document
                for drug in drugs_in_doc:
                    # Check if relationship already exists
                    existing_rel = db.query(DrugTarget).filter(
                        DrugTarget.drug_id == drug.id,
                        DrugTarget.target_id == existing_target.id
                    ).first()
                    
                    if not existing_rel:
                        drug_target = DrugTarget(
                            drug_id=drug.id,
                            target_id=existing_target.id,
                            relationship_type="targets"  # Default relationship type
                        )
                        db.add(drug_target)
                        relationships_created += 1
        
        # Commit batch and clear memory
        if targets_created > 0 or relationships_created > 0:
            db.commit()
            logger.info(f"Created {targets_created} targets and {relationships_created} drug-target relationships in this batch")
        
        offset += batch_size
    
    logger.info(f"Total targets created: {targets_created}, relationships created: {relationships_created}")
    return targets_created


def backfill_drug_targets(db: Session) -> int:
    """Backfill drug-target relationships for existing drugs.
    
    Uses multiple sources:
    1. Hardcoded DRUG_TARGET_MAPPING
    2. Ground Truth Excel file (Primary source)
    3. COMMON_TARGETS list for unique targets
    """
    relationships_created = 0
    
    # Load Ground Truth data for targets
    ground_truth_targets = {}
    ground_truth_target_list = set()  # Unique targets from Ground Truth
    
    try:
        df = pd.read_excel(GROUND_TRUTH_PATH, usecols=['Generic name', 'Target'])
        for _, row in df.iterrows():
            if pd.notna(row.get('Generic name')) and pd.notna(row.get('Target')):
                generic_name_full = str(row['Generic name']).strip()
                target_string = str(row['Target']).strip()
                
                # Parse targets (handles "x" separators)
                target_names = _parse_target_string(target_string)
                
                # Handle compound names (e.g., "RG6620 / GDC-7035")
                generic_names = re.split(r'\s*/\s*', generic_name_full)
                for generic_name_part in generic_names:
                    generic_name_clean = generic_name_part.strip().lower()
                    if generic_name_clean:
                        ground_truth_targets[generic_name_clean] = target_names
                        # Also store full name
                        ground_truth_targets[generic_name_full.lower()] = target_names
                
                # Add unique targets to list
                for target_name in target_names:
                    ground_truth_target_list.add(target_name.strip())
        
        logger.info(f"Loaded {len(ground_truth_targets)} drug-target mappings from Ground Truth")
        logger.info(f"Found {len(ground_truth_target_list)} unique targets in Ground Truth")
    except Exception as e:
        logger.warning(f"Could not load Ground Truth for target backfilling: {e}")
    
    # Add unique Ground Truth targets to COMMON_TARGETS (for document extraction)
    # This ensures targets from Ground Truth are also searched in documents
    for target_name in ground_truth_target_list:
        if target_name and target_name not in COMMON_TARGETS:
            COMMON_TARGETS.append(target_name)
    
    # Get all drugs
    drugs = db.query(Drug).all()
    
    for drug in drugs:
        drug_name = drug.generic_name.lower()
        drug_name_variants = [
            drug_name,
            drug.generic_name.lower(),  # Original case
            drug.generic_name.strip().lower()  # Without extra spaces
        ]
        
        # Strategy 1: Use Ground Truth targets (highest priority)
        target_names = None
        source = None
        
        # Try to find in Ground Truth (check all name variants)
        for variant in drug_name_variants:
            if variant in ground_truth_targets:
                target_names = ground_truth_targets[variant]
                source = "Ground Truth"
                break
        
        # Strategy 2: Use hardcoded mapping if not in Ground Truth
        if not target_names and drug_name in DRUG_TARGET_MAPPING:
            target_names = DRUG_TARGET_MAPPING[drug_name]
            source = "hardcoded mapping"
        
        # Create targets and relationships
        if target_names:
            for target_name in target_names:
                # Find or create target
                target = _get_or_create_target(
                    db, 
                    target_name, 
                    drug.generic_name,
                    description=f"Target for {drug.generic_name} (from {source})"
                )
                
                # Check if relationship already exists
                existing_rel = db.query(DrugTarget).filter(
                    DrugTarget.drug_id == drug.id,
                    DrugTarget.target_id == target.id
                ).first()
                
                if not existing_rel:
                    drug_target = DrugTarget(
                        drug_id=drug.id,
                        target_id=target.id,
                        relationship_type="targets"  # Default relationship
                    )
                    db.add(drug_target)
                    relationships_created += 1
    
    if relationships_created:
        db.commit()
        logger.info(f"✅ Created {relationships_created} drug-target relationships from backfill")
    
    return relationships_created


def extract_targets_from_drug_names(db: Session) -> int:
    """Extract targets from drug names using pattern matching."""
    targets_created = 0
    drugs = db.query(Drug).all()
    
    for drug in drugs:
        drug_name = drug.generic_name.lower()
        found_targets = _extract_targets_from_drug_name(drug_name)
        
        # Create targets and relationships
        targets_created += _create_targets_and_relationships(db, drug, found_targets)
    
    if targets_created:
        db.commit()
    
    return targets_created


def _extract_targets_from_drug_name(drug_name: str) -> set:
    """Extract target names from drug name using pattern matching."""
    found_targets = set()
    
    # Monoclonal antibodies
    if drug_name.endswith('mab'):
        found_targets.update(_extract_mab_targets(drug_name))
    
    # Kinase inhibitors
    elif drug_name.endswith('nib'):
        found_targets.update(_extract_nib_targets(drug_name))
    
    return found_targets


def _extract_mab_targets(drug_name: str) -> set:
    """Extract targets for monoclonal antibodies using a mapping approach."""
    # Drug keyword to targets mapping
    drug_target_mapping = {
        # PD-1 inhibitors
        'pembro': ['PD-1'],
        'keytruda': ['PD-1'],
        'nivo': ['PD-1'],
        'opdivo': ['PD-1'],
        
        # HER2 inhibitors
        'trastu': ['HER2'],
        'herceptin': ['HER2'],
        
        # VEGF inhibitors
        'bevaci': ['VEGF'],
        'avastin': ['VEGF'],
        
        # CD20 inhibitors
        'rituxi': ['CD20'],
        'rituxan': ['CD20'],
        
        # CTLA-4 inhibitors
        'ipili': ['CTLA-4'],
        'yervoy': ['CTLA-4'],
        
        # PD-L1 inhibitors
        'atezo': ['PD-L1'],
        'tecentriq': ['PD-L1'],
        'durva': ['PD-L1'],
        'imfinzi': ['PD-L1'],
        'avelu': ['PD-L1'],
        'bavencio': ['PD-L1'],
    }
    
    targets = set()
    
    # Check each keyword in the drug name
    for keyword, target_list in drug_target_mapping.items():
        if keyword in drug_name:
            targets.update(target_list)
            break  # Only match the first found keyword
    
    return targets


def _extract_nib_targets(drug_name: str) -> set:
    """Extract targets for kinase inhibitors using a mapping approach."""
    # Drug keyword to targets mapping
    drug_target_mapping = {
        # CDK4/6 inhibitors
        'palbo': ['CDK4', 'CDK6'],
        'ibrance': ['CDK4', 'CDK6'],
        'ribo': ['CDK4', 'CDK6'],
        'kisqali': ['CDK4', 'CDK6'],
        'abema': ['CDK4', 'CDK6'],
        'verzenio': ['CDK4', 'CDK6'],
        
        # PARP inhibitors
        'olapa': ['PARP'],
        'lynparza': ['PARP'],
        'ruca': ['PARP'],
        'rubraca': ['PARP'],
        'nira': ['PARP'],
        'zejula': ['PARP'],
        'tala': ['PARP'],
        'talzenna': ['PARP'],
        
        # BCR-ABL/SRC inhibitors
        'dasa': ['BCR-ABL', 'SRC'],
        'sprycel': ['BCR-ABL', 'SRC'],
        
        # ALK/ROS1/MET inhibitors
        'crizo': ['ALK', 'ROS1', 'MET'],
        'xalkori': ['ALK', 'ROS1', 'MET'],
        
        # ALK inhibitors
        'alec': ['ALK'],
        'alecensa': ['ALK'],
        'ceri': ['ALK'],
        'zykadia': ['ALK'],
        'lorla': ['ALK'],
        'lorviqua': ['ALK'],
    }
    
    targets = set()
    
    # Check each keyword in the drug name
    for keyword, target_list in drug_target_mapping.items():
        if keyword in drug_name:
            targets.update(target_list)
            break  # Only match the first found keyword
    
    return targets


def _create_targets_and_relationships(db: Session, drug: Drug, found_targets: set) -> int:
    """Create target entities and drug-target relationships."""
    targets_created = 0
    
    for target_name in found_targets:
        target = _get_or_create_target(db, target_name, drug.generic_name)
        if target:
            targets_created += 1
        
        _create_drug_target_relationship(db, drug, target)
    
    return targets_created


def _parse_nct_ids_from_trials_string(trials_string: str) -> List[str]:
    """Parse NCT IDs from Current Clinical Trials string.
    
    Handles formats like:
    - "NCT01234567"
    - "NCT01234567, NCT01234568"
    - "NCT01234567; NCT01234568"
    - "NCT01234567 | NCT01234568"
    - "NCT01234567 / NCT01234568"
    
    Args:
        trials_string: String containing clinical trial information
        
    Returns:
        List of NCT IDs found in the string
    """
    # Pattern to match NCT IDs (NCT followed by 8 digits)
    nct_pattern = r"NCT\d{8}"
    nct_ids = re.findall(nct_pattern, trials_string.upper())
    
    # Remove duplicates while preserving order
    seen = set()
    unique_nct_ids = []
    for nct_id in nct_ids:
        if nct_id not in seen:
            seen.add(nct_id)
            unique_nct_ids.append(nct_id)
    
    return unique_nct_ids


def _get_or_create_clinical_trial(db: Session, nct_id: str, drug_id: int = None, company_id: int = None, title: str = None) -> ClinicalTrial:
    """Get existing clinical trial or create new one from Ground Truth.
    
    Args:
        db: Database session
        nct_id: NCT identifier (required)
        drug_id: Drug ID to link to (optional)
        company_id: Company ID (sponsor) to link to (optional)
        title: Trial title (optional)
        
    Returns:
        ClinicalTrial entity
    """
    # Try to find existing trial by NCT ID
    trial = db.query(ClinicalTrial).filter(
        ClinicalTrial.nct_id == nct_id
    ).first()
    
    if not trial:
        # Create new trial entity
        trial = ClinicalTrial(
            nct_id=nct_id,
            title=title or f"Clinical Trial {nct_id}",
            drug_id=drug_id,
            sponsor_id=company_id,
            status="unknown",  # Will be updated when more info is available
            created_at=datetime.utcnow()
        )
        db.add(trial)
        db.flush()
        logger.debug(f"Created clinical trial entity: {nct_id}")
    else:
        # Update existing trial if drug_id or company_id provided
        if drug_id and not trial.drug_id:
            trial.drug_id = drug_id
        if company_id and not trial.sponsor_id:
            trial.sponsor_id = company_id
        if title and (not trial.title or trial.title == f"Clinical Trial {nct_id}"):
            trial.title = title
    
    return trial


def _parse_target_string(target_string: str) -> List[str]:
    """Parse target string into list of target names.
    
    Handles formats like:
    - "PD-L1" → ["PD-L1"]
    - "CD20 x CD3" → ["CD20", "CD3"]
    - "KRAS G12D" → ["KRAS G12D"]
    - "FcRH5 x CD3" → ["FcRH5", "CD3"]
    - "DLL3 x CD3 x CD137" → ["DLL3", "CD3", "CD137"]
    """
    # Split by " x " (space-x-space) to handle multiple targets
    targets = []
    parts = re.split(r'\s+x\s+', target_string, flags=re.IGNORECASE)
    
    for part in parts:
        part = part.strip()
        if part:
            targets.append(part)
    
    return targets


def _get_or_create_target(db: Session, target_name: str, drug_name: str = None, description: str = None) -> Target:
    """Get existing target or create new one."""
    # Clean target name
    target_name_clean = target_name.strip()
    
    # Try exact match first
    target = db.query(Target).filter(
        Target.name.ilike(f"%{target_name_clean}%")
    ).first()
    
    if not target:
        # Use provided description or default
        if not description:
            if drug_name:
                description = f"Target from Ground Truth for {drug_name}"
            else:
                description = "Target from Ground Truth"
        
        target = Target(
            name=target_name_clean,
            target_type="protein",
            description=description
        )
        db.add(target)
        db.flush()
    
    return target


def _create_drug_target_relationship(db: Session, drug: Drug, target: Target) -> None:
    """Create drug-target relationship if it doesn't exist."""
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
        from .csv_export import export_drug_table
        
        # Generate the main biopharma drugs CSV (single canonical export)
        biopharma_csv = export_drug_table(db, "outputs/biopharma_drugs.csv")
        
        # Generate drug collection summary
        summary_content = generate_drug_summary(db)
        with open("outputs/drug_collection_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary_content)
        
        logger.info("✅ CSV exports generated successfully")
        return {
            "biopharma_drugs_csv": biopharma_csv,
            "basic_export_csv": biopharma_csv,  # basic export replaced by biopharma_drugs
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
        total_trials = db.query(ClinicalTrial).count()
        total_targets = db.query(Target).count()
        
        # Get actual document counts from database
        fda_docs = db.query(Document).filter(Document.source_type == 'fda_drug_approval').count()
        drugs_com_docs = db.query(Document).filter(Document.source_type == 'drugs_com_profile').count()
        total_docs = db.query(Document).count()
        
        # Get drugs by company
        companies_with_drugs = db.query(Company).join(Drug).distinct().all()
        
        summary_lines = [
            "Comprehensive Drug Collection Summary",
            "========================================",
            "",
            f"Pipeline Drugs Found: {total_drugs}",
            f"FDA Documents: {fda_docs}",
            f"Drugs.com Documents: {drugs_com_docs}",
            f"Clinical Trials: {total_trials}",
            f"Targets: {total_targets}",
            f"Total Documents: {total_docs}",
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


def populate_vector_database() -> dict:
    """Populate vector database for React RAG agent semantic search."""
    try:
        logger.info("Starting vector database population...")
        
        from src.rag.vector_db_manager import VectorDBManager
        
        # Initialize vector database manager
        vector_db = VectorDBManager()
        
        # Check current collection stats
        stats = vector_db.get_collection_stats()
        logger.info(f"Current collection stats: {stats}")
        
        # Reset collection if it has data
        if stats.get("total_chunks", 0) > 0:
            logger.info("Collection has existing data. Resetting...")
            vector_db.reset_collection()
        
        # Populate database with batch processing
        vector_db.populate_database(batch_size=32)  # Use smaller batch size for embeddings
        
        # Get final stats
        final_stats = vector_db.get_collection_stats()
        logger.info(f"Final collection stats: {final_stats}")
        
        logger.info("Vector database population completed successfully!")
        
        return {
            "status": "success",
            "initial_chunks": stats.get("total_chunks", 0),
            "final_chunks": final_stats.get("total_chunks", 0),
            "embedding_model": final_stats.get("embedding_model", ""),
            "collection_name": final_stats.get("collection_name", "")
        }
        
    except Exception as e:
        logger.error(f"Error populating vector database: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def run_processing(db: Session, batch_size: int = 100) -> dict:
    """Run a simplified processing pipeline (lean, core steps only)."""
    logger.info(f"Processing pipeline start (batch_size={batch_size})")

    # 1) Ensure baseline companies exist
    companies_created = ensure_companies(db)

    # 2) Seed drugs from Ground Truth first (with company assignments)
    gt_seeding = seed_drugs_from_ground_truth(db)
    drugs_seeded = gt_seeding.get("drugs_created", 0)
    drugs_updated = gt_seeding.get("drugs_updated", 0)

    # 3) Extract additional drugs from documents using seed drugs and learned patterns
    drugs_extracted = extract_drugs_from_documents(db, batch_size)

    # 4) Link trials to companies (simple sponsor/title containment)
    trials_linked_to_companies = link_trials_to_companies(db)

    # 5) Link clinical trials to drugs based on drug names in trial titles/content
    trials_linked_to_drugs = link_clinical_trials_to_drugs(db)

    # 6) Backfill drug-target relationships from Ground Truth and hardcoded mappings
    # This ensures all drugs get their targets linked (Priority: Ground Truth > Hardcoded)
    # Also adds Ground Truth targets to COMMON_TARGETS for document extraction
    target_relationships = backfill_drug_targets(db)

    # 7) Extract targets directly from documents (batched) and link to drugs
    # Uses expanded COMMON_TARGETS (includes Ground Truth targets added in step 6)
    targets_created = extract_targets_from_documents(db, batch_size)

    # 8) Deduplicate drugs within each company
    deduplication = deduplicate_drugs_within_company(db)

    # 9) Export CSVs and summaries
    csv_exports = generate_csv_exports(db)

    logger.info("Processing pipeline done")
    return {
        "companies_created": companies_created,
        "drugs_seeded_from_gt": drugs_seeded,
        "drugs_updated_from_gt": drugs_updated,
        "drugs_extracted_from_docs": drugs_extracted,
        "trials_linked_to_companies": trials_linked_to_companies,
        "trials_linked_to_drugs": trials_linked_to_drugs,
        "targets_created": targets_created,
        "target_relationships_created": target_relationships,
        "deduplication": deduplication,
        "csv_exports": csv_exports,
        "batch_size_used": batch_size
    }


