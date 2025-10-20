"""Configuration file for API endpoints and settings."""

import os
from typing import Dict, Any


class APIConfig:
    """Configuration class for API endpoints and settings."""
    
    # FDA API Configuration
    FDA_BASE_URL = os.getenv("FDA_BASE_URL", "https://api.fda.gov")
    FDA_ENDPOINTS = {
        "drug_label": os.getenv("FDA_DRUG_LABEL_ENDPOINT", "/drug/label.json"),
        "drug_event": os.getenv("FDA_DRUG_EVENT_ENDPOINT", "/drug/event.json"),
        "drug_ndc": os.getenv("FDA_DRUG_NDC_ENDPOINT", "/drug/ndc.json"),
        "orange_book": os.getenv("FDA_ORANGE_BOOK_ENDPOINT", "/drug/ndc.json"),
        "drug_shortage": os.getenv("FDA_DRUG_SHORTAGE_ENDPOINT", "/drug/shortage.json")
    }
    
    # PubMed API Configuration
    PUBMED_BASE_URL = os.getenv("PUBMED_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils")
    PUBMED_ENDPOINTS = {
        "search": os.getenv("PUBMED_SEARCH_ENDPOINT", "/esearch.fcgi"),
        "fetch": os.getenv("PUBMED_FETCH_ENDPOINT", "/efetch.fcgi"),
        "summary": os.getenv("PUBMED_SUMMARY_ENDPOINT", "/esummary.fcgi")
    }
    
    # Clinical Trials API Configuration
    CLINICAL_TRIALS_BASE_URL = os.getenv("CLINICAL_TRIALS_BASE_URL", "https://clinicaltrials.gov/api/v2")
    CLINICAL_TRIALS_ENDPOINTS = {
        "studies": os.getenv("CLINICAL_TRIALS_STUDIES_ENDPOINT", "/studies"),
        "interventions": os.getenv("CLINICAL_TRIALS_INTERVENTIONS_ENDPOINT", "/interventions"),
        "conditions": os.getenv("CLINICAL_TRIALS_CONDITIONS_ENDPOINT", "/conditions")
    }
    
    # SEC API Configuration
    SEC_BASE_URL = os.getenv("SEC_BASE_URL", "https://data.sec.gov")
    SEC_ENDPOINTS = {
        "submissions": os.getenv("SEC_SUBMISSIONS_ENDPOINT", "/submissions"),
        "company_facts": os.getenv("SEC_COMPANY_FACTS_ENDPOINT", "/api/xbrl/companyfacts")
    }
    
    # Drugs.com Configuration
    DRUGS_COM_BASE_URL = os.getenv("DRUGS_COM_BASE_URL", "https://www.drugs.com")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./biopartnering.db")
    
    # Vector Database Configuration
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    
    # API Rate Limits
    FDA_RATE_LIMIT = int(os.getenv("FDA_RATE_LIMIT", "1000"))  # requests per hour
    PUBMED_RATE_LIMIT = int(os.getenv("PUBMED_RATE_LIMIT", "3"))  # requests per second
    CLINICAL_TRIALS_RATE_LIMIT = int(os.getenv("CLINICAL_TRIALS_RATE_LIMIT", "100"))  # requests per hour
    
    # Request Timeouts
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # seconds
    CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "10"))  # seconds
    
    # Retry Configuration
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "1"))  # seconds
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Data Processing Configuration
    MAX_ARTICLES_PER_DRUG = int(os.getenv("MAX_ARTICLES_PER_DRUG", "20"))
    MAX_CLINICAL_TRIALS_PER_DRUG = int(os.getenv("MAX_CLINICAL_TRIALS_PER_DRUG", "10"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    
    # Company Search Terms (can be overridden by environment variables)
    COMPANY_SEARCH_TERMS = {
        "Roche/Genentech": ["Roche", "Genentech", "Hoffmann-La Roche", "F. Hoffmann-La Roche"],
        "Merck": ["Merck", "Merck & Co", "MSD"],
        "Pfizer": ["Pfizer", "Pfizer Inc"],
        "Novartis": ["Novartis", "Novartis AG"],
        "Johnson & Johnson": ["Johnson & Johnson", "J&J", "Janssen"],
        "Bristol Myers Squibb": ["Bristol Myers Squibb", "BMS"],
        "AbbVie": ["AbbVie", "AbbVie Inc"],
        "Gilead": ["Gilead", "Gilead Sciences"],
        "Amgen": ["Amgen", "Amgen Inc"],
        "Biogen": ["Biogen", "Biogen Inc"],
        "Regeneron": ["Regeneron", "Regeneron Pharmaceuticals"],
        "Moderna": ["Moderna", "Moderna Inc"],
        "BioNTech": ["BioNTech", "BioNTech SE"],
        "Daiichi Sankyo": ["Daiichi Sankyo", "Daiichi"],
        "AstraZeneca": ["AstraZeneca", "AZ"],
        "GSK": ["GlaxoSmithKline", "GSK"],
        "Sanofi": ["Sanofi", "Sanofi-Aventis"],
        "Takeda": ["Takeda", "Takeda Pharmaceutical"],
        "Bayer": ["Bayer", "Bayer AG"],
        "Boehringer Ingelheim": ["Boehringer Ingelheim", "BI"]
    }
    
    @classmethod
    def get_fda_endpoint(cls, endpoint_name: str) -> str:
        """Get FDA endpoint URL."""
        if endpoint_name not in cls.FDA_ENDPOINTS:
            raise ValueError(f"Unknown FDA endpoint: {endpoint_name}")
        return cls.FDA_BASE_URL + cls.FDA_ENDPOINTS[endpoint_name]
    
    @classmethod
    def get_pubmed_endpoint(cls, endpoint_name: str) -> str:
        """Get PubMed endpoint URL."""
        if endpoint_name not in cls.PUBMED_ENDPOINTS:
            raise ValueError(f"Unknown PubMed endpoint: {endpoint_name}")
        return cls.PUBMED_BASE_URL + cls.PUBMED_ENDPOINTS[endpoint_name]
    
    @classmethod
    def get_clinical_trials_endpoint(cls, endpoint_name: str) -> str:
        """Get Clinical Trials endpoint URL."""
        if endpoint_name not in cls.CLINICAL_TRIALS_ENDPOINTS:
            raise ValueError(f"Unknown Clinical Trials endpoint: {endpoint_name}")
        return cls.CLINICAL_TRIALS_BASE_URL + cls.CLINICAL_TRIALS_ENDPOINTS[endpoint_name]
    
    @classmethod
    def get_sec_endpoint(cls, endpoint_name: str) -> str:
        """Get SEC endpoint URL."""
        if endpoint_name not in cls.SEC_ENDPOINTS:
            raise ValueError(f"Unknown SEC endpoint: {endpoint_name}")
        return cls.SEC_BASE_URL + cls.SEC_ENDPOINTS[endpoint_name]
    
    @classmethod
    def get_company_search_terms(cls, company_name: str) -> list:
        """Get search terms for a company."""
        # Direct match
        if company_name in cls.COMPANY_SEARCH_TERMS:
            return cls.COMPANY_SEARCH_TERMS[company_name]
        
        # Partial match
        company_lower = company_name.lower()
        for key, terms in cls.COMPANY_SEARCH_TERMS.items():
            if any(term.lower() in company_lower for term in terms):
                return terms
        
        # Fallback - return the company name itself
        return [company_name]
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status."""
        validation_results = {
            "fda_api": cls._validate_fda_config(),
            "pubmed_api": cls._validate_pubmed_config(),
            "clinical_trials_api": cls._validate_clinical_trials_config(),
            "sec_api": cls._validate_sec_config(),
            "database": cls._validate_database_config(),
            "vector_db": cls._validate_vector_db_config()
        }
        
        return validation_results
    
    @classmethod
    def _validate_fda_config(cls) -> Dict[str, Any]:
        """Validate FDA API configuration."""
        return {
            "base_url": cls.FDA_BASE_URL,
            "endpoints": list(cls.FDA_ENDPOINTS.keys()),
            "rate_limit": cls.FDA_RATE_LIMIT,
            "valid": bool(cls.FDA_BASE_URL)
        }
    
    @classmethod
    def _validate_pubmed_config(cls) -> Dict[str, Any]:
        """Validate PubMed API configuration."""
        return {
            "base_url": cls.PUBMED_BASE_URL,
            "endpoints": list(cls.PUBMED_ENDPOINTS.keys()),
            "rate_limit": cls.PUBMED_RATE_LIMIT,
            "valid": bool(cls.PUBMED_BASE_URL)
        }
    
    @classmethod
    def _validate_clinical_trials_config(cls) -> Dict[str, Any]:
        """Validate Clinical Trials API configuration."""
        return {
            "base_url": cls.CLINICAL_TRIALS_BASE_URL,
            "endpoints": list(cls.CLINICAL_TRIALS_ENDPOINTS.keys()),
            "rate_limit": cls.CLINICAL_TRIALS_RATE_LIMIT,
            "valid": bool(cls.CLINICAL_TRIALS_BASE_URL)
        }
    
    @classmethod
    def _validate_sec_config(cls) -> Dict[str, Any]:
        """Validate SEC API configuration."""
        return {
            "base_url": cls.SEC_BASE_URL,
            "endpoints": list(cls.SEC_ENDPOINTS.keys()),
            "valid": bool(cls.SEC_BASE_URL)
        }
    
    @classmethod
    def _validate_database_config(cls) -> Dict[str, Any]:
        """Validate database configuration."""
        return {
            "url": cls.DATABASE_URL,
            "valid": bool(cls.DATABASE_URL)
        }
    
    @classmethod
    def _validate_vector_db_config(cls) -> Dict[str, Any]:
        """Validate vector database configuration."""
        return {
            "path": cls.VECTOR_DB_PATH,
            "chroma_persist_directory": cls.CHROMA_PERSIST_DIRECTORY,
            "valid": bool(cls.VECTOR_DB_PATH)
        }

