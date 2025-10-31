"""
Overlap Analysis Dashboard

This module provides Streamlit components for analyzing company overlap
between Ground Truth and Pipeline data for quality control purposes.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, List, Tuple
import json


def load_overlap_data() -> pd.DataFrame:
    """Load company overlap analysis data."""
    try:
        df = pd.read_csv("outputs/company_overlap_analysis.csv")
        return df
    except FileNotFoundError:
        st.error("Overlap analysis data not found. Please run the overlap analysis first.")
        return pd.DataFrame()


def display_overlap_summary(df: pd.DataFrame):
    """Display overlap summary metrics."""
    if df.empty:
        return
    
    st.subheader("📊 Overlap Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        exact_matches = len(df[df['match_type'] == 'exact'])
        st.metric("Exact Matches", exact_matches)
    
    with col2:
        partial_matches = len(df[df['match_type'] == 'partial'])
        st.metric("Partial Matches", partial_matches)
    
    with col3:
        total_drugs = df['drug_count'].sum()
        st.metric("Total Drugs", total_drugs)
    
    with col4:
        total_trials = df['trial_count'].sum()
        st.metric("Total Trials", total_trials)


def display_overlap_table(df: pd.DataFrame):
    """Display detailed overlap table."""
    st.subheader("🔍 Company Overlap Details")
    
    # Add quality indicators
    df_display = df.copy()
    df_display['Quality Score'] = df_display.apply(
        lambda row: '🟢 High' if row['drug_count'] > 10 else '🟡 Medium' if row['drug_count'] > 0 else '🔴 Low',
        axis=1
    )
    
    # Reorder columns (only include columns that exist)
    available_columns = ['ground_truth_company', 'pipeline_company', 'match_type', 'Quality Score', 'drug_count', 'trial_count']
    df_display = df_display[[col for col in available_columns if col in df_display.columns]]
    
    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "ground_truth_company": "Ground Truth Company",
            "pipeline_company": "Pipeline Company", 
            "match_type": "Match Type",
            "drug_count": "Drugs",
            "trial_count": "Trials"
        }
    )


def display_quality_analysis(df: pd.DataFrame):
    """Display data quality analysis for overlap companies."""
    st.subheader("📈 Data Quality Analysis")
    
    # Filter out companies with no data
    df_with_data = df[df['drug_count'] > 0]
    
    if df_with_data.empty:
        st.warning("No companies with data found in overlap analysis.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Drugs per company chart
        fig_drugs = px.bar(
            df_with_data.sort_values('drug_count', ascending=True),
            x='drug_count',
            y='pipeline_company',
            orientation='h',
            title="Drugs per Overlap Company",
            labels={'drug_count': 'Number of Drugs', 'pipeline_company': 'Company'}
        )
        fig_drugs.update_layout(height=400)
        st.plotly_chart(fig_drugs, use_container_width=True)
    
    with col2:
        # Trials per company chart
        fig_trials = px.bar(
            df_with_data.sort_values('trial_count', ascending=True),
            x='trial_count',
            y='pipeline_company',
            orientation='h',
            title="Clinical Trials per Overlap Company",
            labels={'trial_count': 'Number of Trials', 'pipeline_company': 'Company'}
        )
        fig_trials.update_layout(height=400)
        st.plotly_chart(fig_trials, use_container_width=True)


def display_match_type_analysis(df: pd.DataFrame):
    """Display analysis by match type."""
    st.subheader("🎯 Match Type Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Match type distribution
        match_counts = df['match_type'].value_counts()
        fig_pie = px.pie(
            values=match_counts.values,
            names=match_counts.index,
            title="Distribution of Match Types"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Data quality by match type
        quality_by_type = df.groupby('match_type').agg({
            'drug_count': ['sum', 'mean'],
            'trial_count': ['sum', 'mean'],
            # 'target_count': ['sum', 'mean']  # Column doesn't exist in current data
        }).round(1)
        
        st.write("**Data Quality by Match Type:**")
        st.dataframe(quality_by_type, use_container_width=True)


def display_quality_benchmarks(df: pd.DataFrame):
    """Display quality benchmarks for overlap companies."""
    st.subheader("🏆 Quality Benchmarks")
    
    # Calculate benchmarks
    benchmarks = {
        'Total Companies': len(df),
        'Companies with Drugs': len(df[df['drug_count'] > 0]),
        'Companies with Trials': len(df[df['trial_count'] > 0]),
        # 'Companies with Targets': len(df[df['target_count'] > 0]),  # Column doesn't exist
        'Average Drugs per Company': df['drug_count'].mean(),
        'Average Trials per Company': df['trial_count'].mean(),
        # 'Average Targets per Company': df['target_count'].mean(),  # Column doesn't exist
        'Total Drugs': df['drug_count'].sum(),
        'Total Trials': df['trial_count'].sum()
        # 'Total Targets': df['target_count'].sum()  # Column doesn't exist
    }
    
    # Display as metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Companies with Data", f"{benchmarks['Companies with Drugs']}/{benchmarks['Total Companies']}")
        st.metric("Avg Drugs/Company", f"{benchmarks['Average Drugs per Company']:.1f}")
    
    with col2:
        st.metric("Companies with Trials", f"{benchmarks['Companies with Trials']}/{benchmarks['Total Companies']}")
        st.metric("Avg Trials/Company", f"{benchmarks['Average Trials per Company']:.1f}")
    
    with col3:
        st.metric("Companies with Targets", f"{benchmarks.get('Companies with Targets', 0)}/{benchmarks['Total Companies']}")
        st.metric("Avg Targets/Company", "N/A")


def display_recommendations(df: pd.DataFrame):
    """Display recommendations based on overlap analysis."""
    st.subheader("💡 Recommendations")
    
    # Calculate insights
    total_companies = len(df)
    companies_with_data = len(df[df['drug_count'] > 0])
    data_coverage = (companies_with_data / total_companies) * 100 if total_companies > 0 else 0
    
    recommendations = []
    
    if data_coverage < 50:
        recommendations.append("🔴 **Low Data Coverage**: Less than 50% of overlap companies have drug data. Consider expanding data collection for these companies.")
    elif data_coverage < 80:
        recommendations.append("🟡 **Medium Data Coverage**: Some overlap companies lack data. Focus on improving data collection for companies with missing information.")
    else:
        recommendations.append("🟢 **Good Data Coverage**: Most overlap companies have comprehensive data. Use this as a quality benchmark for pipeline validation.")
    
    # Check for high-quality companies
    high_quality_companies = df[df['drug_count'] > 10]
    if len(high_quality_companies) > 0:
        recommendations.append(f"⭐ **High-Quality Companies**: {len(high_quality_companies)} companies have >10 drugs. Use these as quality standards for validation.")
    
    # Check for companies with trials
    companies_with_trials = df[df['trial_count'] > 0]
    if len(companies_with_trials) < len(df) * 0.3:
        recommendations.append("📊 **Limited Trial Data**: Few overlap companies have clinical trial data. Consider expanding trial collection for better validation.")
    
    # Display recommendations
    for i, rec in enumerate(recommendations, 1):
        st.write(f"{i}. {rec}")


def main_overlap_dashboard():
    """Main overlap analysis dashboard."""
    st.title("🔍 Company Overlap Analysis")
    st.markdown("Analyzing companies that exist in both Ground Truth and Pipeline data for quality control purposes.")
    
    # Load data
    df = load_overlap_data()
    
    if df.empty:
        st.error("No overlap data available. Please run the overlap analysis first.")
        return
    
    # Display sections
    display_overlap_summary(df)
    st.divider()
    
    display_overlap_table(df)
    st.divider()
    
    display_quality_analysis(df)
    st.divider()
    
    display_match_type_analysis(df)
    st.divider()
    
    display_quality_benchmarks(df)
    st.divider()
    
    display_recommendations(df)
