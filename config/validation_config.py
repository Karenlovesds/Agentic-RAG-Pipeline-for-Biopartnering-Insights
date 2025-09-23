"""
Validation Configuration

Configuration settings for ground truth validation system.
"""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "biopartnering_insights.db"
GROUND_TRUTH_PATH = PROJECT_ROOT / "data" / "Pipeline_Ground_Truth.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Validation thresholds
THRESHOLDS = {
    "drug_names": {
        "f1_score_min": 0.8,
        "precision_min": 0.7,
        "recall_min": 0.7
    },
    "company_coverage": {
        "f1_score_min": 0.9,
        "precision_min": 0.8,
        "recall_min": 0.8
    },
    "mechanisms": {
        "accuracy_min": 0.7,
        "exact_match_min": 0.5
    },
    "clinical_trials": {
        "coverage_min": 0.5,
        "trial_count_min": 1
    }
}

# Company name mappings for validation
COMPANY_MAPPINGS = {
    # Ground truth name -> Pipeline name
    "roche": "roche/genentech",
    "genentech": "roche/genentech", 
    "jnj": "johnson & johnson",
    "merck": "merck & co.",
    "gilead": "gilead sciences",
    "regeneron": "regeneron pharmaceuticals",
    "astellas": "astellas pharma",
    "daiichi": "daiichi sankyo"
}

# Drug name cleaning patterns
DRUG_CLEANING_PATTERNS = [
    r'\s+',  # Multiple spaces
    r'^\s+|\s+$',  # Leading/trailing spaces
    r'[^\w\s-]',  # Special characters except hyphens
]

# Mechanism extraction patterns
MECHANISM_PATTERNS = {
    "monoclonal_antibody": [
        "monoclonal antibody", "mab", "anti-", "humanized", "chimeric"
    ],
    "kinase_inhibitor": [
        "kinase inhibitor", "inhibitor", "tyrosine kinase", "serine/threonine"
    ],
    "adc": [
        "antibody-drug conjugate", "adc", "conjugate", "payload"
    ],
    "bite": [
        "bispecific", "bite", "t-cell engager", "t cell engager"
    ],
    "serd": [
        "serd", "estrogen receptor degrader", "selective estrogen"
    ]
}

# Validation report settings
REPORT_SETTINGS = {
    "max_mismatch_details": 10,
    "max_missing_items": 5,
    "include_partial_matches": True,
    "include_extra_items": True
}
