"""
Analysis Configuration

This module contains configuration settings for the analysis dashboards
to make them flexible and adaptable to different ground truth table formats.
"""

from typing import Dict, List, Optional
from pathlib import Path


class AnalysisConfig:
    """Configuration class for analysis dashboards."""
    
    # Ground Truth file configuration
    GROUND_TRUTH_FILE = "data/Pipeline_Ground_Truth.xlsx"
    
    # Column mapping for ground truth data
    COLUMN_MAPPING = {
        'Generic name': 'Generic Name',
        'Brand name': 'Brand Name', 
        'FDA Approval': 'FDA Approval',
        'Drug Class': 'Drug Class',
        'Target': 'Target',
        'Mechanism': 'Mechanism',
        'Indication Approved': 'Indication Approved',
        'Current Clinical Trials': 'Current Clinical Trials',
        'Partner': 'Company'
    }
    
    # Required columns for analysis
    REQUIRED_COLUMNS = [
        'Generic Name', 'Brand Name', 'FDA Approval', 'Drug Class', 
        'Target', 'Mechanism', 'Indication Approved', 'Current Clinical Trials',
        'Company'
    ]
    
    # Competition level thresholds (configurable)
    COMPETITION_THRESHOLDS = {
        'high_competition': 10,      # 10+ drugs
        'medium_competition': 5,     # 5-9 drugs  
        'low_competition': 2,        # 2-4 drugs
        'single_drug': 1             # 1 drug
    }
    
    # Priority scoring weights (configurable)
    PRIORITY_WEIGHTS = {
        'drug_portfolio': 0.4,       # 40% weight on drug portfolio
        'fda_approvals': 0.3,        # 30% weight on FDA approvals
        'target_diversity': 0.2,     # 20% weight on target diversity
        'clinical_trials': 0.1       # 10% weight on clinical trials
    }
    
    # Priority scoring thresholds (configurable)
    PRIORITY_QUANTILES = {
        'high_priority': 0.7,        # Top 30% by priority score
        'medium_priority': 0.4,      # Middle 30% by priority score
        'low_priority': 0.4          # Bottom 40% by priority score
    }
    
    # Market saturation thresholds
    SATURATION_THRESHOLDS = {
        'high_saturation': 50,       # >50% of drugs target highly competitive areas
        'moderate_saturation': 30,   # 30-50% of drugs target highly competitive areas
        'low_saturation': 30         # <30% of drugs target highly competitive areas
    }
    
    # Chart display limits
    CHART_LIMITS = {
        'top_targets': 10,
        'top_drug_classes': 10,
        'top_mechanisms': 10,
        'top_companies': 10,
        'pie_chart_items': 8,
        'histogram_bins': 20
    }
    
    @classmethod
    def validate_ground_truth_data(cls, df) -> tuple[bool, List[str]]:
        """
        Validate that the ground truth data contains all required columns.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            tuple: (is_valid, missing_columns)
        """
        missing_columns = []
        for col in cls.REQUIRED_COLUMNS:
            if col not in df.columns:
                missing_columns.append(col)
        
        return len(missing_columns) == 0, missing_columns
    
    @classmethod
    def get_competition_level(cls, drug_count: int) -> str:
        """
        Get competition level based on drug count.
        
        Args:
            drug_count: Number of drugs for a target
            
        Returns:
            str: Competition level category
        """
        if drug_count >= cls.COMPETITION_THRESHOLDS['high_competition']:
            return "High Competition (10+ drugs)"
        elif drug_count >= cls.COMPETITION_THRESHOLDS['medium_competition']:
            return "Medium Competition (5-9 drugs)"
        elif drug_count >= cls.COMPETITION_THRESHOLDS['low_competition']:
            return "Low Competition (2-4 drugs)"
        else:
            return "Single Drug (1 drug)"
    
    # Removed get_efficiency_category - was based on ticket analysis
    @classmethod
    def get_saturation_status(cls, saturation_rate: float) -> tuple[str, str]:
        """
        Get market saturation status and recommendation.
        
        Args:
            saturation_rate: Percentage of drugs targeting highly competitive areas
            
        Returns:
            tuple: (status, recommendation)
        """
        if saturation_rate > cls.SATURATION_THRESHOLDS['high_saturation']:
            return "High", "⚠️ **High Market Saturation**: More than 50% of drugs target highly competitive areas. Consider exploring less saturated targets."
        elif saturation_rate > cls.SATURATION_THRESHOLDS['moderate_saturation']:
            return "Moderate", "ℹ️ **Moderate Market Saturation**: Some targets are highly competitive. Balance between proven targets and emerging opportunities."
        else:
            return "Low", "✅ **Low Market Saturation**: Good distribution across targets. Many opportunities for innovation."
