"""Streamlit UI for Biopartnering Insights Pipeline."""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import pandas as pd
from datetime import datetime
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.models.database import get_db
from src.models.entities import Document, Company, Drug, ClinicalTrial, Target, DrugTarget
from src.data_collection.orchestrator import DataCollectionOrchestrator
from config.config import settings, get_target_companies
from src.rag.provider import build_provider, OllamaProvider
from src.rag.rag_agent import create_enhanced_basic_rag_agent
from src.rag.models import DrugSearchQuery, ClinicalTrialSearchQuery, BiopartneringQuery
from src.rag.cache_manager import RAGCacheManager
from src.processing.csv_export import export_basic, export_drug_table
from src.processing.pipeline import run_processing
from src.evaluation.ragas_eval import evaluate_rag_agent
from src.evaluation.feedback_analysis import (
    analyze_feedback_patterns, 
    get_improvement_recommendations,
    generate_feedback_summary,
    export_feedback_data,
    create_feedback_dashboard_data,
    get_detailed_feedback_options,
    validate_feedback_data,
    get_feedback_insights
)


# Page configuration
st.set_page_config(
    page_title="Biopartnering Insights Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;s
    }
    .source-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def render_enhanced_feedback(message_index: int, message_role: str):
    """Render enhanced feedback system for assistant messages."""
    if message_role != "assistant":
        return
    
    # Initialize detailed feedback storage
    if "detailed_feedback" not in st.session_state:
        st.session_state.detailed_feedback = {}
    
    st.write("**📝 Help us improve this response:**")
    
    feedback_col1, feedback_col2 = st.columns([2, 1])
    
    with feedback_col1:
        # Overall rating
        rating = st.select_slider(
            "Overall Quality (1-5)",
            options=[1, 2, 3, 4, 5],
            value=st.session_state.feedback.get(message_index, 3),
            key=f"rating_{message_index}",
            help="1 = Poor, 2 = Fair, 3 = Good, 4 = Very Good, 5 = Excellent",
            format_func=lambda x: f"{x} ⭐" if x == 1 else f"{x} ⭐" if x == 2 else f"{x} ⭐" if x == 3 else f"{x} ⭐" if x == 4 else f"{x} ⭐"
        )
        if rating != st.session_state.feedback.get(message_index, 3):
            st.session_state.feedback[message_index] = rating
            st.success(f"Thank you for rating this response {rating}/5!")
        
        # Detailed feedback options
        st.write("**Specific Issues (select all that apply):**")
        
        # Get detailed feedback options from the analysis module
        detailed_options = get_detailed_feedback_options()
        
        # Initialize detailed feedback for this message
        if message_index not in st.session_state.detailed_feedback:
            st.session_state.detailed_feedback[message_index] = []
        
        # Create checkboxes for detailed feedback
        selected_issues = []
        for option_key, option_text in detailed_options.items():
            if st.checkbox(
                option_text, 
                key=f"detailed_{message_index}_{option_key}",
                value=option_key in st.session_state.detailed_feedback[message_index]
            ):
                if option_key not in st.session_state.detailed_feedback[message_index]:
                    st.session_state.detailed_feedback[message_index].append(option_key)
            else:
                if option_key in st.session_state.detailed_feedback[message_index]:
                    st.session_state.detailed_feedback[message_index].remove(option_key)
        
        # Additional comments
        st.write("**Additional Comments (optional):**")
        comment = st.text_area(
            "Tell us more about what could be improved:",
            key=f"comment_{message_index}",
            placeholder="e.g., 'The drug mechanism explanation was confusing' or 'Need more recent clinical trial data'",
            height=68
        )
        
        # Save comment if provided
        if comment and comment.strip():
            if "comments" not in st.session_state.detailed_feedback[message_index]:
                st.session_state.detailed_feedback[message_index] = st.session_state.detailed_feedback[message_index] + ["comments"]
            st.session_state.detailed_feedback[message_index].append(f"comment: {comment.strip()}")
    
    with feedback_col2:
        if message_index in st.session_state.feedback:
            current_rating = st.session_state.feedback[message_index]
            if current_rating >= 4:
                st.success(f"✅ {current_rating}/5 - Great!")
            elif current_rating >= 3:
                st.info(f"✅ {current_rating}/5 - Good")
            else:
                st.warning(f"⚠️ {current_rating}/5 - Needs improvement")
        
        # Show selected issues
        if message_index in st.session_state.detailed_feedback and st.session_state.detailed_feedback[message_index]:
            st.write("**Selected Issues:**")
            for issue in st.session_state.detailed_feedback[message_index]:
                if not issue.startswith("comment:"):
                    st.write(f"• {detailed_options.get(issue, issue)}")
    
    st.write("---")




def generate_follow_up_questions(answer_text: str, original_question: str) -> list:
    """Generate contextual follow-up questions based on the assistant's response."""
    follow_up_questions = []
    
    # Extract key terms from the answer
    answer_lower = answer_text.lower()
    
    # Drug-related follow-ups
    if any(term in answer_lower for term in ['drug', 'therapeutic', 'medicine', 'mab', 'nib', 'cept']):
        follow_up_questions.extend([
            "What are the side effects of these drugs?",
            "Which companies are developing similar drugs?",
            "What is the mechanism of action of these drugs?",
            "Are there any drug interactions to be aware of?"
        ])
    
    # Clinical trial follow-ups
    if any(term in answer_lower for term in ['trial', 'clinical', 'phase', 'study', 'nct']):
        follow_up_questions.extend([
            "What are the primary endpoints of these trials?",
            "Which phase are these trials in?",
            "What is the enrollment status?",
            "Are there any safety concerns reported?"
        ])
    
    # Company/partnership follow-ups
    if any(term in answer_lower for term in ['company', 'partnership', 'collaboration', 'merger']):
        follow_up_questions.extend([
            "What other partnerships does this company have?",
            "What is the company's pipeline strategy?",
            "Are there any recent acquisitions?",
            "What is the company's market position?"
        ])
    
    # Indication/disease follow-ups
    if any(term in answer_lower for term in ['cancer', 'oncology', 'tumor', 'metastatic', 'biomarker']):
        follow_up_questions.extend([
            "What biomarkers are associated with this indication?",
            "What is the prevalence of this cancer type?",
            "Are there any unmet medical needs?",
            "What are the current treatment options?"
        ])
    
    # FDA/regulatory follow-ups
    if any(term in answer_lower for term in ['fda', 'approval', 'regulatory', 'label', 'indication']):
        follow_up_questions.extend([
            "What is the FDA approval timeline?",
            "Are there any regulatory challenges?",
            "What are the labeling requirements?",
            "Are there any post-marketing commitments?"
        ])
    
    # Generic follow-ups (always include some)
    generic_questions = [
        "Can you provide more details about this?",
        "What are the latest developments?",
        "How does this compare to competitors?",
        "What are the commercial implications?"
    ]
    
    # Add generic questions if we don't have enough specific ones
    if len(follow_up_questions) < 4:
        follow_up_questions.extend(generic_questions[:4-len(follow_up_questions)])
    
    # Remove duplicates and limit to 4 questions
    unique_questions = list(dict.fromkeys(follow_up_questions))
    return unique_questions[:4]


def get_database_stats():
    """Get database statistics."""
    try:
        db = get_db()
        
        stats = {
            "documents": db.query(Document).count(),
            "companies": db.query(Company).count(),
            "drugs": db.query(Drug).count(),
            "clinical_trials": db.query(ClinicalTrial).count()
        }
        
        db.close()
        return stats
    except Exception as e:
        st.error(f"Error getting database stats: {e}")
        return {"documents": 0, "companies": 0, "drugs": 0, "clinical_trials": 0}


def load_drugs_from_database():
    """Load drugs data directly from database with targets and company info."""
    try:
        db = get_db()
        
        # Query drugs with company information
        drugs = db.query(Drug).join(Company, Drug.company_id == Company.id).all()
        
        # Convert to DataFrame format
        drug_data = []
        for drug in drugs:
            # Get targets for this drug
            targets = db.query(Target).join(DrugTarget).filter(
                DrugTarget.drug_id == drug.id
            ).all()
            target_names = [t.name for t in targets]
            
            # Get clinical trials for this drug
            clinical_trials = db.query(ClinicalTrial).filter(
                ClinicalTrial.drug_id == drug.id
            ).all()
            
            # Format clinical trials
            trial_summaries = []
            for trial in clinical_trials:
                parts = [
                    (trial.title or "").strip(),
                    (trial.phase or "").strip(),
                    (trial.status or "").strip(),
                ]
                trial_summaries.append(" | ".join([p for p in parts if p]))
            
            drug_data.append({
                'Generic name': drug.generic_name,
                'Brand name': drug.brand_name or '',
                'Drug Class': drug.drug_class or '',
                'FDA Approval': drug.fda_approval_date.strftime('%Y-%m-%d') if drug.fda_approval_date else '',
                'Company name': drug.company.name if drug.company else '',
                'Target': ', '.join(target_names) if target_names else '',
                'Mechanism of Action': drug.mechanism_of_action or '',
                'FDA Approval Status': 'Approved' if drug.fda_approval_status else 'Not Approved',
                'Indication Approved': '',  # Would need to join with indications table
                'Current Clinical Trials': '; '.join(trial_summaries) if trial_summaries else ''
            })
        
        db.close()
        return pd.DataFrame(drug_data)
        
    except Exception as e:
        logger.error(f"Error loading drugs from database: {e}")
        return pd.DataFrame()


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🧬 Biopartnering Insights Pipeline</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.selectbox(
            "Select Page",
            ["Dashboard", "Data Collection", "RAG Agent", "Results", "Evaluation", "Settings"]
        )
        
        st.header("Database Status")
        stats = get_database_stats()
        st.write(f"**Total Documents:** {stats['documents']}")
        st.write(f"**Companies Tracked:** {stats['companies']}")
        st.write(f"**Drugs in Database:** {stats['drugs']}")
        st.write(f"**Clinical Trials:** {stats['clinical_trials']}")
        
        # Cache statistics
        try:
            cache_manager = RAGCacheManager()
            cache_stats = cache_manager.get_cache_stats(get_db())
            st.write(f"**RAG Cache Entries:** {cache_stats.get('total_entries', 0)}")
            st.write(f"**Valid Cache Entries:** {cache_stats.get('valid_entries', 0)}")
        except Exception as e:
            st.write(f"**RAG Cache:** Error loading stats")
        
        st.header("Model Provider")
        provider = st.selectbox("Provider", ["openai", "ollama"], index=0 if settings.model_provider == "openai" else 1)
        chat_model = st.text_input("Chat model", value=settings.chat_model)
        embed_model = st.text_input("Embedding model", value=settings.embed_model)
        if st.button("Test connection"):
            try:
                p = build_provider(provider, chat_model, embed_model, settings.openai_api_key)
                resp = p.chat([
                    {"role": "system", "content": "You are a healthtech assistant."},
                    {"role": "user", "content": "Say hello in one short sentence."}
                ])
                st.success(f"Provider OK. Sample reply: {resp.content[:100]}")
            except Exception as e:
                st.error(f"Provider test failed: {e}")

        
        for key, value in stats.items():
            st.metric(
                label=key.replace("_", " ").title(),
                value=value
            )
    
    # Main content based on selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Data Collection":
        show_data_collection()
    elif page == "RAG Agent":
        show_rag_agent()
    elif page == "Results":
        show_results()
    elif page == "Evaluation":
        show_evaluation()
    elif page == "Settings":
        show_settings()


def show_dashboard():
    """Show dashboard page."""
    # Dashboard header with time
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("📊 Dashboard")
    
    with col2:
        # Real-time clock
        current_time = datetime.now()
        st.markdown(f"""
        <div style="text-align: right; margin-top: 1rem;">
            <h4 style="color: #666; margin: 0;">🕐 {current_time.strftime('%H:%M:%S')}</h4>
            <p style="color: #888; margin: 0; font-size: 0.9em;">{current_time.strftime('%B %d, %Y')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Get database stats
    stats = get_database_stats()
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Documents", stats["documents"])
    with col2:
        st.metric("Companies Tracked", stats["companies"])
    with col3:
        st.metric("Drugs in Database", stats["drugs"])
    with col4:
        st.metric("Clinical Trials", stats["clinical_trials"])
    
    # Database Data Preview
    st.header("📊 Data Collection Results")
    
    # Load drugs from database
    st.subheader("💊 Biopharma Drugs Preview")
    
    try:
        df = load_drugs_from_database()
        
        if not df.empty:
            
            # Show quick stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Drugs", len(df))
            with col2:
                st.metric("Companies", len(df['Company name'].unique()) if 'Company name' in df.columns else 0)
            with col3:
                st.metric("Drugs with Brand Names", len(df[df['Brand name'].notna() & (df['Brand name'] != '')]))
            with col4:
                st.metric("FDA Approved", len(df[df['FDA Approval Status'] == 'Approved']))
            
            # Add filters
            st.subheader("🔍 Filter Options")
            
            # Create filter columns (7 columns to accommodate all filters)
            filter_col1, filter_col2, filter_col3, filter_col4, filter_col5, filter_col6, filter_col7 = st.columns(7)
            
            with filter_col1:
                # Generic name filter
                generic_filter = st.text_input("Filter by Generic Name", placeholder="e.g., pembrolizumab")
                if generic_filter:
                    df = df[df['Generic name'].str.contains(generic_filter, case=False, na=False)]
            
            with filter_col2:
                # Brand name filter
                brand_filter = st.text_input("Filter by Brand Name", placeholder="e.g., KEYTRUDA")
                if brand_filter:
                    df = df[df['Brand name'].str.contains(brand_filter, case=False, na=False)]
            
            with filter_col3:
                # Drug class filter
                if 'Drug Class' in df.columns:
                    drug_classes = ['All'] + sorted(df['Drug Class'].dropna().unique().tolist())
                    selected_class = st.selectbox("Filter by Drug Class", drug_classes)
                    if selected_class != 'All':
                        df = df[df['Drug Class'] == selected_class]
            
            with filter_col4:
                # Target filter
                if 'Target' in df.columns:
                    targets = ['All'] + sorted(df['Target'].dropna().unique().tolist())
                    selected_target = st.selectbox("Filter by Target", targets)
                    if selected_target != 'All':
                        df = df[df['Target'] == selected_target]
            
            with filter_col5:
                # FDA approval filter
                if 'FDA Approval Status' in df.columns:
                    fda_options = ['All', 'Approved', 'Not Approved']
                    fda_filter = st.selectbox("Filter by FDA Status", fda_options)
                    if fda_filter == 'Approved':
                        df = df[df['FDA Approval Status'] == 'Approved']
                    elif fda_filter == 'Not Approved':
                        df = df[df['FDA Approval Status'] == 'Not Approved']
            
            with filter_col6:
                # Approved indication filter
                if 'Indication Approved' in df.columns:
                    indication_filter = st.text_input("Filter by Approved Indication", placeholder="e.g., cancer, diabetes")
                    if indication_filter:
                        df = df[df['Indication Approved'].str.contains(indication_filter, case=False, na=False)]
            
            with filter_col7:
                # Current clinical trials filter
                if 'Current Clinical Trials' in df.columns:
                    trial_filter = st.text_input("Filter by Current Clinical Trial", placeholder="e.g., NCT12345678")
                    if trial_filter:
                        df = df[df['Current Clinical Trials'].str.contains(trial_filter, case=False, na=False)]
            
            # Show filtered results
            st.subheader(f"💊 Biopharma Drugs ({len(df)} results)")
            
            if len(df) > 0:
                # Show table with filters
                st.dataframe(df, use_container_width=True)
                
                # Download filtered data
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Filtered Data",
                    data=csv_data,
                    file_name=f"filtered_biopharma_drugs_{len(df)}_results.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No drugs match the current filters. Try adjusting your search criteria.")
            
        else:
            st.info("No biopharma drugs data found. Run data collection to generate results.")
            
    except Exception as e:
        st.error(f"Error loading biopharma drugs: {e}")
    
    # Pipeline drugs summary
    if Path("outputs/drug_collection_summary.txt").exists():
        st.subheader("🔬 Pipeline Drugs Summary")
        
        try:
            with open("outputs/drug_collection_summary.txt", "r") as f:
                content = f.read()
            
            # Extract summary info
            lines = content.split('\n')
            summary_lines = [line for line in lines if line.startswith('Pipeline Drugs Found:') or line.startswith('Total Documents:') or line.startswith('Success:')]
            
            if summary_lines:
                for line in summary_lines:
                    st.write(f"**{line}**")
            else:
                st.text_area("Pipeline Drugs Content", content[:500] + "..." if len(content) > 500 else content, height=200)
                
        except Exception as e:
            st.error(f"Error loading pipeline drugs: {e}")
    
    # Recent activity
    st.header("Recent Activity")
    
    try:
        db = get_db()
        recent_docs = db.query(Document).order_by(Document.created_at.desc()).limit(10).all()
        
        if recent_docs:
            doc_data = []
            for doc in recent_docs:
                doc_data.append({
                    "Source": doc.source_type,
                    "Title": doc.title[:50] + "..." if doc.title and len(doc.title) > 50 else doc.title,
                    "URL": doc.source_url,
                    "Retrieved": doc.retrieval_date.strftime("%Y-%m-%d %H:%M")
                })
            
            st.dataframe(pd.DataFrame(doc_data), use_container_width=True)
        else:
            st.info("No documents found. Run data collection to populate the database.")
        
        db.close()
        
    except Exception as e:
        st.error(f"Error loading recent activity: {e}")


def show_data_collection():
    """Show data collection page."""
    st.header("🔄 Data Collection")
    
    st.markdown("""
    This page allows you to collect data from various biomedical sources:
    - **ClinicalTrials.gov**: Clinical trial information
    - **Drugs.com**: Drug profiles and interaction data
    - **FDA**: Regulatory approvals and safety information
    - **Company Websites**: Pharmaceutical company information
    """)
    
    # Collection controls
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Collection Sources")
        clinical_trials = st.checkbox("Clinical Trials", value=True)
        drugs = st.checkbox("Drugs.com", value=True)
        fda = st.checkbox("FDA", value=True)
        company_websites = st.checkbox("Company Websites", value=False)
    
    with col2:
        st.subheader("Actions")
        if st.button("🚀 Start Collection", type="primary"):
            run_data_collection_ui([clinical_trials, drugs, fda, company_websites])
        if st.button("⚙️ Process Documents"):
            try:
                db = get_db()
                summary = run_processing(db)
                st.success(f"Processed: {summary}")
            except Exception as e:
                st.error(f"Processing failed: {e}")
    
    # Collection history
    st.subheader("Collection History")
    st.info("Collection history will be displayed here once implemented.")


def run_data_collection_ui(sources_selected):
    """Run data collection with UI feedback."""
    source_names = []
    if sources_selected[0]:
        source_names.append("clinical_trials")
    if sources_selected[1]:
        source_names.append("drugs")
    if sources_selected[2]:
        source_names.append("fda")
    if sources_selected[3]:
        source_names.append("company_websites")
    
    if not source_names:
        st.warning("Please select at least one data source.")
        return
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("Initializing data collection...")
        progress_bar.progress(10)
        
        # Run collection
        from src.data_collection.orchestrator import DataCollectionOrchestrator
        orchestrator = DataCollectionOrchestrator()
        
        status_text.text("Running data collection...")
        progress_bar.progress(50)
        
        # Note: This is a simplified version. In a real implementation,
        # you'd want to run this in a background thread or use async properly
        results = asyncio.run(orchestrator.run_full_collection(source_names))
        
        progress_bar.progress(100)
        status_text.text("Collection completed!")
        
        # Display results
        st.success("Data collection completed successfully!")
        
        for source, count in results.items():
            st.write(f"**{source.replace('_', ' ').title()}**: {count} documents collected")
        
        # Refresh the page to show updated stats
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during data collection: {e}")
        progress_bar.progress(0)
        status_text.text("Collection failed.")


def show_rag_agent():
    """Show RAG agent page with Ollama integration."""
    st.header("🤖 RAG Agent (Ollama)")
    
    st.markdown("""
    Ask questions about oncology biopartnering opportunities, cancer drug approvals, and clinical trials.
    The AI agent uses Ollama (llama3.1) to provide responses based on your collected biopharma data.
    """)
    
    # Search filters (UI ready, backend implementation pending)
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.write("**Search Options**")
    
    with col2:
        source_filter = st.selectbox("Filter by source", ["All", "clinical_trials", "drugs_com", "fda", "company_website"], help="Filter search results by data source (UI ready, backend implementation pending)")
    
    if source_filter != "All":
        st.info(f"🔧 Source filtering for '{source_filter}' is not yet implemented in the backend. All sources will be searched.")
    
    # Build provider based on sidebar selections
    prov_name = st.session_state.get('provider_selection', settings.model_provider)
    chat_model = st.session_state.get('chat_model_selection', settings.chat_model)
    embed_model = st.session_state.get('embed_model_selection', settings.embed_model)
    
    # Use Basic RAG with selected provider
    if prov_name == "ollama":
        st.info("🤖 Using Basic RAG with Ollama (requires local Ollama installation)")
        agent_type = "Basic RAG (Ollama)"
    else:
        st.info("🤖 Using Basic RAG with OpenAI (cloud-based)")
        agent_type = "Basic RAG (OpenAI)"

    try:
        provider = build_provider(prov_name, chat_model, embed_model, settings.openai_api_key)
    except ValueError as e:
        st.error(f"LLM Provider configuration error: {e}. Please check settings.")
        return

    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Initialize feedback storage
    if "feedback" not in st.session_state:
        st.session_state.feedback = {}
    
    # Chat history controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.write("**Chat History**")
    
    with col2:
        if st.button("🗑️ Clear Chat", help="Clear current chat history"):
            st.session_state.messages = []
            st.session_state.feedback = {}
            st.rerun()
    
    with col3:
        if st.session_state.messages:
            # Create chat history for download
            chat_history = []
            for i, msg in enumerate(st.session_state.messages):
                if msg["role"] == "user":
                    chat_history.append(f"**User:** {msg['content']}")
                else:
                    content = msg["content"]
                    if isinstance(content, dict):
                        answer = content.get("answer", "")
                        confidence = content.get("confidence", 0)
                        chat_history.append(f"**Assistant:** {answer}")
                        chat_history.append(f"*Confidence: {confidence:.2f}*")
                    else:
                        chat_history.append(f"**Assistant:** {content}")
                    
                    # Add rating if available
                    if i in st.session_state.feedback:
                        rating = st.session_state.feedback[i]
                        rating_text = {1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent"}[rating]
                        chat_history.append(f"*User Rating: {rating}/5 ({rating_text})*")
                
                chat_history.append("---")
            
            chat_text = "\n".join(chat_history)
            st.download_button(
                "📥 Download Chat",
                data=chat_text,
                file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="Download current chat history as text file"
            )
    
    # Display chat messages
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict):
                # Enhanced response with structured data
                st.markdown(message["content"].get("answer", ""))
                
                # Show confidence score
                confidence = message["content"].get("confidence", 0)
                st.metric("Confidence", f"{confidence:.2f}")
                
                # Enhanced feedback section for assistant messages
                render_enhanced_feedback(i, message["role"])
                
                # Show drugs mentioned
                drugs = message["content"].get("drugs_mentioned", [])
                if drugs:
                    with st.expander(f"Drugs Mentioned ({len(drugs)})"):
                        for drug in drugs:
                            st.write(f"**{drug.generic_name}** ({drug.company})")
                            if drug.brand_name:
                                st.write(f"Brand: {drug.brand_name}")
                            if drug.drug_class:
                                st.write(f"Class: {drug.drug_class}")
                            if drug.indication:
                                st.write(f"Indication: {drug.indication}")
                            st.write("---")
                
                # Show clinical trials
                trials = message["content"].get("trials_mentioned", [])
                if trials:
                    with st.expander(f"Clinical Trials ({len(trials)})"):
                        for trial in trials:
                            st.write(f"**{trial.title}**")
                            if trial.nct_id:
                                st.write(f"NCT: {trial.nct_id}")
                            if trial.phase:
                                st.write(f"Phase: {trial.phase}")
                            if trial.status:
                                st.write(f"Status: {trial.status}")
                            st.write("---")
                
                # Show biopartnering insights
                insights = message["content"].get("insights", [])
                if insights:
                    with st.expander(f"Biopartnering Insights ({len(insights)})"):
                        for insight in insights:
                            st.write(f"**{insight.title}**")
                            st.write(f"Type: {insight.insight_type}")
                            st.write(f"Description: {insight.description}")
                            st.write(f"Confidence: {insight.confidence:.2f}")
                            st.write("---")
                
                # Show citations
                citations = message["content"].get("citations", [])
                if citations:
                    with st.expander("Citations"):
                        for c in citations:
                            st.write(f"[{c.label}] {c.title} - {c.url}")
            else:
                # Basic text response
                st.markdown(message["content"])
                
                # Enhanced feedback section for assistant messages
                render_enhanced_feedback(i, message["role"])
    
    # Chat input
    if prompt := st.chat_input("Ask about biopartner opportunities, cancer drugs, clinical trials, or oncology partnerships..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            try:
                db = get_db()
                
                # Use enhanced basic RAG agent with Ollama
                agent = create_enhanced_basic_rag_agent(provider)
                result = agent.answer(db, prompt, k=5)
                
                # Display response
                answer = result["answer"]
                st.markdown(answer)
                
                # Show drugs if found
                if result.get("drugs"):
                    with st.expander(f"Drugs Found ({len(result['drugs'])})"):
                        for drug in result["drugs"]:
                            st.write(f"**{drug['generic_name']}** ({drug['brand_name']})")
                            st.write(f"Company: {drug['company']}")
                            st.write(f"Class: {drug['drug_class']}")
                            st.write(f"Target: {drug['target']}")
                            st.write(f"FDA Approved: {drug['fda_approved']}")
                            if drug['approval_date']:
                                st.write(f"Approval Date: {drug['approval_date']}")
                            st.write("---")
                
                # Show clinical trials if found
                if result.get("trials"):
                    with st.expander(f"Clinical Trials ({len(result['trials'])})"):
                        for trial in result["trials"]:
                            st.write(f"**{trial['title']}**")
                            st.write(f"NCT ID: {trial['nct_id']}")
                            st.write(f"Status: {trial['status']}")
                            st.write(f"Phase: {trial['phase']}")
                            st.write("---")
                
                # Show citations if available
                if result.get("citations"):
                    with st.expander("Citations"):
                        for c in result["citations"]:
                            st.write(f"[{c['label']}] {c['title']} - {c['url']}")
                
                st.session_state.messages.append({"role": "assistant", "content": answer})
                    
            except Exception as e:
                st.error(f"RAG error: {e}")
                import traceback
                st.error(traceback.format_exc())
    
    # Follow-up questions section (show after assistant responses)
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.markdown("### 💡 Suggested Follow-up Questions")
        
        # Generate follow-up questions based on the last response
        last_response = st.session_state.messages[-1]["content"]
        if isinstance(last_response, dict):
            answer_text = last_response.get("answer", "")
        else:
            answer_text = str(last_response)
        
        # Generate contextual follow-up questions
        follow_up_questions = generate_follow_up_questions(answer_text, "")
        
        # Display follow-up questions as clickable buttons
        cols = st.columns(2)
        for i, question in enumerate(follow_up_questions[:4]):  # Show up to 4 questions
            col_idx = i % 2
            with cols[col_idx]:
                if st.button(f"❓ {question}", key=f"followup_{i}", help="Click to ask this follow-up question"):
                    # Add the follow-up question as a new user message
                    st.session_state.messages.append({"role": "user", "content": question})
                    st.rerun()
        
        st.markdown("---")
    
    # Feedback summary
    if st.session_state.feedback:
        st.subheader("📊 Feedback Summary")
        
        ratings = list(st.session_state.feedback.values())
        total_feedback = len(ratings)
        average_rating = sum(ratings) / total_feedback if total_feedback > 0 else 0
        
        # Count ratings by category
        excellent_count = sum(1 for r in ratings if r == 5)
        very_good_count = sum(1 for r in ratings if r == 4)
        good_count = sum(1 for r in ratings if r == 3)
        fair_count = sum(1 for r in ratings if r == 2)
        poor_count = sum(1 for r in ratings if r == 1)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Responses", len(st.session_state.messages))
        
        with col2:
            st.metric("Average Rating", f"{average_rating:.1f}/5")
        
        with col3:
            st.metric("Excellent (5⭐)", excellent_count)
        
        with col4:
            st.metric("Poor (1⭐)", poor_count)
        
        # Rating distribution
        st.write("**Rating Distribution:**")
        rating_dist_col1, rating_dist_col2 = st.columns([3, 1])
        
        with rating_dist_col1:
            st.bar_chart({
                "5⭐": excellent_count,
                "4⭐": very_good_count,
                "3⭐": good_count,
                "2⭐": fair_count,
                "1⭐": poor_count
            })
        
        with rating_dist_col2:
            st.write(f"**Quality Score:**")
            if average_rating >= 4.5:
                st.success(f"🌟 {average_rating:.1f}/5 - Excellent!")
            elif average_rating >= 3.5:
                st.info(f"✅ {average_rating:.1f}/5 - Good")
            elif average_rating >= 2.5:
                st.warning(f"⚠️ {average_rating:.1f}/5 - Fair")
            else:
                st.error(f"❌ {average_rating:.1f}/5 - Needs Improvement")
        
        # Download feedback data
        if st.button("📥 Download Feedback Data"):
            feedback_data = []
            for i, msg in enumerate(st.session_state.messages):
                if msg["role"] == "assistant" and i in st.session_state.feedback:
                    rating = st.session_state.feedback[i]
                    rating_text = {1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent"}[rating]
                    
                    feedback_data.append({
                        "message_index": i,
                        "question": st.session_state.messages[i-1]["content"] if i > 0 else "N/A",
                        "response": msg["content"] if isinstance(msg["content"], str) else msg["content"].get("answer", ""),
                        "rating": rating,
                        "rating_text": rating_text,
                        "timestamp": datetime.now().isoformat()
                    })
            
            if feedback_data:
                import json
                feedback_json = json.dumps(feedback_data, indent=2)
                st.download_button(
                    "📥 Download Feedback JSON",
                    data=feedback_json,
                    file_name=f"feedback_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    help="Download feedback data as JSON file"
                )
        
        # Enhanced detailed feedback analysis
        if "detailed_feedback" in st.session_state and st.session_state.detailed_feedback:
            st.subheader("🔍 Detailed Feedback Analysis")
            
            # Analyze feedback patterns
            feedback_analysis = analyze_feedback_patterns(st.session_state.detailed_feedback)
            
            if feedback_analysis["total_responses"] > 0:
                # Show issue breakdown
                st.write("**Common Issues Identified:**")
                issue_percentages = feedback_analysis["issue_percentages"]
                
                if issue_percentages:
                    issue_df = pd.DataFrame([
                        {"Issue": issue.replace("_", " ").title(), "Percentage": f"{percentage:.1f}%", "Count": feedback_analysis["issue_counts"][issue]}
                        for issue, percentage in sorted(issue_percentages.items(), key=lambda x: x[1], reverse=True)
                    ])
                    st.dataframe(issue_df, use_container_width=True)
                    
                    # Improvement recommendations
                    recommendations = get_improvement_recommendations(feedback_analysis)
                    
                    if recommendations:
                        st.subheader("💡 Improvement Recommendations")
                        
                        for rec in recommendations:
                            priority_color = {
                                "High": "🔴",
                                "Medium": "🟡", 
                                "Low": "🟢"
                            }.get(rec["priority"], "⚪")
                            
                            st.write(f"{priority_color} **{rec['issue']}** ({rec['percentage']:.1f}% of responses)")
                            st.write(f"   {rec['recommendation']}")
                            st.write("")
                else:
                    st.info("No specific issues identified in detailed feedback.")
            
            # Download enhanced feedback data using the new module
            if st.button("📥 Download Enhanced Feedback Data"):
                enhanced_feedback_json = export_feedback_data(
                    st.session_state.feedback,
                    st.session_state.detailed_feedback,
                    st.session_state.messages
                )
                
                st.download_button(
                    "📥 Download Enhanced Feedback JSON",
                    data=enhanced_feedback_json,
                    file_name=f"enhanced_feedback_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    help="Download detailed feedback data as JSON file"
                )


def show_results():
    """Show results page with CSV data and exports."""
    st.header("📈 Results & Exports")
    
    # Check if CSV files exist
    csv_files = {
        "Biopharma Drugs": "outputs/biopharma_drugs.csv",
        "Drug Collection Summary": "outputs/drug_collection_summary.txt"
    }
    
    # Display available files
    st.subheader("📁 Available Output Files")
    
    for name, file_path in csv_files.items():
        if Path(file_path).exists():
            st.success(f"✅ {name}: {file_path}")
        else:
            st.warning(f"❌ {name}: {file_path} (not found)")
    
    # Display biopharma_drugs.csv if it exists
    if Path("outputs/biopharma_drugs.csv").exists():
        st.subheader("💊 Biopharma Drugs Data")
        
        try:
            df = pd.read_csv("outputs/biopharma_drugs.csv")
            
            # Show basic stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Drugs", len(df))
            with col2:
                st.metric("Companies", len(df['Company name'].unique()) if 'Company name' in df.columns else 0)
            with col3:
                st.metric("Drugs with Brand Names", len(df[df['Brand name'].notna() & (df['Brand name'] != '')]))
            with col4:
                st.metric("FDA Approved", len(df[df['FDA Approval'].notna() & (df['FDA Approval'] != '')]))
            
            # Display the data
            st.dataframe(df, use_container_width=True)
            
            # Download button
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Biopharma Drugs CSV",
                data=csv_data,
                file_name=f"biopharma_drugs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
    
    # Display drug collection summary if it exists (includes pipeline drugs)
    if Path("outputs/drug_collection_summary.txt").exists():
        st.subheader("🔬 Pipeline Drugs by Company")
        
        try:
            with open("outputs/drug_collection_summary.txt", "r") as f:
                content = f.read()
            
            st.text_area("Pipeline Drugs Content", content, height=400)
            
            # Download button
            st.download_button(
                label="📥 Download Drug Collection Summary TXT",
                data=content,
                file_name=f"drug_collection_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Error loading drug collection summary: {e}")
    
    
    # Export options
    st.subheader("🚀 Generate New Exports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Export Drug Table", type="primary"):
            try:
                export_drug_table("outputs/drug_table_export.csv")
                st.success("✅ Drug table exported successfully!")
            except Exception as e:
                st.error(f"Export error: {e}")
    
    with col2:
        if st.button("📋 Export Basic Data"):
            try:
                export_basic("outputs/basic_export.csv")
                st.success("✅ Basic data exported successfully!")
            except Exception as e:
                st.error(f"Export error: {e}")


def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")
    
    st.subheader("Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Data Sources**")
        st.write(f"- Clinical Trials: {settings.clinical_trials_base_url}")
        st.write(f"- Drugs.com: {settings.drugs_com_base_url}")
        st.write(f"- FDA: {settings.fda_base_url}")
    
    with col2:
        st.write("**Collection Settings**")
        st.write(f"- Max Concurrent Requests: {settings.max_concurrent_requests}")
        st.write(f"- Request Delay: {settings.request_delay}s")
        st.write(f"- Refresh Schedule: {settings.refresh_schedule}")
        st.write("\n**Exports**")
        if st.button("Export standardized CSV"):
            try:
                db = get_db()
                out_path = export_basic(db, "outputs/biopartnering_data.csv")
                with open(out_path, "rb") as f:
                    st.download_button("Download CSV", f, file_name="biopartnering_data.csv", mime="text/csv")
            except Exception as e:
                st.error(f"Export failed: {e}")
        if st.button("Export drug table (requested schema)"):
            try:
                db = get_db()
                out_path = export_drug_table(db, "outputs/biopharma_drugs.csv")
                with open(out_path, "rb") as f:
                    st.download_button("Download Drug CSV", f, file_name="biopharma_drugs.csv", mime="text/csv")
            except Exception as e:
                st.error(f"Export failed: {e}")
    
    st.subheader("Target Companies")
    st.write("Currently tracking the following companies:")
    
    # Display companies in a grid (CSV-backed with fallback)
    tracked_companies = get_target_companies()
    cols = st.columns(3)
    for i, company in enumerate(tracked_companies):
        with cols[i % 3]:
            st.write(f"• {company}")
    
    # Cache Management Section
    st.subheader("RAG Cache Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Cache Statistics**")
        try:
            cache_manager = RAGCacheManager()
            cache_stats = cache_manager.get_cache_stats(get_db())
            
            st.write(f"- Total Cache Entries: {cache_stats.get('total_entries', 0)}")
            st.write(f"- Valid Entries: {cache_stats.get('valid_entries', 0)}")
            st.write(f"- Expired Entries: {cache_stats.get('expired_entries', 0)}")
            
            if cache_stats.get('most_accessed'):
                st.write("\n**Most Accessed Queries:**")
                for i, entry in enumerate(cache_stats['most_accessed'][:3], 1):
                    st.write(f"  {i}. {entry['query'][:50]}... ({entry['access_count']} times)")
                    
        except Exception as e:
            st.error(f"Error loading cache stats: {e}")
    
    with col2:
        st.write("**Cache Actions**")
        if st.button("🧹 Clean Expired Cache"):
            try:
                cache_manager = RAGCacheManager()
                cleaned = cache_manager.cleanup_expired_cache(get_db())
                st.success(f"Cleaned {cleaned} expired cache entries")
                st.rerun()
            except Exception as e:
                st.error(f"Cache cleanup failed: {e}")
        
        if st.button("🗑️ Clear All Cache"):
            try:
                cache_manager = RAGCacheManager()
                cleared = cache_manager.invalidate_cache(get_db())
                st.success(f"Cleared {cleared} cache entries")
                st.rerun()
            except Exception as e:
                st.error(f"Cache clear failed: {e}")
        
        if st.button("🔄 Refresh Cache Stats"):
            st.rerun()


def show_evaluation():
    """Show evaluation page with RAGAS metrics using Ollama."""
    st.header("📊 RAG Evaluation with Ollama")
    
    st.markdown("""
    Evaluate the performance of your RAG system using RAGAS metrics powered by Ollama.
    This evaluation uses local models to assess faithfulness, answer relevancy, context precision, and context recall.
    """)
    
    # Evaluation settings
    col1, col2 = st.columns(2)
    
    with col1:
        use_ollama = st.checkbox("Use Ollama for Evaluation", value=True, help="Use local Ollama models instead of OpenAI")
        ollama_model = st.selectbox("Ollama Model", ["llama3.1", "llama3.2"], index=0)
    
    with col2:
        num_questions = st.slider("Number of Test Questions", 1, 10, 5)
        evaluation_type = st.selectbox("Evaluation Type", ["Predefined Questions", "Custom Questions"])
    
    # Predefined test questions
    predefined_questions = [
        "What cancer drugs does Merck have in their pipeline?",
        "What is pembrolizumab used for?",
        "What clinical trials are Bristol Myers Squibb running?",
        "What are the latest FDA approvals for cancer drugs?",
        "What immunotherapy drugs are available?",
        "What targeted therapies exist for lung cancer?",
        "What are the side effects of checkpoint inhibitors?",
        "What combination therapies are being tested?",
        "What biomarkers are used for cancer treatment?",
        "What are the latest advances in CAR-T therapy?"
    ]
    
    # Get test questions
    if evaluation_type == "Predefined Questions":
        test_questions = predefined_questions[:num_questions]
        st.subheader("Test Questions")
        for i, q in enumerate(test_questions, 1):
            st.write(f"{i}. {q}")
    else:
        st.subheader("Custom Questions")
        test_questions = []
        for i in range(num_questions):
            question = st.text_input(f"Question {i+1}", key=f"custom_q_{i}")
            if question:
                test_questions.append(question)
    
    # Run evaluation
    if st.button("🚀 Run Evaluation", type="primary"):
        if not test_questions:
            st.error("Please provide at least one test question.")
            return
        
        # Build provider and agent
        try:
            provider = build_provider(settings.model_provider, settings.chat_model, settings.embed_model, settings.openai_api_key)
            agent = create_enhanced_basic_rag_agent(provider)
            
            # Show progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Run evaluation
            with st.spinner("Running RAGAS evaluation with Ollama..."):
                status_text.text("Initializing evaluation...")
                progress_bar.progress(0.1)
                
                db = get_db()
                
                status_text.text("Evaluating RAG agent...")
                progress_bar.progress(0.3)
                
                # Run evaluation
                scores = evaluate_rag_agent(
                    agent, 
                    db, 
                    test_questions, 
                    use_ollama=use_ollama
                )
                
                progress_bar.progress(1.0)
                status_text.text("Evaluation complete!")
                
                db.close()
            
            # Display results
            st.subheader("📈 Evaluation Results")
            
            # Create metrics display
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Faithfulness", 
                    f"{scores.get('faithfulness', 0):.3f}",
                    help="Measures how grounded the generated answer is in the given contexts"
                )
            
            with col2:
                st.metric(
                    "Answer Relevancy", 
                    f"{scores.get('answer_relevancy', 0):.3f}",
                    help="Measures how relevant the generated answer is to the given question"
                )
            
            with col3:
                st.metric(
                    "Context Precision", 
                    f"{scores.get('context_precision', 0):.3f}",
                    help="Measures how precise the retrieved contexts are"
                )
            
            with col4:
                st.metric(
                    "Context Recall", 
                    f"{scores.get('context_recall', 0):.3f}",
                    help="Measures how well the retrieved contexts cover the answer"
                )
            
            # Overall score
            overall_score = sum(scores.values()) / len(scores) if scores else 0
            st.metric("Overall Score", f"{overall_score:.3f}")
            
            # Interpretation
            st.subheader("📝 Interpretation")
            
            if overall_score >= 0.8:
                st.success("🎉 Excellent performance! Your RAG system is working very well.")
            elif overall_score >= 0.6:
                st.info("✅ Good performance. Consider fine-tuning for better results.")
            elif overall_score >= 0.4:
                st.warning("⚠️ Moderate performance. There's room for improvement.")
            else:
                st.error("❌ Poor performance. The system needs significant improvements.")
            
            # Detailed breakdown
            with st.expander("📊 Detailed Metrics"):
                st.write("**Faithfulness (0-1):** How well the answer is grounded in the provided contexts")
                st.write("**Answer Relevancy (0-1):** How relevant the answer is to the question")
                st.write("**Context Precision (0-1):** How precise the retrieved contexts are")
                st.write("**Context Recall (0-1):** How well contexts cover the answer")
                
                # Show raw scores
                st.write("\n**Raw Scores:**")
                for metric, score in scores.items():
                    st.write(f"- {metric}: {score:.4f}")
            
            # Recommendations
            st.subheader("💡 Recommendations")
            
            if scores.get('faithfulness', 0) < 0.7:
                st.write("• **Improve Faithfulness:** Ensure answers are better grounded in retrieved contexts")
            
            if scores.get('answer_relevancy', 0) < 0.7:
                st.write("• **Improve Answer Relevancy:** Fine-tune the prompt or model to better address questions")
            
            if scores.get('context_precision', 0) < 0.7:
                st.write("• **Improve Context Precision:** Better retrieval strategies or document preprocessing")
            
            if scores.get('context_recall', 0) < 0.7:
                st.write("• **Improve Context Recall:** Increase the number of retrieved documents or improve retrieval")
            
        except Exception as e:
            st.error(f"Evaluation failed: {e}")
            import traceback
            st.error(traceback.format_exc())
    
    # Evaluation info
    st.subheader("ℹ️ About RAGAS Evaluation")
    st.markdown("""
    **RAGAS (RAG Assessment)** is a framework for evaluating RAG systems with the following metrics:
    
    - **Faithfulness**: Measures how grounded the generated answer is in the given contexts
    - **Answer Relevancy**: Measures how relevant the generated answer is to the given question  
    - **Context Precision**: Measures how precise the retrieved contexts are
    - **Context Recall**: Measures how well the retrieved contexts cover the answer
    
    **Using Ollama**: This evaluation uses local Ollama models instead of requiring OpenAI API keys,
    making it more cost-effective and privacy-friendly for evaluation purposes.
    """)


if __name__ == "__main__":
    main()
