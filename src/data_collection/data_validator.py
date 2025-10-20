"""Comprehensive data validation pipeline across all sources."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from loguru import logger
from .fda_collector import EnhancedFDACollector, ValidatedDrug, DrugTarget, DrugIndication
from .sec_filings_extractor import SECFilingsExtractor, SECFiling, PipelineInfo
from .pubmed_extractor import PubMedExtractor, DrugTargetInfo, DrugIndicationInfo


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
    pipeline_info: List[PipelineInfo]
    sec_filings: List[SECFiling]
    validation_results: List[ValidationResult]
    overall_confidence: float
    data_sources: List[str]


class DataValidator:
    """Comprehensive data validation pipeline across all sources."""
    
    def __init__(self):
        self.fda_collector = EnhancedFDACollector()
        self.sec_extractor = SECFilingsExtractor()
        self.pubmed_extractor = PubMedExtractor()
        
        # Validation thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
    
    async def validate_comprehensive_drug_data(self, drug_names: List[str], company_name: str) -> List[ComprehensiveDrugData]:
        """Validate comprehensive drug data across all sources."""
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
        return comprehensive_data
    
    async def _validate_single_drug_comprehensive(self, drug_name: str, company_name: str) -> ComprehensiveDrugData:
        """Validate single drug across all sources."""
        validation_results = []
        data_sources = []
        
        # 1. FDA validation
        fda_validation = await self._validate_with_fda(drug_name)
        validation_results.append(fda_validation)
        if fda_validation.validation_status == "validated":
            data_sources.append("FDA")
        
        # 2. SEC filings validation
        sec_validation = await self._validate_with_sec_filings(drug_name, company_name)
        validation_results.append(sec_validation)
        if sec_validation.validation_status == "validated":
            data_sources.append("SEC")
        
        # 3. PubMed validation
        pubmed_validation = await self._validate_with_pubmed(drug_name, company_name)
        validation_results.append(pubmed_validation)
        if pubmed_validation.validation_status == "validated":
            data_sources.append("PubMed")
        
        # 4. Extract comprehensive data
        validated_drug = fda_validation.details.get("validated_drug") if fda_validation.validation_status == "validated" else None
        targets = await self._extract_comprehensive_targets(drug_name, company_name)
        indications = await self._extract_comprehensive_indications(drug_name, company_name)
        pipeline_info = await self._extract_pipeline_info(drug_name, company_name)
        sec_filings = await self._extract_sec_filings(drug_name, company_name)
        
        # 5. Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(validation_results, targets, indications, pipeline_info)
        
        return ComprehensiveDrugData(
            drug_name=drug_name,
            validated_drug=validated_drug,
            targets=targets,
            indications=indications,
            pipeline_info=pipeline_info,
            sec_filings=sec_filings,
            validation_results=validation_results,
            overall_confidence=overall_confidence,
            data_sources=data_sources
        )
    
    async def _validate_with_fda(self, drug_name: str) -> ValidationResult:
        """Validate drug with FDA database."""
        try:
            logger.info(f"Validating {drug_name} with FDA database")
            
            # Validate drug name against FDA
            validated_drugs = await self.fda_collector.validate_drug_names([drug_name])
            
            if validated_drugs:
                validated_drug = validated_drugs[0]
                confidence = validated_drug.validation_confidence
                
                return ValidationResult(
                    source="FDA",
                    confidence_score=confidence,
                    validation_status="validated" if confidence > self.confidence_thresholds["medium"] else "partial",
                    details={
                        "validated_drug": validated_drug,
                        "brand_names": validated_drug.brand_names,
                        "generic_names": validated_drug.generic_names,
                        "manufacturer": validated_drug.manufacturer,
                        "indications": validated_drug.indications,
                        "approval_date": validated_drug.approval_date
                    },
                    timestamp=datetime.now()
                )
            else:
                return ValidationResult(
                    source="FDA",
                    confidence_score=0.0,
                    validation_status="not_found",
                    details={"error": "Drug not found in FDA database"},
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Error validating {drug_name} with FDA: {e}")
            return ValidationResult(
                source="FDA",
                confidence_score=0.0,
                validation_status="error",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    async def _validate_with_sec_filings(self, drug_name: str, company_name: str) -> ValidationResult:
        """Validate drug with SEC filings."""
        try:
            logger.info(f"Validating {drug_name} with SEC filings for {company_name}")
            
            # Extract SEC filings for the company
            sec_filings = await self.sec_extractor.extract_pipeline_from_filings(company_name, max_filings=5)
            
            # Check if drug is mentioned in SEC filings
            drug_mentions = []
            for filing in sec_filings:
                for pipeline_info in filing.extracted_pipeline_info:
                    if pipeline_info["drug_name"].lower() == drug_name.lower():
                        drug_mentions.append(pipeline_info)
            
            if drug_mentions:
                # Calculate confidence based on number of mentions and filing quality
                confidence = min(0.9, 0.5 + (len(drug_mentions) * 0.1))
                
                return ValidationResult(
                    source="SEC",
                    confidence_score=confidence,
                    validation_status="validated" if confidence > self.confidence_thresholds["medium"] else "partial",
                    details={
                        "drug_mentions": drug_mentions,
                        "filing_count": len(sec_filings),
                        "pipeline_stages": [info.get("development_stage") for info in drug_mentions],
                        "indications": [info.get("indication") for info in drug_mentions]
                    },
                    timestamp=datetime.now()
                )
            else:
                return ValidationResult(
                    source="SEC",
                    confidence_score=0.0,
                    validation_status="not_found",
                    details={"error": "Drug not found in SEC filings"},
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Error validating {drug_name} with SEC filings: {e}")
            return ValidationResult(
                source="SEC",
                confidence_score=0.0,
                validation_status="error",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    async def _validate_with_pubmed(self, drug_name: str, company_name: str = None) -> ValidationResult:
        """Validate drug with PubMed literature."""
        try:
            logger.info(f"Validating {drug_name} with PubMed literature" + (f" (company: {company_name})" if company_name else ""))
            
            # Search for drug in PubMed (with company filtering if provided)
            targets = await self.pubmed_extractor.extract_drug_targets(drug_name, max_articles=5, company_name=company_name)
            indications = await self.pubmed_extractor.extract_drug_indications(drug_name, max_articles=5, company_name=company_name)
            
            if targets or indications:
                # Calculate confidence based on number of articles and quality
                target_confidence = sum(t.confidence_score for t in targets) / len(targets) if targets else 0
                indication_confidence = sum(i.confidence_score for i in indications) / len(indications) if indications else 0
                overall_confidence = (target_confidence + indication_confidence) / 2
                
                return ValidationResult(
                    source="PubMed",
                    confidence_score=overall_confidence,
                    validation_status="validated" if overall_confidence > self.confidence_thresholds["medium"] else "partial",
                    details={
                        "targets_found": len(targets),
                        "indications_found": len(indications),
                        "target_confidence": target_confidence,
                        "indication_confidence": indication_confidence,
                        "top_targets": [t.target_name for t in targets[:3]],
                        "top_indications": [i.indication for i in indications[:3]]
                    },
                    timestamp=datetime.now()
                )
            else:
                return ValidationResult(
                    source="PubMed",
                    confidence_score=0.0,
                    validation_status="not_found",
                    details={"error": "Drug not found in PubMed literature"},
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Error validating {drug_name} with PubMed: {e}")
            return ValidationResult(
                source="PubMed",
                confidence_score=0.0,
                validation_status="error",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    async def _extract_comprehensive_targets(self, drug_name: str, company_name: str) -> List[DrugTarget]:
        """Extract comprehensive target information from all sources."""
        targets = []
        
        try:
            # Extract from FDA (with company filtering for PubMed)
            fda_targets = await self.fda_collector.extract_drug_targets(drug_name, company_name)
            targets.extend(fda_targets)
            
            # Extract from PubMed (with company filtering)
            pubmed_targets = await self.pubmed_extractor.extract_drug_targets(drug_name, max_articles=10, company_name=company_name)
            for pubmed_target in pubmed_targets:
                targets.append(DrugTarget(
                    target_name=pubmed_target.target_name,
                    target_type=pubmed_target.target_type,
                    mechanism_of_action=pubmed_target.mechanism_of_action,
                    confidence_score=pubmed_target.confidence_score,
                    source=f"PubMed ({pubmed_target.source_pmid})"
                ))
            
            # Deduplicate and sort by confidence
            unique_targets = self._deduplicate_targets(targets)
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive targets for {drug_name}: {e}")
        
        return unique_targets
    
    async def _extract_comprehensive_indications(self, drug_name: str, company_name: str) -> List[DrugIndication]:
        """Extract comprehensive indication information from all sources."""
        indications = []
        
        try:
            # Extract from FDA (with company filtering for PubMed)
            fda_indications = await self.fda_collector.extract_drug_indications(drug_name, company_name)
            indications.extend(fda_indications)
            
            # Extract from PubMed (with company filtering)
            pubmed_indications = await self.pubmed_extractor.extract_drug_indications(drug_name, max_articles=10, company_name=company_name)
            for pubmed_indication in pubmed_indications:
                indications.append(DrugIndication(
                    indication=pubmed_indication.indication,
                    approval_status=pubmed_indication.approval_status == "Approved",
                    approval_date=None,
                    source=f"PubMed ({pubmed_indication.source_pmid})",
                    confidence_score=pubmed_indication.confidence_score
                ))
            
            # Deduplicate and sort by confidence
            unique_indications = self._deduplicate_indications(indications)
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive indications for {drug_name}: {e}")
        
        return unique_indications
    
    async def _extract_pipeline_info(self, drug_name: str, company_name: str) -> List[PipelineInfo]:
        """Extract pipeline information from SEC filings."""
        pipeline_info = []
        
        try:
            # Extract SEC filings for the company
            sec_filings = await self.sec_extractor.extract_pipeline_from_filings(company_name, max_filings=5)
            
            # Find pipeline info for the specific drug
            for filing in sec_filings:
                for info in filing.extracted_pipeline_info:
                    if info["drug_name"].lower() == drug_name.lower():
                        pipeline_info.append(PipelineInfo(
                            drug_name=info["drug_name"],
                            development_stage=info.get("development_stage", ""),
                            indication=info.get("indication", ""),
                            target=info.get("target"),
                            mechanism_of_action=info.get("mechanism_of_action"),
                            phase=info.get("phase"),
                            status=info.get("status", ""),
                            source_filing=filing.accession_number,
                            extraction_confidence=info.get("extraction_confidence", 0.0)
                        ))
            
        except Exception as e:
            logger.error(f"Error extracting pipeline info for {drug_name}: {e}")
        
        return pipeline_info
    
    async def _extract_sec_filings(self, drug_name: str, company_name: str) -> List[SECFiling]:
        """Extract SEC filings that mention the drug."""
        relevant_filings = []
        
        try:
            # Extract SEC filings for the company
            sec_filings = await self.sec_extractor.extract_pipeline_from_filings(company_name, max_filings=5)
            
            # Filter filings that mention the drug
            for filing in sec_filings:
                for info in filing.extracted_pipeline_info:
                    if info["drug_name"].lower() == drug_name.lower():
                        relevant_filings.append(filing)
                        break
            
        except Exception as e:
            logger.error(f"Error extracting SEC filings for {drug_name}: {e}")
        
        return relevant_filings
    
    def _deduplicate_targets(self, targets: List[DrugTarget]) -> List[DrugTarget]:
        """Remove duplicate targets and sort by confidence."""
        seen = set()
        unique_targets = []
        
        for target in targets:
            key = target.target_name.upper()
            if key not in seen:
                seen.add(key)
                unique_targets.append(target)
        
        # Sort by confidence score
        unique_targets.sort(key=lambda x: x.confidence_score, reverse=True)
        return unique_targets[:15]  # Return top 15 targets
    
    def _deduplicate_indications(self, indications: List[DrugIndication]) -> List[DrugIndication]:
        """Remove duplicate indications and sort by confidence."""
        seen = set()
        unique_indications = []
        
        for indication in indications:
            key = indication.indication.lower()
            if key not in seen:
                seen.add(key)
                unique_indications.append(indication)
        
        # Sort by confidence score
        unique_indications.sort(key=lambda x: x.confidence_score, reverse=True)
        return unique_indications[:15]  # Return top 15 indications
    
    def _calculate_overall_confidence(self, validation_results: List[ValidationResult], 
                                    targets: List[DrugTarget], indications: List[DrugIndication],
                                    pipeline_info: List[PipelineInfo]) -> float:
        """Calculate overall confidence score for comprehensive drug data."""
        try:
            # Weight different validation sources
            source_weights = {
                "FDA": 0.4,      # FDA is most authoritative
                "SEC": 0.3,      # SEC filings are official but less specific
                "PubMed": 0.3    # PubMed provides scientific evidence
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
            
            # Pipeline info bonus
            if pipeline_info:
                avg_pipeline_confidence = sum(p.extraction_confidence for p in pipeline_info) / len(pipeline_info)
                data_richness_bonus += min(0.1, avg_pipeline_confidence * 0.1)
            
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
                f"   Pipeline Entries: {len(drug_data.pipeline_info)}",
                f"   SEC Filings: {len(drug_data.sec_filings)}",
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
        
        # Validate all drugs
        comprehensive_data = await self.validate_comprehensive_drug_data(drug_names, company_name)
        
        # Generate report
        report = self.generate_validation_report(comprehensive_data)
        
        logger.info(f"Completed comprehensive validation for {len(comprehensive_data)} drugs")
        
        return comprehensive_data, report

