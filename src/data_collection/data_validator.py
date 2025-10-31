"""Comprehensive data validation pipeline across all sources."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from loguru import logger
from .fda_collector import EnhancedFDACollector, ValidatedDrug, DrugTarget, DrugIndication
from .utils import DataCollectionUtils


@dataclass
class ValidationResult:
    """Data class for validation results."""
    source: str
    confidence_score: float
    validation_status: str
    details: Dict[str, Any]
    timestamp: datetime


@dataclass
class ComprehensiveDrugData:
    """Data class for comprehensive validated drug data."""
    drug_name: str
    validated_drug: Optional[ValidatedDrug]
    targets: List[DrugTarget]
    indications: List[DrugIndication]
    validation_results: List[ValidationResult]
    overall_confidence: float
    data_sources: List[str]


class DataValidator:
    """Comprehensive data validation pipeline across all sources."""
    
    def __init__(self):
        # FDA collector disabled (PubMed removed, SEC removed)
        self.fda_collector = None
        
        # Validation thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
    
    
    async def _validate_single_drug_comprehensive(self, drug_name: str, company_name: str) -> ComprehensiveDrugData:
        """Validate single drug across all sources."""
        validation_results = []
        data_sources = []
        
        # 1. FDA validation
        fda_validation = await self._validate_with_fda(drug_name)
        validation_results.append(fda_validation)
        if fda_validation.validation_status == "validated":
            data_sources.append("FDA")
        
        # 2. Literature validation removed (no PubMed)
        # 3. SEC filings validation removed
        
        # 4. Extract comprehensive data
        validated_drug = fda_validation.details.get("validated_drug") if fda_validation.validation_status == "validated" else None
        targets = await self._extract_comprehensive_targets(drug_name, company_name)
        indications = await self._extract_comprehensive_indications(drug_name, company_name)
        
        # 5. Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(validation_results, targets, indications)
        
        return ComprehensiveDrugData(
            drug_name=drug_name,
            validated_drug=validated_drug,
            targets=targets,
            indications=indications,
            validation_results=validation_results,
            overall_confidence=overall_confidence,
            data_sources=data_sources
        )
    
    async def _validate_with_fda(self, drug_name: str) -> ValidationResult:
        """Validate drug with FDA database."""
        # FDA validation disabled; return not_available
        return ValidationResult(
            source="FDA",
            confidence_score=0.0,
            validation_status="not_available",
            details={"info": "FDA validation disabled in this configuration"},
            timestamp=datetime.now()
        )
    
    
    # PubMed validation removed entirely
    
    async def _extract_comprehensive_targets(self, drug_name: str, company_name: str) -> List[DrugTarget]:
        """Extract comprehensive target information from all sources."""
        # PubMed extraction removed; return empty list
        return []
    
    async def _extract_comprehensive_indications(self, drug_name: str, company_name: str) -> List[DrugIndication]:
        """Extract comprehensive indication information from all sources."""
        # PubMed extraction removed; return empty list
        return []
    
    
    def _calculate_overall_confidence(self, validation_results: List[ValidationResult], 
                                    targets: List[DrugTarget], indications: List[DrugIndication]) -> float:
        """Calculate overall confidence score for comprehensive drug data."""
        try:
            # Weight different validation sources
            source_weights = {
                "FDA": 1.0
            }
            
            # Calculate weighted validation score
            validation_score = 0.0
            total_weight = 0.0
            
            for result in validation_results:
                weight = source_weights.get(result.source, 0.1)
                validation_score += result.confidence_score * weight
                total_weight += weight
            
            if total_weight > 0:
                validation_score /= total_weight
            
            # Boost confidence based on data richness
            data_richness_bonus = 0.0
            
            # Targets bonus
            if targets:
                avg_target_confidence = sum(t.confidence_score for t in targets) / len(targets)
                data_richness_bonus += min(0.1, avg_target_confidence * 0.1)
            
            # Indications bonus
            if indications:
                avg_indication_confidence = sum(i.confidence_score for i in indications) / len(indications)
                data_richness_bonus += min(0.1, avg_indication_confidence * 0.1)
            
            # Calculate final confidence
            overall_confidence = min(1.0, validation_score + data_richness_bonus)
            
            return overall_confidence
            
        except Exception as e:
            logger.error(f"Error calculating overall confidence: {e}")
            return 0.0
    
    def generate_validation_report(self, comprehensive_data: List[ComprehensiveDrugData]) -> str:
        """Generate a comprehensive validation report."""
        report_parts = [
            "COMPREHENSIVE DRUG DATA VALIDATION REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Drugs Validated: {len(comprehensive_data)}",
            "",
            "=" * 80,
            ""
        ]
        
        # Summary statistics
        high_confidence = sum(1 for d in comprehensive_data if d.overall_confidence > self.confidence_thresholds["high"])
        medium_confidence = sum(1 for d in comprehensive_data if self.confidence_thresholds["medium"] < d.overall_confidence <= self.confidence_thresholds["high"])
        low_confidence = sum(1 for d in comprehensive_data if d.overall_confidence <= self.confidence_thresholds["medium"])
        
        report_parts.extend([
            "SUMMARY STATISTICS:",
            f"High Confidence (>0.8): {high_confidence} drugs",
            f"Medium Confidence (0.6-0.8): {medium_confidence} drugs",
            f"Low Confidence (<0.6): {low_confidence} drugs",
            "",
            "=" * 80,
            ""
        ])
        
        # Detailed results for each drug
        for i, drug_data in enumerate(comprehensive_data, 1):
            report_parts.extend([
                f"{i}. {drug_data.drug_name}",
                f"   Overall Confidence: {drug_data.overall_confidence:.3f}",
                f"   Data Sources: {', '.join(drug_data.data_sources)}",
                f"   Targets Found: {len(drug_data.targets)}",
                f"   Indications Found: {len(drug_data.indications)}",
                ""
            ])
            
            # Validation results
            report_parts.append("   Validation Results:")
            for result in drug_data.validation_results:
                status_icon = "✅" if result.validation_status == "validated" else "⚠️" if result.validation_status == "partial" else "❌"
                report_parts.append(f"     {status_icon} {result.source}: {result.confidence_score:.3f} ({result.validation_status})")
            
            # Top targets
            if drug_data.targets:
                report_parts.append("   Top Targets:")
                for target in drug_data.targets[:3]:
                    report_parts.append(f"     - {target.target_name} ({target.target_type}) - {target.confidence_score:.3f}")
            
            # Top indications
            if drug_data.indications:
                report_parts.append("   Top Indications:")
                for indication in drug_data.indications[:3]:
                    status = "Approved" if indication.approval_status else "Investigational"
                    report_parts.append(f"     - {indication.indication} ({status}) - {indication.confidence_score:.3f}")
            
            report_parts.append("")
        
        return "\n".join(report_parts)
    
    async def validate_drug_list_comprehensive(self, drug_names: List[str], company_name: str) -> Tuple[List[ComprehensiveDrugData], str]:
        """Validate a list of drugs and generate a comprehensive report."""
        logger.info(f"Starting comprehensive validation for {len(drug_names)} drugs from {company_name}")
        
        comprehensive_data = []
        
        for drug_name in drug_names:
            try:
                logger.info(f"Validating comprehensive data for {drug_name}")
                
                # Validate drug data across all sources
                drug_data = await self._validate_single_drug_comprehensive(drug_name, company_name)
                comprehensive_data.append(drug_data)
                
                logger.info(f"✅ Completed validation for {drug_name} (confidence: {drug_data.overall_confidence:.2f})")
                
            except Exception as e:
                logger.error(f"Error validating {drug_name}: {e}")
                continue
        
        # Sort by overall confidence
        comprehensive_data.sort(key=lambda x: x.overall_confidence, reverse=True)
        
        logger.info(f"Completed comprehensive validation for {len(comprehensive_data)} drugs")
        
        # Generate report
        report = self.generate_validation_report(comprehensive_data)
        
        return comprehensive_data, report

