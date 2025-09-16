# 🧬 Agentic RAG Pipeline for Biopartnering Insights

An intelligent, production-ready pipeline that automatically generates potential ideas for biopartnering and provides professional, reference-backed insights on biomarkers and drugs. This system combines automated data collection, structured knowledge curation, AI-powered querying, and intelligent monitoring into one streamlined workflow.

## 🎯 Overview

This pipeline automatically collects, processes, and analyzes biomedical data from trusted sources to provide actionable biopartnering insights. It's designed to help researchers, BD teams, and leadership make faster, more confident decisions with full transparency and auditability. The system is production-ready with automated monitoring, change detection, and scheduled updates.

## ✨ Key Features

- **🤖 Intelligent Drug Extraction**: Automatically extracts drug names and indications from company pipeline pages
- **🔄 Automated Data Collection**: Crawls ClinicalTrials.gov, Drugs.com, FDA, and company websites
- **📊 Structured Knowledge Base**: Normalized entities with proper relationships and versioning
- **🧠 AI-Powered RAG Agent**: Dual-provider support (OpenAI/Ollama) with contextual answers and citations
- **🎨 Interactive UI**: Streamlit-based interface with real-time monitoring and analytics
- **📈 Standardized Outputs**: CSV exports for pipeline reviews and BD targeting
- **🔍 Evaluation Framework**: RAGAS metrics and manual validation for reliability
- **⚡ Production Monitoring**: Website change detection and automated pipeline updates
- **📧 Smart Notifications**: Email alerts for changes and scheduled runs
- **🚀 Production Deployment**: Systemd service, cron jobs, and comprehensive logging
- **💾 Intelligent Caching**: RAG response caching for improved performance

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Knowledge Base  │    │   RAG Agent     │
│                 │    │                  │    │                 │
│ • ClinicalTrials│───▶│ • Companies      │───▶│ • Pydantic AI   │
│ • Drugs.com     │    │ • Drugs          │    │ • Dual Provider │
│ • FDA           │    │ • Targets        │    │ • Citations     │
│ • Company Sites │    │ • Indications    │    │ • Confidence    │
│ • Drug Extractor│    │ • Clinical Trials│    │ • Caching       │
└─────────────────┘    │ • RAG Cache      │    └─────────────────┘
                       └──────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Streamlit UI  │
                       │                 │
                       │ • Chat Interface│
                       │ • Filters       │
                       │ • Evidence Pane │
                       │ • Monitoring    │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Production    │
                       │   Monitoring    │
                       │                 │
                       │ • Change Detect │
                       │ • Scheduler     │
                       │ • Notifications │
                       │ • Logging       │
                       └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (or Ollama for local models)
- Git
- Conda (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/Agentic-RAG-Pipeline-for-Biopartnering-Insights.git
   cd Agentic-RAG-Pipeline-for-Biopartnering-Insights
   ```

2. **Create conda environment**
   ```bash
   conda create -n pipe_env python=3.11 -y
   conda activate pipe_env
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys and settings
   ```

5. **Initialize the database**
   ```bash
   python -c "from src.models.database import Base, engine; Base.metadata.create_all(engine)"
   ```

6. **Launch the Streamlit UI**
   ```bash
   streamlit run streamlit_app.py
   ```

### Production Deployment

For production deployment, use the automated deployment script:

```bash
# Make deployment script executable
chmod +x deploy/deploy.sh

# Run deployment (requires sudo for systemd service)
./deploy/deploy.sh

# Manage the service
./monitor.sh start    # Start the service
./monitor.sh status   # Check status
./monitor.sh logs     # View logs
./monitor.sh stop     # Stop the service
```

## 📊 Data Collection

The pipeline collects data from multiple sources with intelligent drug extraction:

### ClinicalTrials.gov
- **Focus**: Ongoing, completed, and planned clinical trials
- **Scope**: Top 30 oncology-focused pharma/biotech companies
- **Data**: Trial phases, status, endpoints, study populations
- **Enhancement**: Oncology-focused queries and phase filtering

### Drugs.com
- **Focus**: Comprehensive drug profiles and FDA approval history
- **Scope**: Cancer drugs and targeted therapies
- **Data**: Generic/brand names, drug classes, indications, safety, interactions
- **Enhancement**: FDA approval history, clinical trials, drug interactions

### FDA
- **Focus**: Comprehensive regulatory approvals and safety communications
- **Scope**: Official labeling and approval information
- **Data**: Approval status, dates, indications, safety alerts, regulatory actions
- **Enhancement**: Comprehensive drug approval data, adverse events, regulatory actions

### Company Websites
- **Focus**: Pipeline and development information
- **Scope**: Top 30 oncology-focused companies
- **Data**: Pipeline drugs, development stages, indications, mechanisms
- **Enhancement**: Specialized content extraction for pipeline, clinical trials, products

### Intelligent Drug Extraction
- **Focus**: Automatically extract drug names and indications from pipeline pages
- **Scope**: All company pipeline pages
- **Data**: Drug names, indications, mechanisms, development stages, phases
- **Enhancement**: Uses extracted drug names to pull comprehensive data from FDA and Drugs.com

## 🗄️ Knowledge Base Structure

The system maintains a structured database with the following entities:

- **Companies**: Pharma/biotech companies with metadata and website information
- **Drugs**: Normalized drug information with standardized IDs and extracted pipeline data
- **Targets**: Proteins, genes, and pathways with HGNC symbols
- **Indications**: Disease conditions with NCIT cancer terms
- **Clinical Trials**: Trial information with relationships and comprehensive data
- **Documents**: Source documents with provenance tracking and specialized content
- **RAG Cache**: Cached RAG responses for improved performance and cost efficiency

## 🤖 RAG Agent Capabilities

The AI agent supports dual providers (OpenAI and Ollama) and can handle oncology-focused queries such as:

- "What are drugs that can be combined with pembrolizumab for solid tumors?"
- "Which companies are developing PD-1 inhibitors for lung cancer?"
- "Show me all Phase 3 trials for HER2+ breast cancer"
- "What are the latest FDA approvals for immunotherapy drugs?"
- "Which companies have pipeline drugs for metastatic melanoma?"

### Provider Support
- **OpenAI**: GPT-4o-mini with text-embedding-3-small
- **Ollama**: Local models (llama3.1, nomic-embed-text)
- **Automatic Fallback**: Seamless switching between providers
- **Connection Testing**: Built-in provider connectivity tests

### Response Features
- **Answer**: Contextual, synthesized response with oncology focus
- **Citations**: Source documents and URLs with confidence scores
- **Confidence Score**: 0-1 confidence rating
- **Evidence**: Relevant passages and metadata
- **Caching**: Intelligent response caching for improved performance
- **Real-time**: Live provider selection and model switching

## 📈 Standardized Output

The pipeline generates CSV files with normalized fields:

| Field | Description |
|-------|-------------|
| Company Name | Standardized company name |
| Generic Name | Drug generic name |
| Brand Name | FDA-approved brand name |
| FDA Approval Status | Y/N approval status |
| Approval Date | FDA approval date |
| Drug Class | Therapeutic class |
| Target(s) | Molecular targets |
| Mechanism of Action | Drug mechanism |
| Indications | FDA-approved indications |
| Clinical Trials | Formatted trial information |

## 🔍 User Interface

The Streamlit interface provides comprehensive monitoring and control:

- **Dashboard**: Overview metrics, recent activity, and real-time statistics
- **Data Collection**: Manual trigger, monitoring, and multi-source collection
- **Knowledge Base**: Search, browse, and analyze collected data with RAGAS evaluation
- **RAG Agent**: Advanced chat interface with dual-provider support and caching
- **Settings**: Configuration, company tracking, and cache management

### Advanced Features
- **Real-time Monitoring**: Live database statistics and cache performance
- **Provider Selection**: Dynamic switching between OpenAI and Ollama
- **Cache Management**: View, clean, and manage RAG response cache
- **Export Capabilities**: Multiple CSV export formats for different use cases
- **Error Handling**: Comprehensive error reporting and recovery

## 📊 Evaluation & Validation

### Manual Evaluation
- Gold-standard evaluation table with 50-100 representative queries
- Covers FDA approvals, biomarker-specific trials, and company pipelines

### Automated Evaluation
- **RAGAS Metrics**: Faithfulness, context precision, citation quality
- **Freshness Checks**: Median data lag ≤14 days
- **Continuous Monitoring**: Automated accuracy tracking

## 🔧 Configuration

Key configuration options in `config.py`:

```python
# Target companies to track
target_companies = [
    "Pfizer", "Johnson & Johnson", "Roche", "Novartis", "Merck",
    # ... 25 more companies
]

# Data collection settings
max_concurrent_requests = 5
request_delay = 1.0
refresh_schedule = "weekly"
```

## 📁 Project Structure

```
├── src/
│   ├── models/           # Database models and entities
│   ├── data_collection/  # Data collection modules
│   │   ├── drug_extractor.py    # Drug extraction from pipeline pages
│   │   ├── orchestrator.py      # Data collection orchestration
│   │   └── ...                  # Individual collectors
│   ├── processing/       # Data processing pipeline
│   ├── rag/             # RAG agent implementation
│   │   ├── provider.py          # Dual provider support
│   │   ├── cache_manager.py     # RAG response caching
│   │   └── agent.py             # Main RAG agent
│   ├── monitoring/       # Production monitoring
│   │   ├── change_detector.py   # Website change detection
│   │   ├── scheduler.py         # Automated scheduling
│   │   └── notifications.py     # Email notifications
│   └── evaluation/      # Evaluation framework
├── deploy/              # Production deployment
│   ├── deploy.sh        # Automated deployment script
│   └── biopartnering-pipeline.service  # Systemd service
├── data/                # Raw collected data
│   └── companies.csv    # Target company configuration
├── outputs/             # Generated CSV files
├── logs/                # Application logs
├── run_production.py    # Production runner
├── streamlit_app.py     # Streamlit UI
├── config.py            # Configuration settings
├── requirements.txt     # Python dependencies
├── monitor.sh           # Production management script
└── .env                 # Environment variables
```

## 🚀 Usage Examples

### Data Collection
```python
from src.data_collection.orchestrator import DataCollectionOrchestrator

# Run full collection
orchestrator = DataCollectionOrchestrator()
results = await orchestrator.run_full_collection()

# Run specific sources
results = await orchestrator.run_full_collection(['clinical_trials', 'drugs'])
```

### Drug Extraction
```python
from src.data_collection.drug_extractor import DrugExtractoraesdrug
extractor = DrugExtractor()
drugs = extractor.extract_drugs_from_html(html_content, "Merck", "https://merck.com/pipeline")
extractor.save_drugs_to_csv(drugs, "extracted_drugs.csv")
```

### RAG Queries
```python
from src.rag.agent import RAGAgent
from src.rag.provider import build_provider

# Using OpenAI
provider = build_provider("openai", "gpt-4o-mini", "text-embedding-3-small", "your-api-key")
agent = RAGAgent(provider=provider)
response = await agent.answer("What are drugs that can be combined with pembrolizumab?")

# Using Ollama
provider = build_provider("ollama", "llama3.1", "nomic-embed-text")
agent = RAGAgent(provider=provider)
response = await agent.answer("Which companies are developing PD-1 inhibitors?")
```

### Production Monitoring
```python
from src.monitoring.change_detector import WebsiteChangeDetector
from src.monitoring.scheduler import create_scheduler

# Check for website changes
detector = WebsiteChangeDetector()
changes = detector.check_for_changes()
if changes:
    detector.trigger_pipeline_update(changes)

# Start production scheduler
scheduler = create_scheduler(enable_monitoring=True, enable_weekly_runs=True)
scheduler.start()
```

### CSV Export
```python
from src.processing.csv_export import export_drug_table

# Export drug table with requested schema
export_drug_table("outputs/drug_table.csv")
```

## 🔄 Data Refresh & Production Monitoring

The system supports multiple refresh schedules with intelligent monitoring:

### Automated Schedules
- **Weekly Full Run**: Every Sunday at 2 AM (all sources)
- **Weekly Light Update**: Every Wednesday at 2 AM (FDA + recent trials)
- **Change Detection**: Every 6 hours (website monitoring)
- **Manual**: On-demand collection via UI

### Production Monitoring
- **Website Change Detection**: Monitors company websites for content changes
- **Automated Updates**: Triggers pipeline updates when changes detected
- **Email Notifications**: Alerts for changes, updates, and errors
- **Comprehensive Logging**: Detailed logs with rotation and compression
- **Health Checks**: System status monitoring and error recovery

### Production Management
```bash
# Start production service
./monitor.sh start

# Check status and logs
./monitor.sh status
./monitor.sh logs

# Manual operations
./monitor.sh run-once      # Run pipeline once
./monitor.sh check-changes # Check for website changes

# Stop service
./monitor.sh stop
```

## 🧬 Intelligent Drug Extraction

The pipeline features advanced drug extraction capabilities that automatically identify and extract drug information from company pipeline pages:

### Extraction Features
- **Drug Name Recognition**: Identifies drug names using pattern matching and ML techniques
- **Indication Extraction**: Extracts cancer types and therapeutic indications
- **Development Stage Detection**: Identifies clinical phases and development status
- **Mechanism of Action**: Extracts drug mechanisms and target information
- **Confidence Scoring**: Provides confidence scores for extracted information

### Supported Drug Types
- Monoclonal antibodies (mab, zumab)
- Kinase inhibitors (nib, tinib)
- Fusion proteins (cept)
- Small molecules and other therapeutics

### Integration Benefits
- **Targeted Data Collection**: Uses extracted drug names to pull comprehensive FDA and Drugs.com data
- **Pipeline Intelligence**: Automatically discovers new drugs in company pipelines
- **Comprehensive Coverage**: Ensures no important pipeline drugs are missed
- **Real-time Updates**: Detects new drugs as they appear in pipeline pages

## 🔧 Configuration

### Environment Variables
```bash
# API Keys
OPENAI_API_KEY=your_openai_api_key
MODEL_PROVIDER=openai  # or ollama
CHAT_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
OLLAMA_HOST=http://localhost:11434

# Monitoring
NOTIFICATIONS_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
NOTIFICATION_RECIPIENTS=["your_email@gmail.com"]

# Data Collection
MAX_CONCURRENT_REQUESTS=5
REQUEST_DELAY=1.0
```

### Company Configuration
Update `data/companies.csv` to add or modify target companies:
```csv
Company,OfficialWebsite
Merck & Co.,https://www.merck.com/
Bristol Myers Squibb,https://www.bms.com/
Roche/Genentech,https://www.roche.com/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- ClinicalTrials.gov for providing clinical trial data
- Drugs.com for drug information
- FDA for regulatory data
- OpenAI and Ollama for AI capabilities
- The biomedical research community
- Oncology research organizations

## 📞 Support

For questions, issues, or contributions, please:

1. Check the [Issues](https://github.com/your-username/Agentic-RAG-Pipeline-for-Biopartnering-Insights/issues) page
2. Create a new issue with detailed information
3. Contact the development team

## 🚀 Production Deployment

For production deployment on Ubuntu/CentOS:

1. **Run the deployment script**:
   ```bash
   chmod +x deploy/deploy.sh
   ./deploy/deploy.sh
   ```

2. **Configure email notifications** (optional):
   ```bash
   # Edit .env file
   NOTIFICATIONS_ENABLED=true
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_app_password
   ```

3. **Start the service**:
   ```bash
   ./monitor.sh start
   ```

4. **Monitor the system**:
   ```bash
   ./monitor.sh status
   ./monitor.sh logs
   ```

---

**Built with ❤️ for the biomedical research community**

A production-ready Pipeline + Agentic RAG system that automatically generates potential ideas for biopartnering and provides professional, reference-backed insights on biomarkers and drugs. This system combines automated data collection, intelligent drug extraction, structured knowledge curation, AI-powered querying, and production monitoring into one streamlined workflow.
