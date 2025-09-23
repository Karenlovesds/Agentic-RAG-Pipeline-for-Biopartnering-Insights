"""
Ground Truth Validation System

This module provides comprehensive validation of pipeline results against ground truth data.
It compares extracted entities, measures accuracy, and identifies gaps for improvement.
"""

import pandas as pd
import sqlite3
from typing import Dict, List, Tuple, Any
from pathlib import Path
import json
from loguru import logger
from datetime import datetime


class GroundTruthValidator:
    """Validates pipeline results against ground truth data."""
    
    def __init__(self, db_path: str = "biopartnering_insights.db", 
                 ground_truth_path: str = "data/Pipeline_Ground_Truth.xlsx"):
        self.db_path = db_path
        self.ground_truth_path = ground_truth_path
        self.gt_df = None
        self.pipeline_data = {}
        self.validation_results = {}
        
    def load_ground_truth(self) -> pd.DataFrame:
        """Load and preprocess ground truth data."""
        try:
            self.gt_df = pd.read_excel(self.ground_truth_path)
            logger.info(f"Loaded ground truth: {len(self.gt_df)} drugs from {self.gt_df['Partner'].nunique()} companies")
            return self.gt_df
        except Exception as e:
            logger.error(f"Failed to load ground truth: {e}")
            raise
    
    def load_pipeline_data(self) -> Dict[str, Any]:
        """Load current pipeline data from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Load drugs
            drugs_df = pd.read_sql_query("""
                SELECT d.generic_name, d.brand_name, d.drug_class, d.mechanism_of_action, 
                       d.fda_approval_status, d.fda_approval_date, c.name as company
                FROM drugs d 
                LEFT JOIN companies c ON d.company_id = c.id
            """, conn)
            
            # Load clinical trials
            trials_df = pd.read_sql_query("""
                SELECT ct.nct_id, ct.title, ct.status, ct.phase, d.generic_name as drug_name
                FROM clinical_trials ct
                LEFT JOIN drugs d ON ct.drug_id = d.id
            """, conn)
            
            # Load targets
            targets_df = pd.read_sql_query("""
                SELECT t.name as target_name, d.generic_name as drug_name
                FROM targets t
                JOIN drug_targets dt ON t.id = dt.target_id
                JOIN drugs d ON dt.drug_id = d.id
            """, conn)
            
            conn.close()
            
            self.pipeline_data = {
                'drugs': drugs_df,
                'clinical_trials': trials_df,
                'targets': targets_df
            }
            
            logger.info(f"Loaded pipeline data: {len(drugs_df)} drugs, {len(trials_df)} trials, {len(targets_df)} target relationships")
            return self.pipeline_data
            
        except Exception as e:
            logger.error(f"Failed to load pipeline data: {e}")
            raise
    
    def validate_drug_names(self) -> Dict[str, Any]:
        """Validate drug name extraction accuracy."""
        if self.gt_df is None or 'drugs' not in self.pipeline_data:
            raise ValueError("Must load ground truth and pipeline data first")
        
        gt_drugs = set(self.gt_df['Generic name'].dropna().str.strip().str.lower())
        pipeline_drugs = set(self.pipeline_data['drugs']['generic_name'].dropna().str.strip().str.lower())
        
        # Find matches and mismatches
        matches = gt_drugs.intersection(pipeline_drugs)
        missing_from_pipeline = gt_drugs - pipeline_drugs
        extra_in_pipeline = pipeline_drugs - gt_drugs
        
        # Calculate metrics
        precision = len(matches) / len(pipeline_drugs) if len(pipeline_drugs) > 0 else 0
        recall = len(matches) / len(gt_drugs) if len(gt_drugs) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        results = {
            'metric': 'drug_names',
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'matches': len(matches),
            'missing_from_pipeline': list(missing_from_pipeline),
            'extra_in_pipeline': list(extra_in_pipeline),
            'total_gt_drugs': len(gt_drugs),
            'total_pipeline_drugs': len(pipeline_drugs)
        }
        
        logger.info(f"Drug name validation: Precision={precision:.3f}, Recall={recall:.3f}, F1={f1_score:.3f}")
        return results
    
    def validate_company_coverage(self) -> Dict[str, Any]:
        """Validate company coverage against ground truth."""
        if self.gt_df is None or 'drugs' not in self.pipeline_data:
            raise ValueError("Must load ground truth and pipeline data first")
        
        gt_companies = set(self.gt_df['Partner'].dropna().str.strip().str.lower())
        pipeline_companies = set(self.pipeline_data['drugs']['company'].dropna().str.strip().str.lower())
        
        # Find matches and mismatches
        matches = gt_companies.intersection(pipeline_companies)
        missing_from_pipeline = gt_companies - pipeline_companies
        extra_in_pipeline = pipeline_companies - gt_companies
        
        # Calculate metrics
        precision = len(matches) / len(pipeline_companies) if len(pipeline_companies) > 0 else 0
        recall = len(matches) / len(gt_companies) if len(gt_companies) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        results = {
            'metric': 'company_coverage',
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'matches': len(matches),
            'missing_from_pipeline': list(missing_from_pipeline),
            'extra_in_pipeline': list(extra_in_pipeline),
            'total_gt_companies': len(gt_companies),
            'total_pipeline_companies': len(pipeline_companies)
        }
        
        logger.info(f"Company coverage validation: Precision={precision:.3f}, Recall={recall:.3f}, F1={f1_score:.3f}")
        return results
    
    def validate_mechanisms(self) -> Dict[str, Any]:
        """Validate mechanism extraction accuracy."""
        if self.gt_df is None or 'drugs' not in self.pipeline_data:
            raise ValueError("Must load ground truth and pipeline data first")
        
        # Create drug-mechanism mapping from ground truth
        gt_mechanisms = {}
        for _, row in self.gt_df.iterrows():
            if pd.notna(row['Generic name']) and pd.notna(row['Mechanism']):
                drug = row['Generic name'].strip().lower()
                mechanism = row['Mechanism'].strip()
                gt_mechanisms[drug] = mechanism
        
        # Create drug-mechanism mapping from pipeline
        pipeline_mechanisms = {}
        for _, row in self.pipeline_data['drugs'].iterrows():
            if pd.notna(row['generic_name']) and pd.notna(row['mechanism_of_action']):
                drug = row['generic_name'].strip().lower()
                mechanism = row['mechanism_of_action'].strip()
                pipeline_mechanisms[drug] = mechanism
        
        # Find common drugs and compare mechanisms
        common_drugs = set(gt_mechanisms.keys()).intersection(set(pipeline_mechanisms.keys()))
        
        exact_matches = 0
        partial_matches = 0
        mismatches = []
        
        for drug in common_drugs:
            gt_mech = gt_mechanisms[drug].lower()
            pipe_mech = pipeline_mechanisms[drug].lower()
            
            if gt_mech == pipe_mech:
                exact_matches += 1
            elif any(word in pipe_mech for word in gt_mech.split() if len(word) > 3):
                partial_matches += 1
            else:
                mismatches.append({
                    'drug': drug,
                    'ground_truth': gt_mechanisms[drug],
                    'pipeline': pipeline_mechanisms[drug]
                })
        
        # Calculate metrics
        total_common = len(common_drugs)
        accuracy = (exact_matches + partial_matches * 0.5) / total_common if total_common > 0 else 0
        
        results = {
            'metric': 'mechanisms',
            'accuracy': accuracy,
            'exact_matches': exact_matches,
            'partial_matches': partial_matches,
            'mismatches': len(mismatches),
            'total_common_drugs': total_common,
            'mismatch_details': mismatches[:10]  # Limit to first 10 for readability
        }
        
        logger.info(f"Mechanism validation: Accuracy={accuracy:.3f}, Exact={exact_matches}, Partial={partial_matches}")
        return results
    
    def validate_clinical_trials(self) -> Dict[str, Any]:
        """Validate clinical trial coverage."""
        if self.gt_df is None or 'clinical_trials' not in self.pipeline_data:
            raise ValueError("Must load ground truth and pipeline data first")
        
        # Count trials per drug in ground truth
        gt_trial_counts = {}
        for _, row in self.gt_df.iterrows():
            if pd.notna(row['Generic name']) and pd.notna(row['Current Clinical Trials']):
                drug = row['Generic name'].strip().lower()
                trials_text = row['Current Clinical Trials']
                # Simple count based on separators (assuming | or ; separation)
                trial_count = len([t.strip() for t in trials_text.split('|') if t.strip()])
                gt_trial_counts[drug] = trial_count
        
        # Count trials per drug in pipeline
        pipeline_trial_counts = self.pipeline_data['clinical_trials'].groupby('drug_name').size().to_dict()
        
        # Compare trial coverage
        common_drugs = set(gt_trial_counts.keys()).intersection(set(pipeline_trial_counts.keys()))
        
        coverage_analysis = []
        for drug in common_drugs:
            gt_count = gt_trial_counts[drug]
            pipe_count = pipeline_trial_counts.get(drug, 0)
            coverage_ratio = pipe_count / gt_count if gt_count > 0 else 0
            
            coverage_analysis.append({
                'drug': drug,
                'gt_trials': gt_count,
                'pipeline_trials': pipe_count,
                'coverage_ratio': coverage_ratio
            })
        
        # Calculate overall metrics
        total_gt_trials = sum(gt_trial_counts.values())
        total_pipeline_trials = sum(pipeline_trial_counts.values())
        overall_coverage = total_pipeline_trials / total_gt_trials if total_gt_trials > 0 else 0
        
        results = {
            'metric': 'clinical_trials',
            'overall_coverage': overall_coverage,
            'total_gt_trials': total_gt_trials,
            'total_pipeline_trials': total_pipeline_trials,
            'common_drugs_analyzed': len(common_drugs),
            'coverage_analysis': coverage_analysis[:10]  # Limit to first 10
        }
        
        logger.info(f"Clinical trial validation: Overall coverage={overall_coverage:.3f}")
        return results
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        logger.info("Starting full ground truth validation...")
        
        # Load data
        self.load_ground_truth()
        self.load_pipeline_data()
        
        # Run all validations
        validations = [
            self.validate_drug_names(),
            self.validate_company_coverage(),
            self.validate_mechanisms(),
            self.validate_clinical_trials()
        ]
        
        # Compile results
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'validations': {v['metric']: v for v in validations},
            'summary': self._generate_summary(validations)
        }
        
        logger.info("Ground truth validation completed")
        return self.validation_results
    
    def _generate_summary(self, validations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate validation summary."""
        summary = {
            'total_validations': len(validations),
            'overall_health': 'Good',
            'key_metrics': {},
            'recommendations': []
        }
        
        # Extract key metrics
        for validation in validations:
            metric = validation['metric']
            if 'f1_score' in validation:
                summary['key_metrics'][f'{metric}_f1'] = validation['f1_score']
            elif 'accuracy' in validation:
                summary['key_metrics'][f'{metric}_accuracy'] = validation['accuracy']
            elif 'overall_coverage' in validation:
                summary['key_metrics'][f'{metric}_coverage'] = validation['overall_coverage']
        
        # Generate recommendations
        if 'drug_names' in summary['key_metrics'] and summary['key_metrics']['drug_names_f1'] < 0.8:
            summary['recommendations'].append("Improve drug name extraction - F1 score below 0.8")
        
        if 'mechanisms' in summary['key_metrics'] and summary['key_metrics']['mechanisms_accuracy'] < 0.7:
            summary['recommendations'].append("Improve mechanism extraction - accuracy below 0.7")
        
        if 'clinical_trials' in summary['key_metrics'] and summary['key_metrics']['clinical_trials_coverage'] < 0.5:
            summary['recommendations'].append("Improve clinical trial collection - coverage below 0.5")
        
        return summary
    
    def save_results(self, output_path: str = "outputs/validation_results.json"):
        """Save validation results to file."""
        if not self.validation_results:
            raise ValueError("No validation results to save. Run validation first.")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        
        logger.info(f"Validation results saved to {output_path}")
    
    def generate_report(self) -> str:
        """Generate human-readable validation report."""
        if not self.validation_results:
            raise ValueError("No validation results available. Run validation first.")
        
        report = []
        report.append("=" * 60)
        report.append("GROUND TRUTH VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {self.validation_results['timestamp']}")
        report.append("")
        
        # Summary
        summary = self.validation_results['summary']
        report.append("SUMMARY")
        report.append("-" * 20)
        report.append(f"Overall Health: {summary['overall_health']}")
        report.append(f"Total Validations: {summary['total_validations']}")
        report.append("")
        
        # Key Metrics
        report.append("KEY METRICS")
        report.append("-" * 20)
        for metric, value in summary['key_metrics'].items():
            report.append(f"{metric}: {value:.3f}")
        report.append("")
        
        # Detailed Results
        report.append("DETAILED RESULTS")
        report.append("-" * 20)
        for metric, results in self.validation_results['validations'].items():
            report.append(f"\n{metric.upper()}:")
            if 'precision' in results:
                report.append(f"  Precision: {results['precision']:.3f}")
                report.append(f"  Recall: {results['recall']:.3f}")
                report.append(f"  F1 Score: {results['f1_score']:.3f}")
            if 'accuracy' in results:
                report.append(f"  Accuracy: {results['accuracy']:.3f}")
            if 'overall_coverage' in results:
                report.append(f"  Coverage: {results['overall_coverage']:.3f}")
            
            if 'missing_from_pipeline' in results and results['missing_from_pipeline']:
                report.append(f"  Missing from pipeline: {len(results['missing_from_pipeline'])} items")
                if len(results['missing_from_pipeline']) <= 5:
                    report.append(f"    {results['missing_from_pipeline']}")
        
        # Recommendations
        if summary['recommendations']:
            report.append("\nRECOMMENDATIONS")
            report.append("-" * 20)
            for i, rec in enumerate(summary['recommendations'], 1):
                report.append(f"{i}. {rec}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


