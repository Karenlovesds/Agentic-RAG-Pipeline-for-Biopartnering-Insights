❌ Test failed: `BaseSettings` has been moved to the `pydantic-settings` package. See https://docs.pydantic.dev/2.11/migration/#basesettings-has-moved-to-pydantic-settings for more details."""Streamlit UI for Biopartnering Insights Pipeline."""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.models.database import get_db
from src.models.entities import Document, Company, Drug, ClinicalTrial
from src.data_collection.orchestrator import DataCollectionOrchestrator
from config import settings, get_target_companies
from src.rag.provider import build_provider
from src.rag.agent import RAGAgent
from src.processing.csv_export import export_basic, export_drug_table
from src.processing.pipeline import run_processing
from src.evaluation.ragas_eval import run_ragas


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


def get_database_stats():
    """Get database statistics."""
    try:
        db = next(get_db())
        
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


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🧬 Biopartnering Insights Pipeline</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.selectbox(
            "Select Page",
            ["Dashboard", "Data Collection", "Knowledge Base", "RAG Agent", "Settings"]
        )
        
        st.header("Database Status")
        stats = get_database_stats()
        st.header("Model Provider")
        provider = st.selectbox("Provider", ["openai", "ollama"], index=0 if settings.openai_api_key else 1)
        chat_model = st.text_input("Chat model", value="gpt-4o-mini" if provider == "openai" else "llama3.1")
        embed_model = st.text_input("Embedding model", value="text-embedding-3-small" if provider == "openai" else "nomic-embed-text")
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
    elif page == "Knowledge Base":
        show_knowledge_base()
    elif page == "RAG Agent":
        show_rag_agent()
    elif page == "Settings":
        show_settings()


def show_dashboard():
    """Show dashboard page."""
    st.header("📊 Dashboard")
    
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
    
    # Recent activity
    st.header("Recent Activity")
    
    try:
        db = next(get_db())
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
    - **Drugs.com**: Drug profiles and information
    - **FDA**: Regulatory approvals and safety information
    """)
    
    # Collection controls
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Collection Sources")
        clinical_trials = st.checkbox("Clinical Trials", value=True)
        drugs = st.checkbox("Drugs.com", value=True)
        fda = st.checkbox("FDA", value=True)
    
    with col2:
        st.subheader("Actions")
        if st.button("🚀 Start Collection", type="primary"):
            run_data_collection_ui([clinical_trials, drugs, fda])
        if st.button("⚙️ Process Documents"):
            try:
                db = next(get_db())
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


def show_knowledge_base():
    """Show knowledge base page."""
    st.header("📚 Knowledge Base")
    
    st.markdown("""
    Browse and search the collected biomedical data.
    """)
    
    # Search and filters
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input("Search the knowledge base", placeholder="Enter search terms...")
    
    with col2:
        source_filter = st.selectbox("Filter by source", ["All", "clinical_trials", "drugs_com", "fda"])
    
    # Display results
    if search_query or source_filter != "All":
        try:
            db = next(get_db())
            
            query = db.query(Document)
            
            if source_filter != "All":
                query = query.filter(Document.source_type == source_filter)
            
            if search_query:
                query = query.filter(Document.content.contains(search_query))
            
            results = query.limit(50).all()
            
            if results:
                st.write(f"Found {len(results)} documents:")
                
                for doc in results:
                    with st.expander(f"{doc.title or 'Untitled'} - {doc.source_type}"):
                        st.write(f"**URL**: {doc.source_url}")
                        st.write(f"**Retrieved**: {doc.retrieval_date}")
                        st.write("**Content Preview**:")
                        st.text(doc.content[:500] + "..." if len(doc.content) > 500 else doc.content)
            else:
                st.info("No documents found matching your criteria.")
            
            db.close()
            
        except Exception as e:
            st.error(f"Error searching knowledge base: {e}")
    else:
        st.info("Enter a search query or select a source filter to browse the knowledge base.")

    st.subheader("Evaluation (RAGAS)")
    st.caption("Provide a question and ground-truth answer to compute quick RAGAS metrics using current contexts")
    q = st.text_input("Question for evaluation", key="eval_q")
    a = st.text_area("Expected answer (short)", key="eval_a")
    if st.button("Run evaluation"):
        try:
            db = next(get_db())
            # Build contexts using simple retrieval
            from src.rag.agent import _simple_retrieve
            ctx = [r.content for r in _simple_retrieve(db, q, limit=5)] if q else []
            dataset = [{"question": q, "answer": a, "contexts": ctx}]
            scores = run_ragas(dataset)
            st.write(scores)
        except Exception as e:
            st.error(f"Evaluation failed: {e}")


def show_rag_agent():
    """Show RAG agent page."""
    st.header("🤖 RAG Agent")
    
    st.markdown("""
    Ask questions about biopartnering opportunities, drug approvals, and clinical trials.
    The AI agent will provide answers with citations and confidence scores.
    """)
    
    # Provider selection from sidebar (stored in session for reuse)
    provider = st.session_state.get("provider_selection")
    # Fallback: read from sidebar widgets directly if available
    # For simplicity here, rebuild with defaults each call
    prov_name = st.sidebar.session_state.get('Provider', 'openai') if 'Provider' in st.sidebar.session_state else ('openai' if settings.openai_api_key else 'ollama')
    chat_model = st.sidebar.session_state.get('Chat model', 'gpt-4o-mini' if prov_name=='openai' else 'llama3.1')
    embed_model = st.sidebar.session_state.get('Embedding model', 'text-embedding-3-small' if prov_name=='openai' else 'nomic-embed-text')
    provider = build_provider(prov_name, chat_model, embed_model, settings.openai_api_key)

    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about biopartnering opportunities..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response using minimal RAG
        with st.chat_message("assistant"):
            try:
                db = next(get_db())
                agent = RAGAgent(provider)
                result = agent.answer(db, prompt, k=5)
                answer = result["answer"]
                st.markdown(answer)
                # Show citations
                if result.get("citations"):
                    with st.expander("Citations"):
                        for c in result["citations"]:
                            st.write(f"[{c['label']}] {c['title']} - {c['url']}")
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"RAG error: {e}")


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
                db = next(get_db())
                out_path = export_basic(db, "outputs/biopartnering_data.csv")
                with open(out_path, "rb") as f:
                    st.download_button("Download CSV", f, file_name="biopartnering_data.csv", mime="text/csv")
            except Exception as e:
                st.error(f"Export failed: {e}")
        if st.button("Export drug table (requested schema)"):
            try:
                db = next(get_db())
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


if __name__ == "__main__":
    main()
