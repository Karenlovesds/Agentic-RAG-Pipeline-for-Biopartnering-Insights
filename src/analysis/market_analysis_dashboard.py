"""
Market Analysis Dashboard

This module provides market analysis using Ground Truth data as the primary source
for validated, high-quality market insights.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, List, Tuple
import json
import sys
sys.path.append('config')
from analysis_config import AnalysisConfig


def load_ground_truth_data() -> pd.DataFrame:
    """Load Ground Truth data for market analysis."""
    try:
        df = pd.read_excel(AnalysisConfig.GROUND_TRUTH_FILE)
        
        # Clean and prepare data using configuration
        df = df.rename(columns=AnalysisConfig.COLUMN_MAPPING)
        
        # Validate required columns
        is_valid, missing_columns = AnalysisConfig.validate_ground_truth_data(df)
        if not is_valid:
            st.error(f"Missing required columns in ground truth data: {missing_columns}")
            return pd.DataFrame()
        
        # Clean FDA approval dates
        df['FDA Approval'] = df['FDA Approval'].astype(str).apply(clean_fda_date)
        
        # Convert tickets to string
        df['Tickets'] = df['Tickets'].astype(str)
        
        return df
    except FileNotFoundError:
        st.error(f"Ground Truth file not found at {AnalysisConfig.GROUND_TRUTH_FILE}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading Ground Truth data: {e}")
        return pd.DataFrame()


def clean_fda_date(date_str):
    """Clean FDA approval date format."""
    if pd.isna(date_str) or date_str == 'nan' or date_str == '':
        return ''
    if ' ' in str(date_str):
        return str(date_str).split(' ')[0]
    return str(date_str)


def display_market_overview(df: pd.DataFrame):
    """Display market overview metrics."""
    st.subheader("📊 Market Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_drugs = len(df)
        st.metric("Total Drugs", total_drugs)
    
    with col2:
        unique_companies = df['Company'].nunique()
        st.metric("Companies", unique_companies)
    
    with col3:
        fda_approved = len(df[df['FDA Approval'] != ''])
        st.metric("FDA Approved", fda_approved)
    
    with col4:
        unique_targets = df['Target'].nunique()
        st.metric("Unique Targets", unique_targets)


def display_company_analysis(df: pd.DataFrame):
    """Display company market share analysis."""
    st.subheader("🏢 Company Market Analysis")
    
    # Company drug counts
    company_counts = df['Company'].value_counts().reset_index()
    company_counts.columns = ['Company', 'Drug Count']
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Company drug distribution
        fig_companies = px.bar(
            company_counts.head(10),
            x='Drug Count',
            y='Company',
            orientation='h',
            title="Top 10 Companies by Drug Count",
            labels={'Drug Count': 'Number of Drugs', 'Company': 'Company'}
        )
        fig_companies.update_layout(height=500)
        st.plotly_chart(fig_companies, use_container_width=True)
    
    with col2:
        # Company market share pie chart
        fig_pie = px.pie(
            company_counts.head(8),
            values='Drug Count',
            names='Company',
            title="Market Share by Company (Top 8)"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Company details table
    st.write("**Company Details:**")
    company_summary = df.groupby('Company').agg({
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Target': lambda x: x.nunique(),
        'Drug Class': lambda x: x.nunique()
    }).round(1)
    company_summary.columns = ['Total Drugs', 'FDA Approved', 'Unique Targets', 'Drug Classes']
    company_summary = company_summary.sort_values('Total Drugs', ascending=False)
    
    st.dataframe(company_summary, use_container_width=True)


def display_drug_class_analysis(df: pd.DataFrame):
    """Display drug class analysis."""
    st.subheader("💊 Drug Class Analysis")
    
    # Drug class distribution
    drug_class_counts = df['Drug Class'].value_counts().reset_index()
    drug_class_counts.columns = ['Drug Class', 'Count']
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Drug class bar chart
        fig_classes = px.bar(
            drug_class_counts.head(10),
            x='Count',
            y='Drug Class',
            orientation='h',
            title="Top 10 Drug Classes",
            labels={'Count': 'Number of Drugs', 'Drug Class': 'Drug Class'}
        )
        fig_classes.update_layout(height=500)
        st.plotly_chart(fig_classes, use_container_width=True)
    
    with col2:
        # Drug class distribution
        fig_pie = px.pie(
            drug_class_counts.head(8),
            values='Count',
            names='Drug Class',
            title="Drug Class Distribution (Top 8)"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Drug class details
    st.write("**Drug Class Details:**")
    class_summary = df.groupby('Drug Class').agg({
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Company': 'nunique',
        'Target': lambda x: x.nunique()
    }).round(1)
    class_summary.columns = ['Total Drugs', 'FDA Approved', 'Companies', 'Unique Targets']
    class_summary = class_summary.sort_values('Total Drugs', ascending=False)
    
    st.dataframe(class_summary, use_container_width=True)


def display_target_analysis(df: pd.DataFrame):
    """Display target analysis."""
    st.subheader("🎯 Target Analysis")
    
    # Target distribution
    target_counts = df['Target'].value_counts().reset_index()
    target_counts.columns = ['Target', 'Count']
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top targets bar chart
        fig_targets = px.bar(
            target_counts.head(10),
            x='Count',
            y='Target',
            orientation='h',
            title="Top 10 Targets",
            labels={'Count': 'Number of Drugs', 'Target': 'Target'}
        )
        fig_targets.update_layout(height=500)
        st.plotly_chart(fig_targets, use_container_width=True)
    
    with col2:
        # Target distribution pie chart
        fig_pie = px.pie(
            target_counts.head(8),
            values='Count',
            names='Target',
            title="Target Distribution (Top 8)"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Target details
    st.write("**Target Details:**")
    target_summary = df.groupby('Target').agg({
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Company': 'nunique',
        'Drug Class': lambda x: x.nunique()
    }).round(1)
    target_summary.columns = ['Total Drugs', 'FDA Approved', 'Companies', 'Drug Classes']
    target_summary = target_summary.sort_values('Total Drugs', ascending=False)
    
    st.dataframe(target_summary, use_container_width=True)


def display_target_drug_focus(df: pd.DataFrame):
    """Display focused analysis on number of drugs per target."""
    st.subheader("🔍 Target Drug Focus Analysis")
    
    # Calculate target drug counts
    target_counts = df['Target'].value_counts().reset_index()
    target_counts.columns = ['Target', 'Drug Count']
    
    # Add target categories based on drug count using configuration
    def categorize_target(count):
        return AnalysisConfig.get_competition_level(count)
    
    target_counts['Competition Level'] = target_counts['Drug Count'].apply(categorize_target)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Competition level distribution
        competition_counts = target_counts['Competition Level'].value_counts()
        fig_competition = px.pie(
            values=competition_counts.values,
            names=competition_counts.index,
            title="Target Competition Distribution",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_competition, use_container_width=True)
    
    with col2:
        # Target drug count histogram
        fig_hist = px.histogram(
            target_counts,
            x='Drug Count',
            nbins=20,
            title="Distribution of Drugs per Target",
            labels={'Drug Count': 'Number of Drugs', 'count': 'Number of Targets'}
        )
        fig_hist.update_layout(height=400)
        st.plotly_chart(fig_hist, use_container_width=True)
    
    # Detailed target analysis by competition level
    st.write("**Target Analysis by Competition Level:**")
    
    # Get competition levels from configuration
    competition_levels = [
        AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['high_competition']),
        AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['medium_competition']),
        AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['low_competition']),
        AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['single_drug'])
    ]
    
    for level in competition_levels:
        level_targets = target_counts[target_counts['Competition Level'] == level]
        if not level_targets.empty:
            st.write(f"**{level}:**")
            
            # Show top targets in this category using configuration
            chart_limits = AnalysisConfig.CHART_LIMITS
            if level == AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['high_competition']):
                display_targets = level_targets.head(chart_limits['top_targets'])
            elif level == AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['medium_competition']):
                display_targets = level_targets.head(15)  # Medium competition gets more space
            else:
                display_targets = level_targets.head(20)  # Low competition and single drug get most space
            
            # Create a detailed table for each target in this category
            target_details = []
            for _, row in display_targets.iterrows():
                target_name = row['Target']
                drug_count = row['Drug Count']
                
                # Get additional details for this target
                target_drugs = df[df['Target'] == target_name]
                fda_approved = len(target_drugs[target_drugs['FDA Approval'] != ''])
                companies = target_drugs['Company'].nunique()
                drug_classes = target_drugs['Drug Class'].nunique()
                
                target_details.append({
                    'Target': target_name,
                    'Drug Count': drug_count,
                    'FDA Approved': fda_approved,
                    'Companies': companies,
                    'Drug Classes': drug_classes,
                    'FDA Rate': f"{(fda_approved/drug_count)*100:.1f}%" if drug_count > 0 else "0%"
                })
            
            if target_details:
                details_df = pd.DataFrame(target_details)
                st.dataframe(details_df, use_container_width=True)
            
            st.write("---")
    
    # Target market concentration analysis
    st.write("**Target Market Concentration Analysis:**")
    
    total_targets = len(target_counts)
    high_comp_level = AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['high_competition'])
    single_drug_level = AnalysisConfig.get_competition_level(AnalysisConfig.COMPETITION_THRESHOLDS['single_drug'])
    
    high_comp_targets = len(target_counts[target_counts['Competition Level'] == high_comp_level])
    single_drug_targets = len(target_counts[target_counts['Competition Level'] == single_drug_level])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Targets", total_targets)
    
    with col2:
        st.metric("High Competition", high_comp_targets)
    
    with col3:
        st.metric("Single Drug", single_drug_targets)
    
    with col4:
        concentration_rate = (high_comp_targets / total_targets) * 100 if total_targets > 0 else 0
        st.metric("High Competition %", f"{concentration_rate:.1f}%")
    
    # Target opportunity analysis
    st.write("**Target Opportunity Analysis:**")
    
    # Find targets with only 1 drug (potential opportunities)
    single_drug_targets_list = target_counts[target_counts['Competition Level'] == single_drug_level]['Target'].tolist()
    
    if single_drug_targets_list:
        st.write(f"**Potential Opportunities ({len(single_drug_targets_list)} targets with only 1 drug):**")
        
        # Show details for single drug targets
        single_drug_details = []
        for target in single_drug_targets_list[:10]:  # Show top 10
            target_data = df[df['Target'] == target].iloc[0]
            single_drug_details.append({
                'Target': target,
                'Drug': target_data['Generic Name'],
                'Company': target_data['Company'],
                'FDA Approved': 'Yes' if target_data['FDA Approval'] != '' else 'No',
                'Drug Class': target_data['Drug Class']
            })
        
        if single_drug_details:
            single_df = pd.DataFrame(single_drug_details)
            st.dataframe(single_df, use_container_width=True)
    
    # Target saturation analysis
    st.write("**Target Saturation Analysis:**")
    
    # Calculate market saturation metrics using configuration
    total_drugs = len(df)
    high_comp_drugs = target_counts[target_counts['Competition Level'] == high_comp_level]['Drug Count'].sum()
    saturation_rate = (high_comp_drugs / total_drugs) * 100 if total_drugs > 0 else 0
    
    st.write(f"**Market Saturation:** {saturation_rate:.1f}% of all drugs target highly competitive targets (10+ drugs)")
    
    # Get saturation status and recommendation using configuration
    status, recommendation = AnalysisConfig.get_saturation_status(saturation_rate)
    if status == "High":
        st.warning(recommendation)
    elif status == "Moderate":
        st.info(recommendation)
    else:
        st.success(recommendation)


def display_fda_approval_analysis(df: pd.DataFrame):
    """Display FDA approval analysis."""
    st.subheader("🏛️ FDA Approval Analysis")
    
    # FDA approval status
    fda_status = df['FDA Approval'].apply(lambda x: 'Approved' if x != '' else 'Not Approved')
    fda_counts = fda_status.value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # FDA approval pie chart
        fig_fda = px.pie(
            values=fda_counts.values,
            names=fda_counts.index,
            title="FDA Approval Status"
        )
        st.plotly_chart(fig_fda, use_container_width=True)
    
    with col2:
        # FDA approval by company
        fda_by_company = df.groupby('Company').apply(
            lambda x: (x['FDA Approval'] != '').sum()
        ).reset_index()
        fda_by_company.columns = ['Company', 'FDA Approved Drugs']
        fda_by_company = fda_by_company.sort_values('FDA Approved Drugs', ascending=False)
        
        fig_company_fda = px.bar(
            fda_by_company.head(10),
            x='FDA Approved Drugs',
            y='Company',
            orientation='h',
            title="FDA Approved Drugs by Company (Top 10)"
        )
        fig_company_fda.update_layout(height=400)
        st.plotly_chart(fig_company_fda, use_container_width=True)
    
    # FDA approval timeline (if dates are available)
    fda_dates = df[df['FDA Approval'] != '']['FDA Approval']
    if not fda_dates.empty:
        st.write("**FDA Approval Timeline:**")
        # This would need more sophisticated date parsing for a proper timeline
        st.write(f"Drugs with FDA approval dates: {len(fda_dates)}")


def display_mechanism_analysis(df: pd.DataFrame):
    """Display mechanism of action analysis."""
    st.subheader("⚙️ Mechanism of Action Analysis")
    
    # Mechanism distribution
    mechanism_counts = df['Mechanism'].value_counts().reset_index()
    mechanism_counts.columns = ['Mechanism', 'Count']
    
    # Top mechanisms bar chart
    fig_mechanisms = px.bar(
        mechanism_counts.head(10),
        x='Count',
        y='Mechanism',
        orientation='h',
        title="Top 10 Mechanisms of Action",
        labels={'Count': 'Number of Drugs', 'Mechanism': 'Mechanism'}
    )
    fig_mechanisms.update_layout(height=500)
    st.plotly_chart(fig_mechanisms, use_container_width=True)
    
    # Mechanism details
    st.write("**Mechanism Details:**")
    mechanism_summary = df.groupby('Mechanism').agg({
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Company': 'nunique',
        'Target': lambda x: x.nunique()
    }).round(1)
    mechanism_summary.columns = ['Total Drugs', 'FDA Approved', 'Companies', 'Unique Targets']
    mechanism_summary = mechanism_summary.sort_values('Total Drugs', ascending=False)
    
    st.dataframe(mechanism_summary, use_container_width=True)


def display_clinical_trials_analysis(df: pd.DataFrame):
    """Display clinical trials analysis."""
    st.subheader("🧪 Clinical Trials Analysis")
    
    # Clinical trials distribution
    trial_counts = df['Current Clinical Trials'].value_counts().reset_index()
    trial_counts.columns = ['Clinical Trials', 'Count']
    
    # Filter out empty values
    trial_counts = trial_counts[trial_counts['Clinical Trials'] != '']
    
    if not trial_counts.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Clinical trials bar chart
            fig_trials = px.bar(
                trial_counts.head(10),
                x='Count',
                y='Clinical Trials',
                orientation='h',
                title="Top 10 Clinical Trials",
                labels={'Count': 'Number of Drugs', 'Clinical Trials': 'Clinical Trial'}
            )
            fig_trials.update_layout(height=500)
            st.plotly_chart(fig_trials, use_container_width=True)
        
        with col2:
            # Clinical trials distribution
            fig_pie = px.pie(
                trial_counts.head(8),
                values='Count',
                names='Clinical Trials',
                title="Clinical Trials Distribution (Top 8)"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    
    # Clinical trials summary
    st.write("**Clinical Trials Summary:**")
    trials_summary = df.groupby('Current Clinical Trials').agg({
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Company': 'nunique',
        'Drug Class': lambda x: x.nunique()
    }).round(1)
    trials_summary.columns = ['Total Drugs', 'FDA Approved', 'Companies', 'Drug Classes']
    trials_summary = trials_summary.sort_values('Total Drugs', ascending=False)
    
    st.dataframe(trials_summary, use_container_width=True)


def display_market_insights(df: pd.DataFrame):
    """Display key market insights and recommendations."""
    st.subheader("💡 Market Insights & Recommendations")
    
    # Calculate key metrics
    total_drugs = len(df)
    fda_approved = len(df[df['FDA Approval'] != ''])
    unique_companies = df['Company'].nunique()
    unique_targets = df['Target'].nunique()
    unique_mechanisms = df['Mechanism'].nunique()
    
    # Market concentration
    top_3_companies = df['Company'].value_counts().head(3).sum()
    market_concentration = (top_3_companies / total_drugs) * 100
    
    # FDA approval rate
    fda_approval_rate = (fda_approved / total_drugs) * 100
    
    insights = []
    
    # Market concentration insights
    if market_concentration > 50:
        insights.append(f"🔴 **High Market Concentration**: Top 3 companies control {market_concentration:.1f}% of the market")
    elif market_concentration > 30:
        insights.append(f"🟡 **Moderate Market Concentration**: Top 3 companies control {market_concentration:.1f}% of the market")
    else:
        insights.append(f"🟢 **Diverse Market**: Top 3 companies control only {market_concentration:.1f}% of the market")
    
    # FDA approval insights
    if fda_approval_rate > 70:
        insights.append(f"🟢 **High FDA Approval Rate**: {fda_approval_rate:.1f}% of drugs are FDA approved")
    elif fda_approval_rate > 40:
        insights.append(f"🟡 **Moderate FDA Approval Rate**: {fda_approval_rate:.1f}% of drugs are FDA approved")
    else:
        insights.append(f"🔴 **Low FDA Approval Rate**: Only {fda_approval_rate:.1f}% of drugs are FDA approved")
    
    # Target diversity insights
    if unique_targets > 20:
        insights.append(f"🟢 **High Target Diversity**: {unique_targets} unique targets indicate broad therapeutic coverage")
    elif unique_targets > 10:
        insights.append(f"🟡 **Moderate Target Diversity**: {unique_targets} unique targets provide good coverage")
    else:
        insights.append(f"🔴 **Limited Target Diversity**: Only {unique_targets} unique targets may indicate narrow focus")
    
    # Display insights
    for i, insight in enumerate(insights, 1):
        st.write(f"{i}. {insight}")
    
    # Recommendations
    st.write("**Strategic Recommendations:**")
    
    recommendations = []
    
    # Company recommendations
    top_company = df['Company'].value_counts().index[0]
    top_company_drugs = df['Company'].value_counts().iloc[0]
    recommendations.append(f"📈 **Focus on {top_company}**: Leading company with {top_company_drugs} drugs - study their strategy")
    
    # Target recommendations
    top_target = df['Target'].value_counts().index[0]
    top_target_drugs = df['Target'].value_counts().iloc[0]
    recommendations.append(f"🎯 **Target {top_target}**: Most popular target with {top_target_drugs} drugs - high market potential")
    
    # Mechanism recommendations
    top_mechanism = df['Mechanism'].value_counts().index[0]
    top_mechanism_drugs = df['Mechanism'].value_counts().iloc[0]
    recommendations.append(f"⚙️ **Mechanism {top_mechanism}**: Most common mechanism with {top_mechanism_drugs} drugs - proven approach")
    
    # FDA approval recommendations
    if fda_approval_rate < 50:
        recommendations.append("🏛️ **FDA Strategy**: Low approval rate suggests need for better regulatory strategy")
    
    for i, rec in enumerate(recommendations, 1):
        st.write(f"{i}. {rec}")


def main_market_analysis_dashboard():
    """Main market analysis dashboard."""
    st.title("📈 Market Analysis Dashboard")
    st.markdown("Comprehensive market analysis using Ground Truth data for validated insights.")
    
    # Load data
    df = load_ground_truth_data()
    
    if df.empty:
        st.error("No Ground Truth data available for market analysis.")
        return
    
    # Display sections
    display_market_overview(df)
    st.divider()
    
    display_company_analysis(df)
    st.divider()
    
    display_drug_class_analysis(df)
    st.divider()
    
    display_target_analysis(df)
    st.divider()
    
    display_target_drug_focus(df)
    st.divider()
    
    display_fda_approval_analysis(df)
    st.divider()
    
    display_mechanism_analysis(df)
    st.divider()
    
    display_clinical_trials_analysis(df)
    st.divider()
    
    display_market_insights(df)
