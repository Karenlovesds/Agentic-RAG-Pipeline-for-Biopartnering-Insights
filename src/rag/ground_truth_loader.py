"""
Ground Truth Data Loader for RAG Integration

This module provides access to ground truth data for enhanced RAG responses,
including business context, validated drug information, and priority scoring.
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.validation_config import GROUND_TRUTH_PATH


class GroundTruthLoader:
    """Loader for ground truth data with business context."""
    
    def __init__(self):
        self.ground_truth_path = GROUND_TRUTH_PATH
        self._data = None
        self._load_data()
    
    def _load_data(self):
        """Load ground truth data from Excel file."""
        try:
            usecols = [
                'Generic name', 'Brand name', 'Company', 'Target', 'Mechanism',
                'Drug Class', 'Indication Approved', 'Current Clinical Trials', 'FDA Approval'
            ]
            self._data = pd.read_excel(self.ground_truth_path, usecols=usecols)
            logger.info(f"Loaded ground truth data: {len(self._data)} records")
        except Exception as e:
            logger.error(f"Failed to load ground truth data: {e}")
            self._data = pd.DataFrame()
    
    def search_drugs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for drugs in ground truth data."""
        if self._data.empty:
            return []
        
        query_lower = query.lower()
        results = []
        
        # Search in generic name, brand name, and indication
        for _, row in self._data.iterrows():
            score = 0
            match_fields = []
            
            # Check generic name
            if pd.notna(row['Generic name']) and query_lower in str(row['Generic name']).lower():
                score += 100
                match_fields.append('generic_name')
            
            # Check brand name
            if pd.notna(row['Brand name']) and query_lower in str(row['Brand name']).lower():
                score += 90
                match_fields.append('brand_name')
            
            # Check indication
            if pd.notna(row['Indication Approved']) and query_lower in str(row['Indication Approved']).lower():
                score += 80
                match_fields.append('indication')
            
            # Check target
            if pd.notna(row['Target']) and query_lower in str(row['Target']).lower():
                score += 70
                match_fields.append('target')
            
            # Check mechanism
            if pd.notna(row['Mechanism']) and query_lower in str(row['Mechanism']).lower():
                score += 60
                match_fields.append('mechanism')
            
            # Check drug class
            if pd.notna(row['Drug Class']) and query_lower in str(row['Drug Class']).lower():
                score += 50
                match_fields.append('drug_class')
            
            # Check company
            if pd.notna(row['Company']) and query_lower in str(row['Company']).lower():
                score += 40
                match_fields.append('company')
            
            if score > 0:
                results.append({
                    'source': 'ground_truth',
                    'score': score,
                    'match_fields': match_fields,
                    'company': row['Company'],
                    # 'tickets': row['Tickets'],  # Commented out - Tickets column not needed
                    'generic_name': row['Generic name'],
                    'brand_name': row['Brand name'],
                    'fda_approval': row['FDA Approval'],
                    'drug_class': row['Drug Class'],
                    'target': row['Target'],
                    'mechanism': row['Mechanism'],
                    'indication_approved': row['Indication Approved'],
                    'current_clinical_trials': row['Current Clinical Trials'],
                    # 'business_priority': self._calculate_business_priority(row['Tickets']),  # Commented out - Tickets column not needed
                    'data_quality': 'validated'
                })
        
        # Sort by score and return top results
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    def search_companies(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for companies in ground truth data."""
        if self._data.empty:
            return []
        
        query_lower = query.lower()
        results = []
        
        # Group by company to get company-level insights
        company_data = self._data.groupby('Company').agg({
            # 'Tickets': 'sum',  # Commented out - Tickets column not needed
            'Generic name': 'count',
            'FDA Approval': lambda x: (x.notna()).sum(),
            'Target': lambda x: x.nunique(),
            'Drug Class': lambda x: x.nunique()
        }).reset_index()
        
        company_data.columns = ['company', 'drug_count', 'fda_approved_count', 'unique_targets', 'unique_drug_classes']
        
        for _, row in company_data.iterrows():
            if query_lower in str(row['company']).lower():
                # Get company's drug portfolio
                company_drugs = self._data[self._data['Company'] == row['company']]
                
                results.append({
                    'source': 'ground_truth',
                    'company': row['company'],
                    'drug_count': row['drug_count'],
                    'fda_approved_count': row['fda_approved_count'],
                    'unique_targets': row['unique_targets'],
                    'unique_drug_classes': row['unique_drug_classes'],
                    'drug_portfolio': company_drugs[['Generic name', 'Brand name', 'FDA Approval', 'Target', 'Drug Class']].to_dict('records'),
                    'data_quality': 'validated'
                })
        
        # Sort by drug count (removed tickets-based sorting)
        results.sort(key=lambda x: x['drug_count'], reverse=True)
        return results[:limit]
    
    def search_targets(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for targets in ground truth data."""
        if self._data.empty:
            return []
        
        query_lower = query.lower()
        results = []
        
        # Group by target to get target-level insights
        target_data = self._data.groupby('Target').agg({
            'Generic name': 'count',
            'Company': 'nunique',
            'FDA Approval': lambda x: (x.notna()).sum(),
            # 'Tickets': 'sum'  # Commented out - Tickets column not needed
        }).reset_index()
        
        target_data.columns = ['target', 'drug_count', 'company_count', 'fda_approved_count']
        
        for _, row in target_data.iterrows():
            if pd.notna(row['target']) and query_lower in str(row['target']).lower():
                # Get drugs targeting this target
                target_drugs = self._data[self._data['Target'] == row['target']]
                
                results.append({
                    'source': 'ground_truth',
                    'target': row['target'],
                    'drug_count': row['drug_count'],
                    'company_count': row['company_count'],
                    'fda_approved_count': row['fda_approved_count'],
                    # 'total_tickets': row['total_tickets'],  # Commented out - Tickets column not needed
                    # 'business_priority': self._calculate_business_priority(row['total_tickets']),  # Commented out - Tickets column not needed
                    'targeting_drugs': target_drugs[['Generic name', 'Brand name', 'Company', 'FDA Approval', 'Mechanism']].to_dict('records'),
                    'data_quality': 'validated'
                })
        
        # Sort by drug count (removed tickets-based sorting)
        results.sort(key=lambda x: x['drug_count'], reverse=True)
        return results[:limit]
    
    def get_business_context(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Get business context for a specific company."""
        if self._data.empty:
            return None
        
        company_data = self._data[self._data['Company'].str.contains(company_name, case=False, na=False)]
        
        if company_data.empty:
            return None
        
        return {
            'company': company_name,
            # 'total_tickets': company_data['Tickets'].sum(),  # Commented out - Tickets column not needed
            'drug_count': len(company_data),
            'fda_approved_count': company_data['FDA Approval'].notna().sum(),
            'unique_targets': company_data['Target'].nunique(),
            # 'business_priority': self._calculate_business_priority(company_data['Tickets'].sum()),  # Commented out - Tickets column not needed
            'drug_portfolio': company_data[['Generic name', 'Brand name', 'FDA Approval', 'Target', 'Drug Class']].to_dict('records'),
            'data_quality': 'validated'
        }
    
    def validate_pipeline_data(self, pipeline_drugs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate pipeline data against ground truth."""
        if self._data.empty:
            return {'validation_status': 'no_ground_truth', 'matches': [], 'discrepancies': []}
        
        matches = []
        discrepancies = []
        
        for drug in pipeline_drugs:
            drug_name = drug.get('generic_name', '').lower()
            
            # Find matching ground truth entry
            gt_match = self._data[
                self._data['Generic name'].str.lower().str.contains(drug_name, na=False)
            ]
            
            if not gt_match.empty:
                gt_row = gt_match.iloc[0]
                matches.append({
                    'pipeline_drug': drug,
                    'ground_truth': gt_row.to_dict(),
                    'match_quality': 'exact' if drug_name == gt_row['Generic name'].lower() else 'partial'
                })
            else:
                discrepancies.append({
                    'pipeline_drug': drug,
                    'issue': 'not_in_ground_truth'
                })
        
        return {
            'validation_status': 'completed',
            'total_pipeline_drugs': len(pipeline_drugs),
            'matches': matches,
            'discrepancies': discrepancies,
            'match_rate': len(matches) / len(pipeline_drugs) if pipeline_drugs else 0
        }
