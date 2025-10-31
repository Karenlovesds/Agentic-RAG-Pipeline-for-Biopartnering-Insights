"""
Ground Truth Dashboard

This module provides a dedicated dashboard for viewing and analyzing ground truth data.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
import json
from pathlib import Path


def load_ground_truth_data() -> pd.DataFrame:
    """Load and preprocess ground truth data."""
    try:
        gt_df = pd.read_excel("data/Pipeline_Ground_Truth.xlsx")
        
        # Fix data type issues for Streamlit display
        gt_df['FDA Approval'] = gt_df['FDA Approval'].astype(str)
        
        # Clean up FDA approval date format
        def clean_fda_date(date_str):
            if pd.isna(date_str) or date_str == 'nan' or date_str == '':
                return ''
            # Remove time component if present
            if ' ' in str(date_str):
                return str(date_str).split(' ')[0]
            return str(date_str)
        
        gt_df['FDA Approval'] = gt_df['FDA Approval'].apply(clean_fda_date)
        
        return gt_df
    except Exception as e:
        st.error(f"Error loading ground truth data: {e}")
        return pd.DataFrame()


def display_ground_truth_table():
    """Display ground truth table with comprehensive filtering."""
    st.subheader("📋 Ground Truth Data Table")
    
    gt_df = load_ground_truth_data()
    if gt_df.empty:
        return
    
    st.write(f"**Loaded {len(gt_df)} drugs from ground truth data**")
    
    # Create comprehensive filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Company filter
        companies = ['All'] + sorted(gt_df['Company'].dropna().unique().tolist())
        selected_company = st.selectbox("Filter by Company", companies, key="gt_company_filter")
        
    with col2:
        # Drug class filter
        drug_classes = ['All'] + sorted(gt_df['Drug Class'].dropna().unique().tolist())
        selected_drug_class = st.selectbox("Filter by Drug Class", drug_classes, key="gt_drug_class_filter")
        
    with col3:
        # Target filter
        targets = ['All'] + sorted(gt_df['Target'].dropna().unique().tolist())
        selected_target = st.selectbox("Filter by Target", targets, key="gt_target_filter")
        
    with col4:
        # FDA approval filter
        fda_options = ['All', 'FDA Approved', 'Not FDA Approved', 'Unknown']
        selected_fda = st.selectbox("Filter by FDA Status", fda_options, key="gt_fda_filter")
    
    # Additional filters
    col5, col6 = st.columns(2)
    
    with col5:
        # Mechanism filter
        mechanisms = ['All'] + sorted(gt_df['Mechanism'].dropna().unique().tolist())
        selected_mechanism = st.selectbox("Filter by Mechanism", mechanisms, key="gt_mechanism_filter")
    
    with col6:
        # Indication filter
        indications = ['All'] + sorted(gt_df['Indication Approved'].dropna().unique().tolist())
        selected_indication = st.selectbox("Filter by Indication", indications, key="gt_indication_filter")
    
    # Apply filters
    filtered_df = gt_df.copy()
    
    if selected_company != 'All':
        filtered_df = filtered_df[filtered_df['Company'] == selected_company]
        
    if selected_drug_class != 'All':
        filtered_df = filtered_df[filtered_df['Drug Class'] == selected_drug_class]
        
    if selected_target != 'All':
        filtered_df = filtered_df[filtered_df['Target'] == selected_target]
        
    if selected_mechanism != 'All':
        filtered_df = filtered_df[filtered_df['Mechanism'] == selected_mechanism]
        
    if selected_indication != 'All':
        filtered_df = filtered_df[filtered_df['Indication Approved'] == selected_indication]
        
    if selected_fda == 'FDA Approved':
        filtered_df = filtered_df[filtered_df['FDA Approval'].notna()]
    elif selected_fda == 'Not FDA Approved':
        filtered_df = filtered_df[filtered_df['FDA Approval'].isna()]
    elif selected_fda == 'Unknown':
        filtered_df = filtered_df[filtered_df['FDA Approval'].isna()]
    
    # Display summary
    st.write(f"**Showing {len(filtered_df)} of {len(gt_df)} drugs**")
    
    # Show filter summary
    active_filters = []
    if selected_company != 'All':
        active_filters.append(f"Company: {selected_company}")
    if selected_drug_class != 'All':
        active_filters.append(f"Drug Class: {selected_drug_class}")
    if selected_target != 'All':
        active_filters.append(f"Target: {selected_target}")
    if selected_mechanism != 'All':
        active_filters.append(f"Mechanism: {selected_mechanism}")
    if selected_indication != 'All':
        active_filters.append(f"Indication: {selected_indication}")
    if selected_fda != 'All':
        active_filters.append(f"FDA Status: {selected_fda}")
    
    if active_filters:
        st.write(f"**Active filters:** {', '.join(active_filters)}")
    
    # Display table
    if len(filtered_df) > 0:
        # Select columns to display
        display_columns = [
            'Company', 'Generic name', 'Brand name', 'FDA Approval', 
            'Drug Class', 'Target', 'Mechanism', 'Indication Approved', 
            'Current Clinical Trials'
        ]
        
        # Filter columns that exist
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        display_df = filtered_df[available_columns]
        
        # Rename columns for better display
        column_mapping = {
            'Company': 'Company',
            'Generic name': 'Generic Name',
            'Brand name': 'Brand Name',
            'FDA Approval': 'FDA Approval',
            'Drug Class': 'Drug Class',
            'Target': 'Target',
            'Mechanism': 'Mechanism',
            'Indication Approved': 'Indication Approved',
            'Current Clinical Trials': 'Clinical Trials'
        }
        
        display_df = display_df.rename(columns=column_mapping)
        
        # Display all data without pagination
        st.dataframe(
            display_df,
            use_container_width=True,
            height=700
        )
            
    else:
        st.warning("No data matches the selected filters.")


def display_ground_truth_analytics():
    """Display ground truth analytics and insights."""
    st.subheader("📊 Ground Truth Analytics")
    
    gt_df = load_ground_truth_data()
    if gt_df.empty:
        return
    
    # Create analytics tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview", "Company Analysis", "Target Analysis", "Drug Analysis", "Trial Analysis"
    ])
    
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Drugs", len(gt_df))
        with col2:
            st.metric("Total Companies", gt_df['Company'].nunique())
        with col3:
            st.metric("FDA Approved", len(gt_df[gt_df['FDA Approval'].notna()]))
        with col4:
            st.metric("Unique Targets", gt_df['Target'].nunique())
        
        # Quick stats
        st.write("**Data Completeness**")
        completeness = {
            'Brand Name': (gt_df['Brand name'].notna().sum() / len(gt_df) * 100).round(1),
            'Drug Class': (gt_df['Drug Class'].notna().sum() / len(gt_df) * 100).round(1),
            'Target': (gt_df['Target'].notna().sum() / len(gt_df) * 100).round(1),
            'Mechanism': (gt_df['Mechanism'].notna().sum() / len(gt_df) * 100).round(1),
            'Indication': (gt_df['Indication Approved'].notna().sum() / len(gt_df) * 100).round(1),
            'Clinical Trials': (gt_df['Current Clinical Trials'].notna().sum() / len(gt_df) * 100).round(1)
        }
        
        completeness_df = pd.DataFrame(list(completeness.items()), columns=['Field', 'Completeness %'])
        st.bar_chart(completeness_df.set_index('Field'))
    
    with tab2:
        st.write("**Company Distribution**")
        company_counts = gt_df['Company'].value_counts()
        st.bar_chart(company_counts)
        
        st.write("**Company Drug Counts**")
        st.dataframe(company_counts, use_container_width=True)
    
    with tab3:
        st.write("**Target Distribution**")
        targets = gt_df['Target'].dropna()
        target_counts = targets.value_counts()
        st.bar_chart(target_counts.head(15))
        
        st.write("**Top Targets**")
        st.dataframe(target_counts.head(10), use_container_width=True)
    
    with tab4:
        st.write("**Drug Class Distribution**")
        drug_class_counts = gt_df['Drug Class'].value_counts().head(10)
        st.bar_chart(drug_class_counts)
        
        st.write("**FDA Approval Status**")
        fda_status = gt_df['FDA Approval'].notna().value_counts()
        st.bar_chart(fda_status)
    
    with tab5:
        st.write("**Clinical Trial Analysis**")
        # Count trials per drug (rough estimate based on separators)
        trial_counts = gt_df['Current Clinical Trials'].dropna().apply(
            lambda x: len([t.strip() for t in str(x).split('|') if t.strip()]) if pd.notna(x) else 0
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Average trials per drug", f"{trial_counts.mean():.1f}")
        with col2:
            st.metric("Total estimated trials", trial_counts.sum())
        
        # Show drugs with most trials
        gt_df_with_trials = gt_df.copy()
        gt_df_with_trials['Trial Count'] = trial_counts
        top_trial_drugs = gt_df_with_trials.nlargest(10, 'Trial Count')[['Company', 'Generic name', 'Trial Count']]
        st.dataframe(top_trial_drugs, use_container_width=True)


def display_export_options():
    """Display export options for ground truth data."""
    st.subheader("📤 Export Options")
    
    gt_df = load_ground_truth_data()
    if gt_df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Export to CSV", type="primary"):
            csv = gt_df.to_csv(index=False)
            st.download_button(
                label="Download Ground Truth CSV",
                data=csv,
                file_name="ground_truth_data.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("Export to Excel"):
            try:
                import io
                # Create Excel file in memory
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    gt_df.to_excel(writer, sheet_name='Ground Truth', index=False)
                output.seek(0)
                
                st.download_button(
                    label="Download Ground Truth Excel",
                    data=output.getvalue(),
                    file_name="ground_truth_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except ImportError:
                st.error("openpyxl is required for Excel export. Please install it with: pip install openpyxl")


def main_ground_truth_dashboard():
    """Main ground truth dashboard function."""
    st.title("📋 Ground Truth Data")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Data Table", "Analytics", "Export"])
    
    with tab1:
        display_ground_truth_table()
    
    with tab2:
        display_ground_truth_analytics()
    
    with tab3:
        display_export_options()


