"""Data models for biopartnering insights entities."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field


Base = declarative_base()


class Company(Base):
    """Company entity model."""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    ticker = Column(String(10), nullable=True)
    website = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drugs = relationship("Drug", back_populates="company")
    clinical_trials = relationship("ClinicalTrial", back_populates="sponsor")


class Drug(Base):
    """Drug entity model."""
    __tablename__ = "drugs"
    
    id = Column(Integer, primary_key=True, index=True)
    generic_name = Column(String(255), index=True, nullable=False)
    brand_name = Column(String(255), nullable=True)
    drug_class = Column(String(255), nullable=True)
    mechanism_of_action = Column(Text, nullable=True)
    fda_approval_status = Column(Boolean, default=False)
    fda_approval_date = Column(DateTime, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    
    # Standardized identifiers
    rxnorm_id = Column(String(50), nullable=True)
    drugbank_id = Column(String(50), nullable=True)
    unii = Column(String(50), nullable=True)
    
    # Clinical trial information
    nct_codes = Column(JSON, nullable=True)  # List of NCT codes associated with this drug
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="drugs")
    targets = relationship("DrugTarget", back_populates="drug")
    indications = relationship("DrugIndication", back_populates="drug")
    clinical_trials = relationship("ClinicalTrial", back_populates="drug")


class Target(Base):
    """Target entity model (proteins, genes, etc.)."""
    __tablename__ = "targets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    hgnc_symbol = Column(String(50), nullable=True)
    uniprot_id = Column(String(50), nullable=True)
    gene_id = Column(String(50), nullable=True)
    target_type = Column(String(100), nullable=True)  # protein, gene, pathway, etc.
    description = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drugs = relationship("DrugTarget", back_populates="target")


class Indication(Base):
    """Indication entity model."""
    __tablename__ = "indications"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    ncit_id = Column(String(50), nullable=True)
    icd10_code = Column(String(20), nullable=True)
    indication_type = Column(String(100), nullable=True)  # cancer, autoimmune, etc.
    description = Column(Text, nullable=True)
    
    # Cancer-specific fields
    biomarker_status = Column(JSON, nullable=True)  # {"ER": "positive", "PR": "negative", "HER2": "positive"}
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drugs = relationship("DrugIndication", back_populates="indication")


class ClinicalTrial(Base):
    """Clinical trial entity model."""
    __tablename__ = "clinical_trials"
    
    id = Column(Integer, primary_key=True, index=True)
    nct_id = Column(String(20), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    phase = Column(String(50), nullable=True)  # Phase 1, Phase 2, Phase 3, etc.
    status = Column(String(100), nullable=True)  # recruiting, completed, etc.
    start_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    
    # Relationships
    sponsor_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=True)
    
    # Trial details
    trial_type = Column(String(100), nullable=True)  # interventional, observational
    primary_purpose = Column(String(100), nullable=True)  # treatment, prevention, etc.
    study_population = Column(Text, nullable=True)
    primary_endpoints = Column(JSON, nullable=True)
    secondary_endpoints = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sponsor = relationship("Company", back_populates="clinical_trials")
    drug = relationship("Drug", back_populates="clinical_trials")


class DrugTarget(Base):
    """Association table for drug-target relationships."""
    __tablename__ = "drug_targets"
    
    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)
    relationship_type = Column(String(100), nullable=True)  # inhibits, activates, etc.
    affinity = Column(String(100), nullable=True)  # IC50, Ki, etc.
    
    # Relationships
    drug = relationship("Drug", back_populates="targets")
    target = relationship("Target", back_populates="drugs")


class DrugIndication(Base):
    """Association table for drug-indication relationships."""
    __tablename__ = "drug_indications"
    
    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    indication_id = Column(Integer, ForeignKey("indications.id"), nullable=False)
    approval_status = Column(Boolean, default=False)
    approval_date = Column(DateTime, nullable=True)
    line_of_therapy = Column(String(100), nullable=True)  # 1L, 2L, etc.
    
    # Relationships
    drug = relationship("Drug", back_populates="indications")
    indication = relationship("Indication", back_populates="drugs")


class Document(Base):
    """Document entity for storing source documents."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(1000), nullable=False)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256 hash
    source_type = Column(String(100), nullable=False)  # clinical_trials, drugs_com, fda
    retrieval_date = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RAGCache(Base):
    """Cache for RAG retrieval results to improve performance."""
    __tablename__ = "rag_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    query_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 of query
    query_text = Column(Text, nullable=False)
    retrieved_doc_ids = Column(JSON, nullable=False)  # List of document IDs
    answer = Column(Text, nullable=False)
    citations = Column(JSON, nullable=False)  # List of citation objects
    confidence_score = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=0)
    
    # Cache expiration (in hours)
    expires_at = Column(DateTime, nullable=True)


# Pydantic models for API responses
class CompanyResponse(BaseModel):
    """Pydantic model for company API responses."""
    id: int
    name: str
    ticker: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DrugResponse(BaseModel):
    """Pydantic model for drug API responses."""
    id: int
    generic_name: str
    brand_name: Optional[str] = None
    drug_class: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    fda_approval_status: bool
    fda_approval_date: Optional[datetime] = None
    company_name: str
    rxnorm_id: Optional[str] = None
    drugbank_id: Optional[str] = None
    unii: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClinicalTrialResponse(BaseModel):
    """Pydantic model for clinical trial API responses."""
    id: int
    nct_id: str
    title: str
    phase: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    sponsor_name: Optional[str] = None
    drug_name: Optional[str] = None
    trial_type: Optional[str] = None
    primary_purpose: Optional[str] = None
    study_population: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BiopartneringInsight(BaseModel):
    """Pydantic model for biopartnering insights."""
    query: str
    answer: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    sources: List[Dict[str, Any]]
    citations: List[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
