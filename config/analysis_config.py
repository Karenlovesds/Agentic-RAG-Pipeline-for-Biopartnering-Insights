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
        'Partner': 'Company',
        'Tickets': 'Tickets'
    }
    
    # Required columns for analysis
    REQUIRED_COLUMNS = [
        'Generic Name', 'Brand Name', 'FDA Approval', 'Drug Class', 
        'Target', 'Mechanism', 'Indication Approved', 'Current Clinical Trials',
        'Company', 'Tickets'
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
        'ticket_volume': 0.4,        # 40% weight on ticket volume
        'drug_portfolio': 0.3,       # 30% weight on drug portfolio
        'fda_approvals': 0.2,        # 20% weight on FDA approvals
        'target_diversity': 0.1      # 10% weight on target diversity
    }
    
    # Time allocation configuration
    TIME_ALLOCATION = {
        'total_hours': 60,           # Total hours for allocation
        'base_hours_tickets': 40,    # Base hours based on ticket volume
        'adjustment_hours_priority': 20  # Adjustment hours based on priority
    }
    
    # Efficiency thresholds (configurable)
    EFFICIENCY_THRESHOLDS = {
        'high_demand_low_portfolio': 20,  # 20+ tickets per drug
        'medium_demand_low_portfolio': 10, # 10+ tickets per drug
        'balanced': 5,                     # 5+ tickets per drug
        'high_portfolio_low_demand': 5     # <5 tickets per drug
    }
    
    # Quantile thresholds for priority categorization
    PRIORITY_QUANTILES = {
        'high_priority': 0.7,        # Top 30% by priority score
        'medium_priority': 0.4,      # Middle 30% by priority score
        'low_priority': 0.4          # Bottom 40% by priority score
    }
    
    # Quantile thresholds for efficiency analysis
    EFFICIENCY_QUANTILES = {
        'high_efficiency': 0.8,      # Top 20% by tickets per drug
        'underutilized': 0.2         # Bottom 20% by tickets per drug
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
    
    @classmethod
    def get_efficiency_category(cls, tickets_per_drug: float) -> str:
        """
        Get efficiency category based on tickets per drug ratio.
        
        Args:
            tickets_per_drug: Ratio of tickets to drugs
            
        Returns:
            str: Efficiency category
        """
        if tickets_per_drug > cls.EFFICIENCY_THRESHOLDS['high_demand_low_portfolio']:
            return "High Demand, Low Portfolio"
        elif tickets_per_drug > cls.EFFICIENCY_THRESHOLDS['medium_demand_low_portfolio']:
            return "Medium Demand, Low Portfolio"
        elif tickets_per_drug > cls.EFFICIENCY_THRESHOLDS['balanced']:
            return "Balanced"
        else:
            return "High Portfolio, Low Demand"
    
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
