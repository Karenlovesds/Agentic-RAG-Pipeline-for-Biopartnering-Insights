"""Streamlit UI for Biopartnering Insights Pipeline."""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import pandas as pd
import io
import uuid
import json
from datetime import datetime
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.models.database import get_db
from src.models.entities import Document, Company, Drug, ClinicalTrial, Target, DrugTarget
from config.config import settings, get_target_companies
from src.rag.react_rag_agent import ReactRAGAgent
from src.evaluation.feedback_manager import FeedbackManager, create_feedback_tables
from src.rag.cache_manager import RAGCacheManager
from src.processing.csv_export import export_drug_table
from src.processing.pipeline import run_processing
from src.evaluation.react_agent_eval import evaluate_react_agent
from src.evaluation.feedback_analyzer import (
    get_enhanced_feedback_analysis,
    get_feedback_trends,
    get_rag_improvement_plan,
    get_detailed_feedback_options,
    analyze_feedback_patterns,
    get_improvement_recommendations,
    export_feedback_data
)
from src.analysis.market_analysis_dashboard import main_market_analysis_dashboard
from src.analysis.overlap_dashboard import main_overlap_dashboard
from src.rag.ground_truth_loader import GroundTruthLoader


# Initialize feedback tables on startup
try:
    create_feedback_tables()
    logger.info("Feedback tables initialized successfully")
except Exception as e:
    logger.error(f"Error initializing feedback tables: {e}")

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
    
    # Initialize feedback manager
    if "feedback_manager" not in st.session_state:
        st.session_state.feedback_manager = FeedbackManager()
    
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
            
            # Auto-save feedback to database
            try:
                session_id = st.session_state.get("session_id", str(uuid.uuid4()))
                if "session_id" not in st.session_state:
                    st.session_state.session_id = session_id
                
                # Get question and response
                question = None
                response = None
                if message_index > 0 and message_index < len(st.session_state.messages):
                    if message_index > 0:
                        question = st.session_state.messages[message_index - 1].get("content", "")
                    response = st.session_state.messages[message_index].get("content", "")
                
                # Save to database
                success = st.session_state.feedback_manager.save_feedback(
                    session_id=session_id,
                    message_index=message_index,
                    rating=rating,
                    detailed_issues=st.session_state.detailed_feedback.get(message_index, []),
                    question=question,
                    response=response,
                    user_agent=st.get_option("browser.serverAddress")
                )
                
                if success:
                    st.info("💾 Feedback saved automatically!")
                else:
                    st.warning("⚠️ Could not save feedback to database")
                    
            except Exception as e:
                logger.error(f"Error saving feedback: {e}")
                st.warning("⚠️ Could not save feedback to database")
        
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
            
            # Auto-save detailed feedback to database
            try:
                session_id = st.session_state.get("session_id", str(uuid.uuid4()))
                if "session_id" not in st.session_state:
                    st.session_state.session_id = session_id
                
                # Get question and response
                question = None
                response = None
                if message_index > 0 and message_index < len(st.session_state.messages):
                    if message_index > 0:
                        question = st.session_state.messages[message_index - 1].get("content", "")
                    response = st.session_state.messages[message_index].get("content", "")
                
                # Save detailed feedback to database
                rating = st.session_state.feedback.get(message_index, 3)
                success = st.session_state.feedback_manager.save_feedback(
                    session_id=session_id,
                    message_index=message_index,
                    rating=rating,
                    detailed_issues=st.session_state.detailed_feedback[message_index],
                    question=question,
                    response=response,
                    user_agent=st.get_option("browser.serverAddress")
                )
                
                if success:
                    st.info("💾 Detailed feedback saved!")
                    
            except Exception as e:
                logger.error(f"Error saving detailed feedback: {e}")
                st.warning("⚠️ Could not save detailed feedback")
    
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
    """Generate unified follow-up questions for all biopharmaceutical queries."""
    
    # Unified set of comprehensive follow-up questions for all queries
    follow_up_questions = [
        "What other companies are targeting this same target?",
        "What are the different mechanisms of action for this target?",
        "Which drugs are in clinical trials for this target?",
        "What is the competitive landscape for this target?",
        "Which indications are being targeted with this target?",
        "What are the latest developments in this area?"
    ]
    
    return follow_up_questions


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
            ["Dashboard", "Data Collection", "Agentic RAG", "Ground Truth", "Market Analysis", "Overlap Analysis", "Results", "Evaluation", "Feedback Analytics", "Settings"]
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
        
        st.header("Agentic RAG Agent")
        st.info("🤖 Using Enhanced Agentic RAG with Vector Database")
        
        if st.button("Test Agentic RAG"):
            try:
                react_agent = ReactRAGAgent(settings)
                result = react_agent.generate_response("Say hello in one short sentence.")
                st.success(f"Agentic RAG OK. Sample reply: {result['answer'][:100]}")
            except Exception as e:
                st.error(f"Agentic RAG test failed: {e}")

        
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
    elif page == "Agentic RAG":
        show_rag_agent()
    elif page == "Ground Truth":
        show_ground_truth()
    elif page == "Market Analysis":
        main_market_analysis_dashboard()
    elif page == "Overlap Analysis":
        main_overlap_dashboard()
    elif page == "Results":
        show_results()
    elif page == "Evaluation":
        show_evaluation()
    elif page == "Feedback Analytics":
        show_feedback_analytics()
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
        async def collect_from_sources(sources):
            results = {}
            
            if "clinical_trials" in sources:
                ct_collector = ClinicalTrialsCollector()
                ct_data = await ct_collector.collect_data()
                results['clinical_trials'] = sum(1 for d in ct_data if ct_collector._save_document(d))
            
            if "company_websites" in sources:
                cw_collector = CompanyWebsiteCollector()
                cw_data = await cw_collector.collect_data()
                results['company_websites'] = sum(1 for d in cw_data if cw_collector._save_document(d))
            
            if "drugs" in sources:
                drugs_collector = DrugsCollector()
                drugs_data = await drugs_collector.collect_data()
                results['drugs'] = sum(1 for d in drugs_data if drugs_collector._save_document(d))
            
            return results
        
        status_text.text("Running data collection...")
        progress_bar.progress(50)
        
        # Run collection
        results = asyncio.run(collect_from_sources(source_names))
        
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
    """Show Agentic RAG agent page."""
    st.header("🤖 Agentic RAG")
    
    st.markdown("""
    **🧠 React Framework Agent**: Uses reasoning, acting, and observing to provide more reliable answers.
    - **Reasoning**: Thinks through problems step-by-step
    - **Acting**: Uses tools to search databases and ground truth
    - **Observing**: Analyzes results and decides next steps
    - **Iterative**: Can refine answers based on observations
    - **Cross-Validation**: Compares data across multiple sources for accuracy
    """)
    
    # Search filters (UI ready, backend implementation pending)
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.write("**Search Options**")
    
    with col2:
        st.write("**Chat Controls**")
    

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
            # Simple text display for React agent responses
            st.markdown(message["content"])
            
            # Enhanced feedback section for assistant messages
            if message["role"] == "assistant":
                render_enhanced_feedback(i, message["role"])
    
    # Chat input
    if prompt := st.chat_input("Ask about biopartner opportunities, cancer drugs, clinical trials, or oncology partnerships..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response using React Framework agent
        with st.chat_message("assistant"):
            try:
                # Session-scoped React agent with persistent memory
                if "react_agent" not in st.session_state:
                    st.session_state.react_agent = ReactRAGAgent(settings)
                result = st.session_state.react_agent.generate_response(prompt)
                answer = result["answer"]
                
                # Display response
                st.markdown(answer)
                
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
        for i, question in enumerate(follow_up_questions[:6]):  # Show up to 6 questions
            col_idx = i % 2
            with cols[col_idx]:
                if st.button(f"❓ {question}", key=f"followup_{i}", help="Click to ask this follow-up question"):
                    # Add the follow-up question as a new user message
                    st.session_state.messages.append({"role": "user", "content": question})
                    
                    # Process the follow-up question immediately
                    with st.chat_message("user"):
                        st.markdown(question)
                    
                    # Generate response using React Framework agent
                    with st.chat_message("assistant"):
                        try:
                            # Reuse session-scoped agent to preserve memory
                            if "react_agent" not in st.session_state:
                                st.session_state.react_agent = ReactRAGAgent(settings)
                            result = st.session_state.react_agent.generate_response(question)
                            answer = result["answer"]
                            
                            # Display response
                            st.markdown(answer)
                            
                            # Show citations if available
                            if result.get("citations"):
                                with st.expander("Citations"):
                                    for c in result["citations"]:
                                        st.write(f"[{c['label']}] {c['title']} - {c['url']}")
                            
                            st.session_state.messages.append({"role": "assistant", "content": answer})
                            
                        except Exception as e:
                            st.error(f"Error generating response: {e}")
                            logger.error(f"React agent error: {e}")
                            st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
                    
                    st.rerun()
        
        st.markdown("---")

    
    
    # Database Feedback Analytics
    
    # Initialize feedback manager if not exists
    if "feedback_manager" not in st.session_state:
        st.session_state.feedback_manager = FeedbackManager()
    
    # Feedback metrics removed - no longer showing empty metrics

    # Current Session Feedback section removed - no longer showing session metrics
    


def show_feedback_analytics():
    """Show dedicated Feedback Analytics dashboard."""
    st.header("🚀 Enhanced Feedback Analytics")
    
    st.markdown("""
    **📊 Comprehensive Feedback Analysis Dashboard**
    
    This dashboard provides detailed insights into user feedback patterns, system performance, and actionable improvement recommendations.
    """)
    
    # Initialize feedback storage
    if "feedback" not in st.session_state:
        st.session_state.feedback = {}
    
    if "detailed_feedback" not in st.session_state:
        st.session_state.detailed_feedback = {}
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Initialize feedback manager if not exists
    if "feedback_manager" not in st.session_state:
        st.session_state.feedback_manager = FeedbackManager()
    
    # Tabs for different analysis views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Comprehensive Analysis", "📈 Trends & Patterns", "🎯 Improvement Plan", "💾 Data Export"])
    
    with tab1:
        st.write("**Comprehensive analysis combining database persistence with advanced pattern recognition**")
        
        try:
            enhanced_analysis = get_enhanced_feedback_analysis(days=30)
            
            if enhanced_analysis.get("status") == "success":
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Records", enhanced_analysis.get("total_records", 0))
                
                with col2:
                    avg_rating = enhanced_analysis.get("summary", {}).get("average_rating", 0)
                    st.metric("Average Rating", f"{avg_rating}/5")
                
                with col3:
                    system_health = enhanced_analysis.get("insights", {}).get("system_health", "Unknown")
                    if system_health == "Excellent":
                        st.success(f"🌟 {system_health}")
                    elif system_health == "Good":
                        st.info(f"✅ {system_health}")
                    elif system_health == "Fair":
                        st.warning(f"⚠️ {system_health}")
                    else:
                        st.error(f"❌ {system_health}")
                
                # Top issues with percentages
                top_issues = enhanced_analysis.get("insights", {}).get("top_issues", [])
                if top_issues:
                    st.write("**🔍 Top Issues:**")
                    for issue_data in top_issues:
                        issue = issue_data.get("issue", "").replace("_", " ").title()
                        percentage = issue_data.get("percentage", 0)
                        st.write(f"• {issue}: {percentage:.1f}%")
                
                # Recommendations
                recommendations = enhanced_analysis.get("recommendations", [])
                if recommendations:
                    st.write("**💡 Improvement Recommendations:**")
                    for rec in recommendations[:3]:  # Show top 3
                        priority_color = "🔴" if rec.get("priority") == "High" else "🟡"
                        st.write(f"{priority_color} **{rec.get('issue')}** ({rec.get('percentage', 0):.1f}%)")
                        st.write(f"   {rec.get('recommendation')}")
                
            elif enhanced_analysis.get("status") == "no_data":
                st.info("No feedback data found yet. Start rating responses to build comprehensive analytics!")
            else:
                st.error(f"Analysis error: {enhanced_analysis.get('message', 'Unknown error')}")
                
        except Exception as e:
            st.error(f"Error loading enhanced analysis: {e}")
    
    with tab2:
        st.write("**Trend analysis showing feedback patterns over time**")
        
        try:
            trends = get_feedback_trends(days=30)
            
            if trends.get("status") == "success":
                st.write("**📅 Analysis Period:**", trends.get("analysis_period", "Unknown"))
                
                # Show trend summary
                daily_trends = trends.get("daily_trends", {})
                if daily_trends:
                    st.write("**Daily Rating Trends:**")
                    # Convert to a more readable format
                    for date, metrics in daily_trends.items():
                        if isinstance(metrics, dict) and 'mean' in str(metrics):
                            st.write(f"• {date}: {metrics}")
                
                # Issue trends
                issue_trends = trends.get("issue_trends", {})
                if issue_trends:
                    st.write("**Issue Trends Over Time:**")
                    for issue, dates in issue_trends.items():
                        issue_name = issue.replace("_", " ").title()
                        total_reports = sum(dates.values())
                        st.write(f"• {issue_name}: {total_reports} total reports")
            else:
                st.info("No trend data available yet. Collect more feedback to see patterns!")
                
        except Exception as e:
            st.error(f"Error loading trends: {e}")
    
    with tab3:
        st.write("**Actionable improvement plan based on feedback analysis**")
        
        try:
            improvement_plan = get_rag_improvement_plan(days=30)
            
            if improvement_plan.get("status") == "success":
                # System health
                system_health = improvement_plan.get("system_health", "Unknown")
                st.write(f"**🏥 System Health:** {system_health}")
                
                # Quick wins
                quick_wins = improvement_plan.get("quick_wins", [])
                if quick_wins:
                    st.write("**⚡ Quick Wins (High Priority):**")
                    for win in quick_wins:
                        st.write(f"• **{win.get('issue')}** ({win.get('impact', 0):.1f}% impact)")
                        st.write(f"  {win.get('action')}")
                        st.write(f"  Timeline: {win.get('timeline', 'Unknown')}")
                
                # All action items
                action_items = improvement_plan.get("action_items", [])
                if action_items:
                    st.write("**📋 Complete Action Plan:**")
                    for item in action_items:
                        priority_icon = "🔴" if item.get("priority") == "High" else "🟡"
                        st.write(f"{priority_icon} **{item.get('issue')}** ({item.get('impact', 0):.1f}% impact)")
                        st.write(f"   Action: {item.get('action')}")
                        st.write(f"   Timeline: {item.get('timeline', 'Unknown')}")
                        st.write("")
                
                # Data quality
                data_quality = improvement_plan.get("data_quality", {})
                st.write("**📊 Data Quality:**")
                st.write(f"• Total Responses: {data_quality.get('total_responses', 0)}")
                st.write(f"• Response Rate: {data_quality.get('response_rate', 'Unknown')}")
                
            else:
                st.info("No improvement plan available yet. Collect more feedback to generate actionable insights!")
                
        except Exception as e:
            st.error(f"Error loading improvement plan: {e}")
    
    with tab4:
        st.write("**Export and download feedback data**")
        
        # Database Feedback Analytics
        st.subheader("📊 Database Feedback Analytics")
        
        # Get feedback summary from database
        try:
            feedback_summary = st.session_state.feedback_manager.get_feedback_summary(days=30)
            
            if feedback_summary.get("total_feedback", 0) > 0:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Feedback (30 days)", feedback_summary["total_feedback"])
                
                with col2:
                    st.metric("Average Rating", f"{feedback_summary['average_rating']}/5")
                
                with col3:
                    quality_score = feedback_summary.get("quality_score", "Unknown")
                    if quality_score == "Excellent":
                        st.success(f"🌟 {quality_score}")
                    elif quality_score == "Good":
                        st.info(f"✅ {quality_score}")
                    elif quality_score == "Fair":
                        st.warning(f"⚠️ {quality_score}")
                    else:
                        st.error(f"❌ {quality_score}")
                
                # Top issues
                if feedback_summary.get("top_issues"):
                    st.write("**🔍 Top Issues:**")
                    for issue, count in feedback_summary["top_issues"][:3]:
                        st.write(f"• {issue.replace('_', ' ').title()}: {count} reports")
                
                # Download database feedback
                if st.button("📥 Download Database Feedback"):
                    feedback_json = st.session_state.feedback_manager.export_feedback_to_json(days=30)
                    st.download_button(
                        "📥 Download Database Feedback JSON",
                        data=feedback_json,
                        file_name=f"database_feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        help="Download all feedback data from database"
                    )
            else:
                st.info("No feedback data found in database yet. Start rating responses to build analytics!")
                
        except Exception as e:
            st.error(f"Error loading database feedback: {e}")
            logger.error(f"Database feedback error: {e}")

        # Session Feedback Summary
        if st.session_state.feedback:
            st.subheader("📊 Current Session Feedback")
            
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
                st.write("**Quick Stats:**")
                st.write(f"• Total: {total_feedback}")
                st.write(f"• Avg: {average_rating:.1f}")
                st.write(f"• Best: {excellent_count}")
                st.write(f"• Worst: {poor_count}")
            
            # Download session feedback
            if st.button("📥 Download Session Feedback"):
                session_feedback_data = {
                    "session_id": st.session_state.get("session_id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "total_responses": len(st.session_state.messages),
                    "total_feedback": total_feedback,
                    "average_rating": average_rating,
                    "rating_distribution": {
                        "excellent": excellent_count,
                        "very_good": very_good_count,
                        "good": good_count,
                        "fair": fair_count,
                        "poor": poor_count
                    },
                    "detailed_feedback": st.session_state.feedback,
                    "messages": st.session_state.messages
                }
                
                feedback_json = json.dumps(session_feedback_data, indent=2)
                st.download_button(
                    "📥 Download Session Feedback JSON",
                    data=feedback_json,
                    file_name=f"session_feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
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
                export_drug_table(get_db(), "outputs/biopharma_drugs.csv")
                st.success("✅ Drug table exported to outputs/biopharma_drugs.csv!")
            except Exception as e:
                st.error(f"Export error: {e}")
    
    with col2:
        if st.button("📋 Export Basic Data (same as Drug Table)"):
            try:
                export_drug_table(get_db(), "outputs/biopharma_drugs.csv")
                st.success("✅ Basic export replaced by outputs/biopharma_drugs.csv!")
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
        if st.button("Export standardized CSV (biopharma_drugs.csv)"):
            try:
                db = get_db()
                out_path = export_drug_table(db, "outputs/biopharma_drugs.csv")
                with open(out_path, "rb") as f:
                    st.download_button("Download CSV", f, file_name="biopharma_drugs.csv", mime="text/csv")
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
    """Show evaluation page with Agentic RAG self-evaluation metrics."""
    st.header("🤖 Agentic RAG Self-Evaluation")
    
    st.markdown("""
    Evaluate the performance of your Agentic RAG system using its own built-in metrics.
    This evaluation analyzes tool usage, data source attribution, and response quality.
    """)
    
    # Evaluation settings
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("🤖 Using Agentic RAG Self-Evaluation")
    
    with col2:
        num_questions = st.slider("Number of Evaluation Questions", 1, 3, 3)
        evaluation_type = st.selectbox("Evaluation Type", ["Predefined Questions", "Custom Questions"])
    
    # Predefined evaluation questions (official set - 3 examples)
    predefined_questions = [
        "Which companies are active in KRAS inhibitor?",
        "Who is working on BCL6?",
        "Can you pull who does MTAP?",
    ]
    
    # Get test questions
    if evaluation_type == "Predefined Questions":
        test_questions = predefined_questions[:num_questions]
        st.subheader("🧪 Evaluation Questions")
        for i, q in enumerate(test_questions, 1):
            st.write(f"{i}. {q}")
        # Reference vs Our Answers (preview)
        with st.expander("Show reference (correct) answers and preview our answers"):
            st.markdown("**Reference (correct) answers**")
            refs = {
                "Which companies are active in KRAS inhibitor?": "Roche: Divarasib (GDC‑6036 / RG6330, KRAS G12C); RG6620 (GDC‑7035, KRAS G12D). Amgen: LUMAKRAS (sotorasib, KRAS G12C) – approved in KRAS G12C‑mutated NSCLC; trials include NSCLC and advanced CRC. Merck: MK‑1084 (KRAS G12C). Eli Lilly: Olomorasib (KRAS G12C); KRAS G12D program; LY4066434 (pan‑KRAS).",
                "Who is working on BCL6?": "Arvinas: ARV‑393 (oral BCL6 PROTAC degrader, Phase 1, advanced NHL). Bristol Myers Squibb: BMS‑986458 (BCL6 degrader, Phase 1, NHL). Treeline Biosciences: TLN‑121 (BCL6 degrader, Phase 1, relapsed/refractory NHL).",
                "Can you pull who does MTAP?": "Bayer: BAY 3713372 – Phase 1/2 mono & combo in advanced NSCLC, GI, biliary tract, pancreatic, and other solid tumors. Amgen: AMG 193 – Phase 1 mono & combo in MTAP‑deleted solid tumors incl. PDAC, GI, biliary. BMS: MRTX1719 / BMS‑986504 – Phase 1–3 mono & combo across MTAP‑deleted tumors; BMS‑986504 in 1L metastatic NSCLC. AstraZeneca: AZD3470 – Phase 1 in MTAP‑deficient tumors. Gilead: GS‑5319 – Phase 1 in MTAP‑deleted tumors."
            }
            for i, q in enumerate(test_questions, 1):
                st.write(f"{i}. {q}")
                st.caption(refs.get(q, "Provide specific, sourced details."))
            st.markdown("**Our answers (preview)**")
            if st.button("Generate preview answers", key="gen_preview_answers"):
                if "react_agent" not in st.session_state:
                    st.session_state.react_agent = ReactRAGAgent(settings)
                previews = []
                for q in test_questions:
                    try:
                        resp = st.session_state.react_agent.generate_response(q)
                        previews.append((q, resp.get("answer", str(resp))[:1200]))
                    except Exception as e:
                        previews.append((q, f"Error: {e}"))
                for i, (q, ans) in enumerate(previews, 1):
                    st.write(f"{i}. {q}")
                    st.code(ans)
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
        
        # Build React agent for evaluation
        try:
            # Use React Framework agent for evaluation
            react_agent = ReactRAGAgent(settings)
            
            # Show progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Run evaluation
            with st.spinner("Running React agent self-evaluation..."):
                status_text.text("Initializing evaluation...")
                progress_bar.progress(0.1)
                
                db = get_db()
                
                status_text.text("Evaluating React agent...")
                progress_bar.progress(0.3)
                
                # Run evaluation using React agent self-evaluation
                try:
                    scores = evaluate_react_agent(
                        agent=react_agent,
                        db=db,
                        test_questions=test_questions
                    )
                except Exception as e:
                    st.error(f"❌ Evaluation failed: {e}")
                    import traceback
                    st.error(traceback.format_exc())
                    return
                
                progress_bar.progress(1.0)
                status_text.text("Evaluation complete!")
                
                db.close()
            
            # Display results
            st.subheader("📈 Agentic RAG Evaluation Results")
            
            # Check if evaluation was successful
            if 'evaluation_scores' not in scores and 'ragas_compatible_scores' not in scores:
                st.error("❌ Evaluation failed. The Agentic RAG evaluation system encountered an error.")
                st.write("**Debug Info:**")
                st.json(scores)
                return
            
            # Use the available scores (prefer evaluation_scores, fallback to ragas_compatible_scores)
            display_scores = scores.get('evaluation_scores', scores.get('ragas_compatible_scores', {}))
            
            if not display_scores:
                st.error("❌ No evaluation scores available.")
                return
            
            # Display React agent evaluation scores
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Data Source Attribution", 
                    f"{display_scores['faithfulness']:.3f}",
                    help="Measures confidence in data source attribution and honesty"
                )
            
            with col2:
                st.metric(
                    "Semantic Relevance", 
                    f"{display_scores['answer_relevancy']:.3f}",
                    help="Measures relevance scores from semantic search"
                )
            
            with col3:
                st.metric(
                    "Cross-Source Consistency", 
                    f"{scores['evaluation_scores']['context_precision']:.3f}",
                    help="Measures consistency across data sources"
                )
            
            with col4:
                st.metric(
                    "Success Rate", 
                    f"{scores['evaluation_scores']['context_recall']:.3f}",
                    help="Measures success rate of question answering"
                )
            
            # Agentic RAG specific metrics
            st.subheader("🤖 Agentic RAG Metrics")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Average Relevance", f"{scores['overall_metrics']['average_relevance']:.3f}")
                st.metric("Average Confidence", f"{scores['overall_metrics']['average_confidence']:.3f}")
            
            with col2:
                st.metric("Average Consistency", f"{scores['overall_metrics']['average_consistency']:.3f}")
                st.metric("Success Rate", f"{scores['overall_metrics']['success_rate']:.3f}")
            
            with col3:
                st.metric("Questions Evaluated", scores['questions_evaluated'])
                st.metric("Tools Used", len(scores['tool_usage_stats']))
            
            # Tool usage breakdown
            if scores['tool_usage_stats']:
                st.subheader("🛠️ Tool Usage Statistics")
                tool_df = pd.DataFrame(list(scores['tool_usage_stats'].items()), columns=['Tool', 'Usage Count'])
                st.dataframe(tool_df, use_container_width=True)
            
            # Data source breakdown
            if scores['data_source_stats']:
                st.subheader("📊 Data Source Statistics")
                source_df = pd.DataFrame(list(scores['data_source_stats'].items()), columns=['Data Source', 'Usage Count'])
                st.dataframe(source_df, use_container_width=True)
            
            # Overall score
            overall_score = sum(scores['evaluation_scores'].values()) / len(scores['evaluation_scores'])
            st.metric("Overall Agentic RAG Score", f"{overall_score:.3f}")
            
            # Interpretation
            st.subheader("📝 Interpretation")
            
            if overall_score >= 0.8:
                st.success("🎉 Excellent performance! Your React agent is working very well.")
            elif overall_score >= 0.6:
                st.info("✅ Good performance. Consider fine-tuning tools for better results.")
            elif overall_score >= 0.4:
                st.warning("⚠️ Moderate performance. There's room for improvement in tool usage.")
            else:
                st.error("❌ Poor performance. The React agent needs significant improvements.")
            
            # Detailed breakdown
            with st.expander("📊 Detailed Metrics"):
                st.write("**Data Source Attribution (0-1):** How well the agent indicates data sources")
                st.write("**Semantic Relevance (0-1):** Relevance scores from semantic search")
                st.write("**Cross-Source Consistency (0-1):** Consistency across data sources")
                st.write("**Success Rate (0-1):** Percentage of questions answered successfully")
                
                # Show raw scores
                st.write("\n**Raw Scores:**")
                for metric, score in scores.items():
                    if isinstance(score, (int, float)):
                        st.write(f"- {metric}: {score:.4f}")
                    else:
                        st.write(f"- {metric}: {score}")
            
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
    st.subheader("ℹ️ About Agentic RAG Self-Evaluation")
    st.markdown("""
    **Agentic RAG Self-Evaluation** uses the agent's own built-in metrics to assess performance:
    
    - **Faithfulness**: Measures confidence in data source attribution and honesty
    - **Answer Relevancy**: Measures relevance scores from semantic search results
    - **Context Precision**: Measures consistency across multiple data sources  
    - **Context Recall**: Measures success rate of question answering
    
    **Additional Agentic RAG Metrics:**
    - Tool usage statistics and effectiveness
    - Data source attribution tracking
    - Cross-validation confidence scores
    - Answer quality analysis
    
    **Benefits over External Evaluation:**
    - Uses agent's own relevance and confidence scores
    - Tracks tool usage and data source attribution
    - Provides detailed analytics specific to our React framework
    - No external dependencies or complex setup required
    """)


def show_ground_truth():
    """Show Ground Truth data page."""
    st.header("🏆 Ground Truth Data")
    st.markdown("Curated, validated business data with context and priority scoring.")
    
    try:
        # Load ground truth data from Excel file
        gt_loader = GroundTruthLoader()
        
        if gt_loader._data.empty:
            st.error("No Ground Truth data available. Please check the Excel file.")
            return
        
        # Display data overview
        st.subheader("📊 Data Overview")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Records", len(gt_loader._data))
        
        with col2:
            unique_companies = gt_loader._data['Company'].nunique() if 'Company' in gt_loader._data.columns else 0
            st.metric("Unique Companies", unique_companies)
        
        with col3:
            unique_drugs = gt_loader._data['Generic name'].nunique() if 'Generic name' in gt_loader._data.columns else 0
            st.metric("Unique Drugs", unique_drugs)
        
        with col4:
            unique_targets = gt_loader._data['Target'].nunique() if 'Target' in gt_loader._data.columns else 0
            st.metric("Unique Targets", unique_targets)
        
        # Data table with filters
        st.subheader("📋 Ground Truth Data")
        
        # Create 6 filter columns
        filter_col1, filter_col2, filter_col3, filter_col4, filter_col5, filter_col6 = st.columns(6)
        
        with filter_col1:
            company_options = ["All"] + sorted([str(x) for x in gt_loader._data['Company'].unique() if pd.notna(x)])
            company_filter = st.selectbox("Company", company_options, key="company_filter")
        
        with filter_col2:
            drug_options = ["All"] + sorted([str(x) for x in gt_loader._data['Generic name'].unique() if pd.notna(x)])
            drug_name_filter = st.selectbox("Drug Name", drug_options, key="drug_name_filter")
        
        with filter_col3:
            indication_options = ["All"] + sorted([str(x) for x in gt_loader._data['Indication Approved'].unique() if pd.notna(x)])
            indication_filter = st.selectbox("Indication", indication_options, key="indication_filter")
        
        with filter_col4:
            target_options = ["All"] + sorted([str(x) for x in gt_loader._data['Target'].unique() if pd.notna(x)])
            target_filter = st.selectbox("Target", target_options, key="target_filter")
        
        with filter_col5:
            mechanism_options = ["All"] + sorted([str(x) for x in gt_loader._data['Mechanism'].unique() if pd.notna(x)])
            mechanism_filter = st.selectbox("Mechanism", mechanism_options, key="mechanism_filter")
        
        with filter_col6:
            drug_class_options = ["All"] + sorted([str(x) for x in gt_loader._data['Drug Class'].unique() if pd.notna(x)])
            drug_class_filter = st.selectbox("Drug Class", drug_class_options, key="drug_class_filter")
        
        # Apply filters to the ground truth data
        filtered_data = gt_loader._data.copy()
        
        if company_filter != "All":
            filtered_data = filtered_data[filtered_data['Company'] == company_filter]
        
        if drug_name_filter != "All":
            filtered_data = filtered_data[filtered_data['Generic name'] == drug_name_filter]
        
        if indication_filter != "All":
            filtered_data = filtered_data[filtered_data['Indication Approved'] == indication_filter]
        
        if target_filter != "All":
            filtered_data = filtered_data[filtered_data['Target'] == target_filter]
        
        if mechanism_filter != "All":
            filtered_data = filtered_data[filtered_data['Mechanism'] == mechanism_filter]
        
        if drug_class_filter != "All":
            filtered_data = filtered_data[filtered_data['Drug Class'] == drug_class_filter]
        
        # Display the filtered table (excluding Tickets column)
        display_data = filtered_data.drop(columns=['Tickets'], errors='ignore')
        st.dataframe(
            display_data,
            use_container_width=True,
            height=600
        )
        
        # Show summary
        st.write(f"Showing {len(filtered_data)} of {len(gt_loader._data)} total records")
        
        # Export functionality
        st.subheader("📤 Export Options")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Export Filtered Data to CSV"):
                csv = filtered_data.to_csv(index=False)
                st.download_button(
                    label="Download Filtered Ground Truth CSV",
                    data=csv,
                    file_name="ground_truth_filtered.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("Export All Data to CSV"):
                csv = gt_loader._data.to_csv(index=False)
                st.download_button(
                    label="Download All Ground Truth CSV",
                    data=csv,
                    file_name="ground_truth_all.csv",
                    mime="text/csv"
                )
    
    except Exception as e:
        st.error(f"Error loading Ground Truth data: {e}")
        logger.error(f"Ground Truth dashboard error: {e}")


if __name__ == "__main__":
    main()
