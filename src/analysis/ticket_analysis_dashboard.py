"""
Ticket Analysis Dashboard

This module provides analysis of company ticket requests vs drug counts
to help prioritize analysis efforts and time allocation.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import sys
sys.path.append('config')
from analysis_config import AnalysisConfig


def load_ground_truth_data() -> pd.DataFrame:
    """Load Ground Truth data for ticket analysis."""
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
        
        # Convert tickets to numeric
        df['Tickets'] = pd.to_numeric(df['Tickets'], errors='coerce').fillna(0)
        
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


def calculate_company_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate comprehensive company metrics."""
    company_metrics = df.groupby('Company').agg({
        'Tickets': 'first',  # Take first ticket number instead of summing
        'Generic Name': 'count',
        'FDA Approval': lambda x: (x != '').sum(),
        'Target': 'nunique',
        'Drug Class': 'nunique',
        'Mechanism': 'nunique'
    }).reset_index()
    
    # Get target names for each company
    target_names = df.groupby('Company')['Target'].apply(
        lambda x: ' | '.join(x.dropna().unique()) if x.notna().any() else 'No targets'
    ).reset_index()
    target_names.columns = ['Company', 'Target Names']
    
    # Get drug names for each company
    drug_names = df.groupby('Company')['Generic Name'].apply(
        lambda x: ' | '.join(x.dropna().unique()) if x.notna().any() else 'No drugs'
    ).reset_index()
    drug_names.columns = ['Company', 'Drug Names']
    
    company_metrics.columns = [
        'Company', 'Ticket Number', 'Total Drugs', 'FDA Approved Drugs', 
        'Unique Targets', 'Drug Classes', 'Unique Mechanisms'
    ]
    
    # Merge target names and drug names
    company_metrics = company_metrics.merge(target_names, on='Company', how='left')
    company_metrics = company_metrics.merge(drug_names, on='Company', how='left')
    
    # Calculate efficiency metrics
    company_metrics['Drugs per Ticket'] = company_metrics['Total Drugs'] / company_metrics['Ticket Number']
    company_metrics['FDA Approval Rate'] = (company_metrics['FDA Approved Drugs'] / company_metrics['Total Drugs'] * 100).round(1)
    
    # Calculate priority scores using configuration
    weights = AnalysisConfig.PRIORITY_WEIGHTS
    company_metrics['Priority Score'] = (
        company_metrics['Ticket Number'] * weights['ticket_volume'] +
        company_metrics['Total Drugs'] * weights['drug_portfolio'] +
        company_metrics['FDA Approved Drugs'] * weights['fda_approvals'] +
        company_metrics['Unique Targets'] * weights['target_diversity']
    ).round(1)
    
    return company_metrics.sort_values('Ticket Number', ascending=False)


def display_ticket_overview(df: pd.DataFrame, company_metrics: pd.DataFrame):
    """Display ticket analysis overview."""
    st.subheader("📊 Business Analysis Overview")
    
    total_companies = len(company_metrics)
    total_drugs = company_metrics['Total Drugs'].sum()
    avg_ticket_number = company_metrics['Ticket Number'].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Companies", total_companies)
    
    with col2:
        st.metric("Total Drugs", f"{total_drugs:.0f}")
    
    with col3:
        st.metric("Avg Ticket Number", f"{avg_ticket_number:.1f}")
    
    with col4:
        drugs_per_company = total_drugs / total_companies
        st.metric("Drugs per Company", f"{drugs_per_company:.1f}")


def display_ticket_vs_drug_analysis(company_metrics: pd.DataFrame):
    """Display ticket vs drug analysis."""
    st.subheader("📈 Client Demand vs Portfolio Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Scatter plot: Ticket Number vs Drugs
        fig_scatter = px.scatter(
            company_metrics,
            x='Total Drugs',
            y='Ticket Number',
            size='FDA Approved Drugs',
            color='Priority Score',
            hover_data=['Company', 'FDA Approval Rate', 'Unique Targets'],
            title="Ticket Number vs Drugs by Company",
            labels={'Total Drugs': 'Number of Drugs', 'Ticket Number': 'Ticket Number'}
        )
        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col2:
        # Drugs per ticket analysis
        fig_drugs_per_ticket = px.bar(
            company_metrics.head(10),
            x='Drugs per Ticket',
            y='Company',
            orientation='h',
            title="Drugs per Ticket (Top 10)",
            labels={'Drugs per Ticket': 'Drugs per Ticket', 'Company': 'Company'}
        )
        fig_drugs_per_ticket.update_layout(height=500)
        st.plotly_chart(fig_drugs_per_ticket, use_container_width=True)
    
    # Detailed analysis table
    st.write("**Detailed Company Analysis:**")
    
    # Add explanatory note
    st.info("""
    **📊 Understanding the Metrics:**
    
    **Priority Score**: Calculated using weighted factors:
    - Ticket Number × weight (demand indicator)
    - Total Drugs × weight (portfolio size)
    - FDA Approved Drugs × weight (market success)
    - Unique Targets × weight (therapeutic diversity)
    
    **Efficiency Categories**:
    - **Low Portfolio, High Demand**: <5 drugs per ticket (few drugs, high ticket numbers)
    - **Balanced**: 5-10 drugs per ticket (moderate portfolio vs demand)
    - **Medium Portfolio, Low Demand**: 10-20 drugs per ticket (good portfolio, moderate demand)
    - **High Portfolio, Low Demand**: >20 drugs per ticket (large portfolio, low demand)
    """)
    
    # Add efficiency categories
    def categorize_efficiency(row):
        if row['Drugs per Ticket'] > 20:
            return "High Portfolio, Low Demand"
        elif row['Drugs per Ticket'] > 10:
            return "Medium Portfolio, Low Demand"
        elif row['Drugs per Ticket'] > 5:
            return "Balanced"
        else:
            return "Low Portfolio, High Demand"
    
    company_metrics['Efficiency Category'] = company_metrics.apply(categorize_efficiency, axis=1)
    
    # Display table with all metrics
    display_columns = [
        'Company', 'Ticket Number', 'Total Drugs', 'Drugs per Ticket', 
        'FDA Approval Rate', 'Priority Score', 'Efficiency Category'
    ]
    
    st.dataframe(
        company_metrics[display_columns].sort_values('Priority Score', ascending=False),
        use_container_width=True
    )


def display_priority_recommendations(company_metrics: pd.DataFrame):
    """Display priority recommendations for time allocation."""
    st.subheader("🎯 Strategic Priorities")
    
    # Categorize companies for recommendations using configuration
    quantiles = AnalysisConfig.PRIORITY_QUANTILES
    high_priority = company_metrics[company_metrics['Priority Score'] >= company_metrics['Priority Score'].quantile(quantiles['high_priority'])]
    medium_priority = company_metrics[(company_metrics['Priority Score'] >= company_metrics['Priority Score'].quantile(quantiles['medium_priority'])) & 
                                    (company_metrics['Priority Score'] < company_metrics['Priority Score'].quantile(quantiles['high_priority']))]
    low_priority = company_metrics[company_metrics['Priority Score'] < company_metrics['Priority Score'].quantile(quantiles['low_priority'])]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**🔴 High Priority (Focus 60% of time)**")
        st.write(f"*{len(high_priority)} companies*")
        
        for _, company in high_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f}, {company['Total Drugs']:.0f} drugs")
            st.write(f"  - Priority Score: {company['Priority Score']:.1f}")
            st.write(f"  - Drugs per Ticket: {company['Drugs per Ticket']:.1f}")
            st.write("")
    
    with col2:
        st.write("**🟡 Medium Priority (Focus 30% of time)**")
        st.write(f"*{len(medium_priority)} companies*")
        
        for _, company in medium_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f}, {company['Total Drugs']:.0f} drugs")
            st.write(f"  - Priority Score: {company['Priority Score']:.1f}")
            st.write("")
    
    with col3:
        st.write("**🟢 Low Priority (Focus 10% of time)**")
        st.write(f"*{len(low_priority)} companies*")
        
        for _, company in low_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f}, {company['Total Drugs']:.0f} drugs")
            st.write(f"  - Priority Score: {company['Priority Score']:.1f}")
            st.write("")


def display_efficiency_analysis(company_metrics: pd.DataFrame):
    """Display efficiency analysis and insights."""
    st.subheader("💼 Business Efficiency Analysis")
    
    # Calculate efficiency metrics
    total_drugs = company_metrics['Total Drugs'].sum()
    
    # Calculate priority thresholds based on Priority Score
    priority_threshold_high = company_metrics['Priority Score'].quantile(0.67)  # Top 33%
    priority_threshold_low = company_metrics['Priority Score'].quantile(0.33)  # Bottom 33%
    
    # Categorize companies by priority
    high_priority = company_metrics[company_metrics['Priority Score'] >= priority_threshold_high]
    mid_priority = company_metrics[(company_metrics['Priority Score'] >= priority_threshold_low) & 
                                   (company_metrics['Priority Score'] < priority_threshold_high)]
    low_priority = company_metrics[company_metrics['Priority Score'] < priority_threshold_low]
    
    # High Priority Companies
    st.write("**🔴 High Priority Companies**")
    st.write("*Top 33% by Priority Score - Focus 60% of time*")
    
    if not high_priority.empty:
        for _, company in high_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f} for {company['Total Drugs']:.0f} drugs")
            st.write(f"  - **Drugs**: {company['Drug Names']}")
            st.write(f"  - **Targets**: {company['Target Names']}")
            st.write("")
    else:
        st.write("No companies in this category")
    
    st.write("")  # Add spacing
    
    # Mid Priority Companies
    st.write("**🟡 Mid Priority Companies**")
    st.write("*Middle 34% by Priority Score - Focus 30% of time*")
    
    if not mid_priority.empty:
        for _, company in mid_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f} for {company['Total Drugs']:.0f} drugs")
            st.write(f"  - **Drugs**: {company['Drug Names']}")
            st.write(f"  - **Targets**: {company['Target Names']}")
            st.write("")
    else:
        st.write("No companies in this category")
    
    st.write("")  # Add spacing
    
    # Low Priority Companies
    st.write("**🟢 Low Priority Companies**")
    st.write("*Bottom 33% by Priority Score - Focus 10% of time*")
    
    if not low_priority.empty:
        for _, company in low_priority.iterrows():
            st.write(f"• **{company['Company']}**: Ticket #{company['Ticket Number']:.0f} for {company['Total Drugs']:.0f} drugs")
            st.write(f"  - **Drugs**: {company['Drug Names']}")
            st.write(f"  - **Targets**: {company['Target Names']}")
            st.write("")
    else:
        st.write("No companies in this category")
    
    # Priority insights
    st.write("**📈 Priority Insights:**")
    
    insights = []
    
    # High priority insight
    if not high_priority.empty:
        avg_priority_score = high_priority['Priority Score'].mean()
        insights.append(f"🔴 **High Priority Focus**: {len(high_priority)} companies with average priority score {avg_priority_score:.1f} - allocate 60% of resources")
    
    # Mid priority insight
    if not mid_priority.empty:
        avg_priority_score = mid_priority['Priority Score'].mean()
        insights.append(f"🟡 **Mid Priority Management**: {len(mid_priority)} companies with average priority score {avg_priority_score:.1f} - allocate 30% of resources")
    
    # Low priority insight
    if not low_priority.empty:
        avg_priority_score = low_priority['Priority Score'].mean()
        insights.append(f"🟢 **Low Priority Monitoring**: {len(low_priority)} companies with average priority score {avg_priority_score:.1f} - allocate 10% of resources")
    
    # Overall portfolio efficiency
    overall_efficiency = total_drugs / len(company_metrics)
    insights.append(f"📊 **Portfolio Efficiency**: {overall_efficiency:.1f} drugs per company across all companies")
    
    # Priority score distribution
    priority_range = company_metrics['Priority Score'].max() - company_metrics['Priority Score'].min()
    insights.append(f"🎯 **Priority Range**: Scores range from {company_metrics['Priority Score'].min():.1f} to {company_metrics['Priority Score'].max():.1f} (span: {priority_range:.1f})")
    
    for insight in insights:
        st.write(insight)


def main_ticket_analysis_dashboard():
    """Main ticket analysis dashboard."""
    st.title("📊 Business Analysis Dashboard")
    st.markdown("Analyzing company client demand vs drug portfolio to optimize resource allocation and strategic priorities.")
    
    # Load data
    df = load_ground_truth_data()
    
    if df.empty:
        st.error("No Ground Truth data available for ticket analysis.")
        return
    
    # Calculate company metrics
    company_metrics = calculate_company_metrics(df)
    
    # Display sections
    display_ticket_overview(df, company_metrics)
    st.divider()
    
    display_ticket_vs_drug_analysis(company_metrics)
    st.divider()
    
    display_priority_recommendations(company_metrics)
    st.divider()
    
    display_efficiency_analysis(company_metrics)
