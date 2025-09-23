"""Pydantic models for structured RAG responses and biopartnering insights."""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation reference for RAG responses."""
    label: str = Field(..., description="Citation label (e.g., 'Doc 1', 'Trial 1')")
    title: str = Field(..., description="Document or trial title")
    url: str = Field(..., description="Source URL")
    source: str = Field(..., description="Source type (e.g., 'clinical_trial', 'fda', 'company_website')")
    page_number: Optional[int] = Field(None, description="Page number if applicable")
    section: Optional[str] = Field(None, description="Document section if applicable")


class DrugInfo(BaseModel):
    """Structured drug information."""
    generic_name: str = Field(..., description="Generic drug name")
    brand_name: Optional[str] = Field(None, description="Brand name if available")
    company: str = Field(..., description="Developing company")
    drug_class: Optional[str] = Field(None, description="Drug class (e.g., 'Monoclonal antibody', 'Small molecule')")
    target: Optional[str] = Field(None, description="Molecular target")
    mechanism: Optional[str] = Field(None, description="Mechanism of action")
    indication: Optional[str] = Field(None, description="Approved indication")
    fda_approval_date: Optional[str] = Field(None, description="FDA approval date (YYYY-MM-DD)")
    development_stage: Optional[str] = Field(None, description="Development stage (e.g., 'Phase I', 'Approved')")
    nct_codes: List[str] = Field(default_factory=list, description="Associated clinical trial NCT codes")


class ClinicalTrialInfo(BaseModel):
    """Structured clinical trial information."""
    nct_id: str = Field(..., description="NCT identifier")
    title: str = Field(..., description="Trial title")
    phase: Optional[str] = Field(None, description="Trial phase (I, II, III, IV)")
    status: Optional[str] = Field(None, description="Trial status (e.g., 'Recruiting', 'Completed')")
    condition: Optional[str] = Field(None, description="Condition being studied")
    intervention: Optional[str] = Field(None, description="Intervention being tested")
    sponsor: Optional[str] = Field(None, description="Trial sponsor")
    start_date: Optional[str] = Field(None, description="Trial start date")
    completion_date: Optional[str] = Field(None, description="Trial completion date")
    location: Optional[str] = Field(None, description="Trial location(s)")


class BiopartneringInsight(BaseModel):
    """Structured biopartnering insight."""
    insight_type: str = Field(..., description="Type of insight (e.g., 'collaboration_opportunity', 'competitive_analysis', 'market_gap')")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Detailed description")
    companies_involved: List[str] = Field(default_factory=list, description="Companies mentioned")
    drugs_involved: List[str] = Field(default_factory=list, description="Drugs mentioned")
    therapeutic_area: Optional[str] = Field(None, description="Therapeutic area")
    market_potential: Optional[str] = Field(None, description="Market potential assessment")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    supporting_evidence: List[str] = Field(default_factory=list, description="Supporting evidence points")


class RAGResponse(BaseModel):
    """Structured RAG response with citations and confidence."""
    answer: str = Field(..., description="Main answer to the question")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (0-1)")
    citations: List[Citation] = Field(default_factory=list, description="Source citations")
    drugs_mentioned: List[DrugInfo] = Field(default_factory=list, description="Drugs mentioned in response")
    trials_mentioned: List[ClinicalTrialInfo] = Field(default_factory=list, description="Clinical trials mentioned")
    insights: List[BiopartneringInsight] = Field(default_factory=list, description="Biopartnering insights generated")
    cached: bool = Field(default=False, description="Whether response was cached")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class DrugSearchQuery(BaseModel):
    """Structured drug search query."""
    query: str = Field(..., description="Search query")
    company_filter: Optional[str] = Field(None, description="Filter by company")
    drug_class_filter: Optional[str] = Field(None, description="Filter by drug class")
    indication_filter: Optional[str] = Field(None, description="Filter by indication")
    development_stage_filter: Optional[str] = Field(None, description="Filter by development stage")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")


class ClinicalTrialSearchQuery(BaseModel):
    """Structured clinical trial search query."""
    query: str = Field(..., description="Search query")
    phase_filter: Optional[str] = Field(None, description="Filter by trial phase")
    status_filter: Optional[str] = Field(None, description="Filter by trial status")
    condition_filter: Optional[str] = Field(None, description="Filter by condition")
    sponsor_filter: Optional[str] = Field(None, description="Filter by sponsor")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")


class BiopartneringQuery(BaseModel):
    """Structured biopartnering query."""
    query: str = Field(..., description="Biopartnering question or request")
    focus_area: Optional[str] = Field(None, description="Focus area (e.g., 'oncology', 'immunotherapy')")
    company_interest: Optional[List[str]] = Field(None, description="Companies of interest")
    therapeutic_area: Optional[str] = Field(None, description="Therapeutic area of interest")
    partnership_type: Optional[str] = Field(None, description="Type of partnership (e.g., 'collaboration', 'licensing')")


class DataCollectionTask(BaseModel):
    """Structured data collection task."""
    task_type: str = Field(..., description="Type of collection task")
    target_urls: List[str] = Field(..., description="URLs to collect from")
    extraction_focus: Optional[str] = Field(None, description="What to extract (e.g., 'drugs', 'trials', 'pipeline')")
    company_context: Optional[str] = Field(None, description="Company context for extraction")
    priority: int = Field(default=1, ge=1, le=5, description="Task priority (1-5)")


class ErrorResponse(BaseModel):
    """Structured error response."""
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")



