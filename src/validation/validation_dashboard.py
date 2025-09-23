"""
Validation Dashboard Integration

This module provides Streamlit components for displaying validation results.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any
import json
from pathlib import Path


def load_validation_results(results_path: str = "outputs/validation_results.json") -> Dict[str, Any]:
    """Load validation results from file."""
    try:
        with open(results_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Validation results not found at {results_path}")
        return None
    except Exception as e:
        st.error(f"Error loading validation results: {e}")
        return None


def display_validation_summary(results: Dict[str, Any]):
    """Display validation summary metrics."""
    st.subheader("🎯 Validation Summary")
    
    summary = results.get('summary', {})
    key_metrics = summary.get('key_metrics', {})
    
    # Create metrics columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'drug_names_f1' in key_metrics:
            f1_score = key_metrics['drug_names_f1']
            color = "green" if f1_score >= 0.8 else "orange" if f1_score >= 0.5 else "red"
            st.metric("Drug Names F1", f"{f1_score:.3f}", delta=None)
    
    with col2:
        if 'company_coverage_f1' in key_metrics:
            f1_score = key_metrics['company_coverage_f1']
            color = "green" if f1_score >= 0.8 else "orange" if f1_score >= 0.5 else "red"
            st.metric("Company Coverage F1", f"{f1_score:.3f}", delta=None)
    
    with col3:
        if 'mechanisms_accuracy' in key_metrics:
            accuracy = key_metrics['mechanisms_accuracy']
            color = "green" if accuracy >= 0.7 else "orange" if accuracy >= 0.5 else "red"
            st.metric("Mechanism Accuracy", f"{accuracy:.3f}", delta=None)
    
    with col4:
        if 'clinical_trials_coverage' in key_metrics:
            coverage = key_metrics['clinical_trials_coverage']
            color = "green" if coverage >= 0.5 else "orange" if coverage >= 0.3 else "red"
            st.metric("Trial Coverage", f"{coverage:.3f}", delta=None)


def display_validation_charts(results: Dict[str, Any]):
    """Display validation charts."""
    st.subheader("📊 Validation Metrics")
    
    validations = results.get('validations', {})
    
    # Prepare data for charts
    metrics_data = []
    for metric, data in validations.items():
        if 'f1_score' in data:
            metrics_data.append({
                'Metric': metric.replace('_', ' ').title(),
                'F1 Score': data['f1_score'],
                'Precision': data.get('precision', 0),
                'Recall': data.get('recall', 0)
            })
        elif 'accuracy' in data:
            metrics_data.append({
                'Metric': metric.replace('_', ' ').title(),
                'Accuracy': data['accuracy']
            })
        elif 'overall_coverage' in data:
            metrics_data.append({
                'Metric': metric.replace('_', ' ').title(),
                'Coverage': data['overall_coverage']
            })
    
    if metrics_data:
        df = pd.DataFrame(metrics_data)
        
        # F1 Score chart
        if 'F1 Score' in df.columns:
            fig_f1 = px.bar(
                df, 
                x='Metric', 
                y='F1 Score',
                title="F1 Scores by Metric",
                color='F1 Score',
                color_continuous_scale=['red', 'orange', 'green']
            )
            fig_f1.update_layout(yaxis_range=[0, 1])
            st.plotly_chart(fig_f1, use_container_width=True)
        
        # Precision vs Recall chart
        if 'Precision' in df.columns and 'Recall' in df.columns:
            fig_pr = go.Figure()
            fig_pr.add_trace(go.Scatter(
                x=df['Precision'],
                y=df['Recall'],
                mode='markers+text',
                text=df['Metric'],
                textposition="top center",
                marker=dict(size=10, color=df['F1 Score'], colorscale='RdYlGn')
            ))
            fig_pr.update_layout(
                title="Precision vs Recall",
                xaxis_title="Precision",
                yaxis_title="Recall",
                xaxis_range=[0, 1],
                yaxis_range=[0, 1]
            )
            st.plotly_chart(fig_pr, use_container_width=True)


def display_detailed_results(results: Dict[str, Any]):
    """Display detailed validation results."""
    st.subheader("🔍 Detailed Results")
    
    validations = results.get('validations', {})
    
    for metric, data in validations.items():
        with st.expander(f"{metric.replace('_', ' ').title()}", expanded=False):
            
            # Basic metrics
            if 'precision' in data:
                st.write(f"**Precision:** {data['precision']:.3f}")
                st.write(f"**Recall:** {data['recall']:.3f}")
                st.write(f"**F1 Score:** {data['f1_score']:.3f}")
            
            if 'accuracy' in data:
                st.write(f"**Accuracy:** {data['accuracy']:.3f}")
            
            if 'overall_coverage' in data:
                st.write(f"**Coverage:** {data['overall_coverage']:.3f}")
            
            # Missing items
            if 'missing_from_pipeline' in data and data['missing_from_pipeline']:
                st.write(f"**Missing from pipeline:** {len(data['missing_from_pipeline'])} items")
                if len(data['missing_from_pipeline']) <= 10:
                    st.write("Missing items:")
                    for item in data['missing_from_pipeline']:
                        st.write(f"- {item}")
            
            # Mismatch details
            if 'mismatch_details' in data and data['mismatch_details']:
                st.write("**Mismatch details:**")
                mismatch_df = pd.DataFrame(data['mismatch_details'])
                st.dataframe(mismatch_df, use_container_width=True)


def display_recommendations(results: Dict[str, Any]):
    """Display validation recommendations."""
    st.subheader("💡 Recommendations")
    
    summary = results.get('summary', {})
    recommendations = summary.get('recommendations', [])
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            st.write(f"{i}. {rec}")
    else:
        st.success("No specific recommendations at this time. Pipeline is performing well!")


def display_ground_truth_stats(results: Dict[str, Any]):
    """Display ground truth statistics."""
    st.subheader("📈 Ground Truth Statistics")
    
    validations = results.get('validations', {})
    
    # Drug names stats
    if 'drug_names' in validations:
        drug_data = validations['drug_names']
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Ground Truth Drugs", drug_data.get('total_gt_drugs', 0))
        with col2:
            st.metric("Pipeline Drugs", drug_data.get('total_pipeline_drugs', 0))
    
    # Company stats
    if 'company_coverage' in validations:
        company_data = validations['company_coverage']
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Ground Truth Companies", company_data.get('total_gt_companies', 0))
        with col2:
            st.metric("Pipeline Companies", company_data.get('total_pipeline_companies', 0))


def display_ground_truth_table():
    """Display ground truth table with filters."""
    st.subheader("📋 Ground Truth Data Table")
    
    try:
        # Load ground truth data
        import pandas as pd
        gt_df = pd.read_excel("data/Pipeline_Ground_Truth.xlsx")
        
        # Fix data type issues for Streamlit display
        gt_df['FDA Approval'] = gt_df['FDA Approval'].astype(str)
        gt_df['Tickets'] = gt_df['Tickets'].astype(str)
        
        # Clean up FDA approval date format
        def clean_fda_date(date_str):
            if pd.isna(date_str) or date_str == 'nan' or date_str == '':
                return ''
            # Remove time component if present
            if ' ' in str(date_str):
                return str(date_str).split(' ')[0]
            return str(date_str)
        
        gt_df['FDA Approval'] = gt_df['FDA Approval'].apply(clean_fda_date)
        
        st.write(f"**Loaded {len(gt_df)} drugs from ground truth data**")
        
        # Create filters
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Company filter
            companies = ['All'] + sorted(gt_df['Partner'].dropna().unique().tolist())
            selected_company = st.selectbox("Filter by Company", companies)
            
        with col2:
            # Drug class filter
            drug_classes = ['All'] + sorted(gt_df['Drug Class'].dropna().unique().tolist())
            selected_drug_class = st.selectbox("Filter by Drug Class", drug_classes)
            
        with col3:
            # Target filter
            targets = ['All'] + sorted(gt_df['Target'].dropna().unique().tolist())
            selected_target = st.selectbox("Filter by Target", targets)
            
        with col4:
            # FDA approval filter
            fda_options = ['All', 'FDA Approved', 'Not FDA Approved', 'Unknown']
            selected_fda = st.selectbox("Filter by FDA Status", fda_options)
        
        # Apply filters
        filtered_df = gt_df.copy()
        
        if selected_company != 'All':
            filtered_df = filtered_df[filtered_df['Partner'] == selected_company]
            
        if selected_drug_class != 'All':
            filtered_df = filtered_df[filtered_df['Drug Class'] == selected_drug_class]
            
        if selected_target != 'All':
            filtered_df = filtered_df[filtered_df['Target'] == selected_target]
            
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
        if selected_fda != 'All':
            active_filters.append(f"FDA Status: {selected_fda}")
        
        if active_filters:
            st.write(f"**Active filters:** {', '.join(active_filters)}")
        
        # Display table
        if len(filtered_df) > 0:
            # Select columns to display
            display_columns = [
                'Partner', 'Generic name', 'Brand name', 'FDA Approval', 
                'Drug Class', 'Target', 'Mechanism', 'Indication Approved', 
                'Current Clinical Trials'
            ]
            
            # Filter columns that exist
            available_columns = [col for col in display_columns if col in filtered_df.columns]
            display_df = filtered_df[available_columns]
            
            # Rename columns for better display
            column_mapping = {
                'Partner': 'Company',
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
            
            # Display with pagination
            page_size = 20
            total_pages = (len(display_df) - 1) // page_size + 1
            
            if total_pages > 1:
                page = st.selectbox("Page", range(1, total_pages + 1))
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                page_df = display_df.iloc[start_idx:end_idx]
            else:
                page_df = display_df
            
            # Display table
            st.dataframe(
                page_df,
                use_container_width=True,
                height=600
            )
            
            # Display pagination info
            if total_pages > 1:
                st.write(f"Page {page} of {total_pages}")
                
        else:
            st.warning("No data matches the selected filters.")
            
    except FileNotFoundError:
        st.error("Ground truth file not found at data/Pipeline_Ground_Truth.xlsx")
    except Exception as e:
        st.error(f"Error loading ground truth data: {e}")


def display_ground_truth_analysis():
    """Display ground truth analysis and insights."""
    st.subheader("🔍 Ground Truth Analysis")
    
    try:
        import pandas as pd
        gt_df = pd.read_excel("data/Pipeline_Ground_Truth.xlsx")
        
        # Fix data type issues for Streamlit display
        gt_df['FDA Approval'] = gt_df['FDA Approval'].astype(str)
        gt_df['Tickets'] = gt_df['Tickets'].astype(str)
        
        # Clean up FDA approval date format
        def clean_fda_date(date_str):
            if pd.isna(date_str) or date_str == 'nan' or date_str == '':
                return ''
            # Remove time component if present
            if ' ' in str(date_str):
                return str(date_str).split(' ')[0]
            return str(date_str)
        
        gt_df['FDA Approval'] = gt_df['FDA Approval'].apply(clean_fda_date)
        
        # Create analysis tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Company Analysis", "Drug Analysis", "Target Analysis", "Mechanism Analysis", "Trial Analysis"])
        
        with tab1:
            st.write("**Company Distribution**")
            company_counts = gt_df['Partner'].value_counts()
            st.bar_chart(company_counts)
            
            st.write("**Company Completeness**")
            company_completeness = gt_df.groupby('Partner').agg({
                'Generic name': 'count',
                'Mechanism': lambda x: x.notna().sum(),
                'Current Clinical Trials': lambda x: x.notna().sum()
            }).rename(columns={'Generic name': 'Total Drugs', 'Mechanism': 'With Mechanism', 'Current Clinical Trials': 'With Trials'})
            
            company_completeness['Mechanism %'] = (company_completeness['With Mechanism'] / company_completeness['Total Drugs'] * 100).round(1)
            company_completeness['Trial %'] = (company_completeness['With Trials'] / company_completeness['Total Drugs'] * 100).round(1)
            
            st.dataframe(company_completeness, use_container_width=True)
        
        with tab2:
            st.write("**Drug Class Distribution**")
            drug_class_counts = gt_df['Drug Class'].value_counts().head(10)
            st.bar_chart(drug_class_counts)
            
            st.write("**FDA Approval Status**")
            fda_status = gt_df['FDA Approval'].notna().value_counts()
            st.bar_chart(fda_status)
            
            st.write("**Missing Data Analysis**")
            missing_data = {
                'Brand Name': gt_df['Brand name'].isna().sum(),
                'Drug Class': gt_df['Drug Class'].isna().sum(),
                'Target': gt_df['Target'].isna().sum(),
                'Mechanism': gt_df['Mechanism'].isna().sum(),
                'Indication': gt_df['Indication Approved'].isna().sum(),
                'Clinical Trials': gt_df['Current Clinical Trials'].isna().sum()
            }
            
            missing_df = pd.DataFrame(list(missing_data.items()), columns=['Field', 'Missing Count'])
            missing_df['Missing %'] = (missing_df['Missing Count'] / len(gt_df) * 100).round(1)
            st.dataframe(missing_df, use_container_width=True)
        
        with tab3:
            st.write("**Target Distribution**")
            targets = gt_df['Target'].dropna()
            target_counts = targets.value_counts()
            st.bar_chart(target_counts.head(15))
            
            st.write("**Top Targets**")
            top_targets = target_counts.head(10)
            st.dataframe(top_targets, use_container_width=True)
            
            st.write("**Target Coverage by Company**")
            target_company = gt_df.groupby('Partner')['Target'].nunique().sort_values(ascending=False)
            st.bar_chart(target_company)
            
            st.write("**Drugs per Target**")
            drugs_per_target = gt_df.groupby('Target').size().sort_values(ascending=False).head(10)
            st.dataframe(drugs_per_target, use_container_width=True)
        
        with tab4:
            st.write("**Mechanism Categories**")
            mechanisms = gt_df['Mechanism'].dropna()
            
            # Categorize mechanisms
            mechanism_categories = {
                'Monoclonal Antibody': mechanisms[mechanisms.str.contains('monoclonal|mab|anti-', case=False, na=False)].count(),
                'Kinase Inhibitor': mechanisms[mechanisms.str.contains('kinase|inhibitor', case=False, na=False)].count(),
                'ADC': mechanisms[mechanisms.str.contains('adc|antibody-drug|conjugate', case=False, na=False)].count(),
                'BiTE': mechanisms[mechanisms.str.contains('bite|bispecific|t-cell', case=False, na=False)].count(),
                'SERD': mechanisms[mechanisms.str.contains('serd|estrogen', case=False, na=False)].count(),
                'Other': mechanisms[~mechanisms.str.contains('monoclonal|mab|anti-|kinase|inhibitor|adc|antibody-drug|conjugate|bite|bispecific|t-cell|serd|estrogen', case=False, na=False)].count()
            }
            
            mechanism_df = pd.DataFrame(list(mechanism_categories.items()), columns=['Category', 'Count'])
            st.bar_chart(mechanism_df.set_index('Category'))
            
            st.write("**Top Mechanisms**")
            top_mechanisms = mechanisms.value_counts().head(10)
            st.dataframe(top_mechanisms, use_container_width=True)
        
        with tab5:
            st.write("**Clinical Trial Distribution**")
            # Count trials per drug (rough estimate based on separators)
            trial_counts = gt_df['Current Clinical Trials'].dropna().apply(
                lambda x: len([t.strip() for t in str(x).split('|') if t.strip()]) if pd.notna(x) else 0
            )
            
            st.write(f"**Average trials per drug:** {trial_counts.mean():.1f}")
            st.write(f"**Total estimated trials:** {trial_counts.sum()}")
            
            # Show drugs with most trials
            gt_df_with_trials = gt_df.copy()
            gt_df_with_trials['Trial Count'] = trial_counts
            top_trial_drugs = gt_df_with_trials.nlargest(10, 'Trial Count')[['Partner', 'Generic name', 'Trial Count']]
            st.dataframe(top_trial_drugs, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error in ground truth analysis: {e}")


def main_validation_dashboard():
    """Main validation dashboard function."""
    st.title("🔍 Ground Truth Validation Dashboard")
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Validation Metrics", "Ground Truth Analysis"])
    
    with tab1:
        # Load validation results
        results = load_validation_results()
        if not results:
            return
        
        # Display sections
        display_validation_summary(results)
        st.divider()
        
        display_validation_charts(results)
        st.divider()
        
        display_ground_truth_stats(results)
        st.divider()
        
        display_detailed_results(results)
        st.divider()
        
        display_recommendations(results)
    
    with tab2:
        display_ground_truth_analysis()


