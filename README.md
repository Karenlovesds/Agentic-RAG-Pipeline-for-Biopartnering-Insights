# 🧬 Agentic RAG Pipeline for Biopartnering Insights

An intelligent pipeline that automatically generates potential ideas for biopartnering and provides professional, reference-backed insights on biomarkers and drugs. This system combines automated data collection, structured knowledge curation, and AI-powered querying into one streamlined workflow.

## 🎯 Overview

This pipeline automatically collects, processes, and analyzes biomedical data from trusted sources to provide actionable biopartnering insights. It's designed to help researchers, BD teams, and leadership make faster, more confident decisions with full transparency and auditability.

## ✨ Key Features

- **Automated Data Collection**: Crawls ClinicalTrials.gov, Drugs.com, and FDA sources
- **Structured Knowledge Base**: Normalized entities with proper relationships and versioning
- **AI-Powered RAG Agent**: Contextual answers with citations and confidence scores
- **Interactive UI**: Streamlit-based interface for querying and analysis
- **Standardized Outputs**: CSV exports for pipeline reviews and BD targeting
- **Evaluation Framework**: RAGAS metrics and manual validation for reliability

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Knowledge Base  │    │   RAG Agent     │
│                 │    │                  │    │                 │
│ • ClinicalTrials│───▶│ • Companies      │───▶│ • Pydantic AI   │
│ • Drugs.com     │    │ • Drugs          │    │ • Citations     │
│ • FDA           │    │ • Targets        │    │ • Confidence    │
└─────────────────┘    │ • Indications    │    └─────────────────┘
                       │ • Clinical Trials│
                       └──────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Streamlit UI  │
                       │                 │
                       │ • Chat Interface│
                       │ • Filters       │
                       │ • Evidence Pane │
                       └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/Agentic-RAG-Pipeline-for-Biopartnering-Insights.git
   cd Agentic-RAG-Pipeline-for-Biopartnering-Insights
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. **Initialize the database**
   ```bash
   python main.py
   ```

5. **Launch the Streamlit UI**
   ```bash
   streamlit run streamlit_app.py
   ```

## 📊 Data Collection

The pipeline collects data from three primary sources:

### ClinicalTrials.gov
- **Focus**: Ongoing, completed, and planned clinical trials
- **Scope**: Top 30 pharma/biotech companies
- **Data**: Trial phases, status, endpoints, study populations

### Drugs.com
- **Focus**: Drug profiles and mechanisms of action
- **Scope**: Cancer drugs and targeted therapies
- **Data**: Generic/brand names, drug classes, indications, safety

### FDA
- **Focus**: Regulatory approvals and safety communications
- **Scope**: Official labeling and approval information
- **Data**: Approval status, dates, indications, safety alerts

## 🗄️ Knowledge Base Structure

The system maintains a structured database with the following entities:

- **Companies**: Pharma/biotech companies with metadata
- **Drugs**: Normalized drug information with standardized IDs
- **Targets**: Proteins, genes, and pathways with HGNC symbols
- **Indications**: Disease conditions with NCIT cancer terms
- **Clinical Trials**: Trial information with relationships
- **Documents**: Source documents with provenance tracking

## 🤖 RAG Agent Capabilities

The AI agent can handle queries such as:

- "Which companies should I pitch for TROP2?"
- "Is VEOZAH FDA approved?"
- "What are the potential needs for metastatic prostate cancer?"
- "Show me all Phase 3 trials for HER2+ breast cancer"

Each response includes:
- **Answer**: Contextual, synthesized response
- **Citations**: Source documents and URLs
- **Confidence Score**: 0-1 confidence rating
- **Evidence**: Relevant passages and metadata

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

The Streamlit interface provides:

- **Dashboard**: Overview metrics and recent activity
- **Data Collection**: Manual trigger and monitoring
- **Knowledge Base**: Search and browse collected data
- **RAG Agent**: Chat interface for AI queries
- **Settings**: Configuration and company tracking

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
│   ├── processing/       # Data processing pipeline
│   ├── rag/             # RAG agent implementation
│   └── evaluation/      # Evaluation framework
├── data/                # Raw collected data
├── outputs/             # Generated CSV files
├── logs/                # Application logs
├── main.py              # Main application entry point
├── streamlit_app.py     # Streamlit UI
├── config.py            # Configuration settings
└── requirements.txt     # Python dependencies
```

## 🚀 Usage Examples

### Data Collection
```python
from src.data_collection.orchestrator import DataCollectionOrchestrator

orchestrator = DataCollectionOrchestrator()
results = await orchestrator.run_full_collection()
```

### RAG Queries
```python
from src.rag.agent import BiopartneringAgent

agent = BiopartneringAgent()
response = await agent.query("Which companies are developing TROP2 inhibitors?")
```

### CSV Export
```python
from src.processing.csv_generator import CSVGenerator

generator = CSVGenerator()
generator.export_standardized_data("outputs/biopartnering_data.csv")
```

## 🔄 Data Refresh

The system supports multiple refresh schedules:

- **Weekly**: Automatic refresh every Sunday
- **Daily**: Daily incremental updates
- **Manual**: On-demand collection via UI

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
- OpenAI for AI capabilities
- The biomedical research community

## 📞 Support

For questions, issues, or contributions, please:

1. Check the [Issues](https://github.com/your-username/Agentic-RAG-Pipeline-for-Biopartnering-Insights/issues) page
2. Create a new issue with detailed information
3. Contact the development team

---

**Built with ❤️ for the biomedical research community**
A Pipeline + Agentic RAG system that automatically generates potential ideas for biopartnering and provides professional, reference-backed insights on biomarkers and drugs. This system will combine automated data collection, structured knowledge curation, and AI-powered querying into one streamlined workflow.
