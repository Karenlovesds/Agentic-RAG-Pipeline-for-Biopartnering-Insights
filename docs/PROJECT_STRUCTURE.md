
File "/Users/mingyuezheng/Agentic-RAG-Pipeline-for-Biopartnering-Insights/scripts/main/streamlit_app.py", line 26, in <module>
    from src.evaluation.ragas_eval import run_ragas, evaluate_rag_agent
File "/Users/mingyuezheng/Agentic-RAG-Pipeline-for-Biopartnering-Insights/src/evaluation/ragas_eval.py", line 11, in <module>
    from langchain_ollama import ChatOllama
oure# Project Structure

This document describes the organized structure of the Biopartnering Insights Pipeline project.

## 📁 Directory Structure

```
Agentic-RAG-Pipeline-for-Biopartnering-Insights/
├── 📄 run_pipeline.py                    # Main entry point script
├── 📄 requirements.txt                   # Python dependencies
├── 📄 .env                              # Environment variables
├── 📄 biopartnering_insights.db         # SQLite database
├── 📄 pipeline_state.json               # Pipeline state tracking
│
├── 📁 config/                           # Configuration files



Evaluation features are not available in this environment.
o
│   └── setup.py                         # Package setup
│
├── 📁 data/                             # Data files
│   ├── companies.csv                    # Company data
│   ├── biopharma_pipeline_output_example.csv
│   └── merck_ground_truth_corrected.csv
│
├── 📁 docs/                             # Documentation
│   ├── README.md                        # Main documentation
│   ├── PROJECT_STRUCTURE.md             # This file
│   └── PRD_Agentic_RAG_Pipeline_Biopartnering_Insights.md
│
├── 📁 monitoring/                       # Monitoring and logs
│   ├── logs/                            # Log files
│   ├── pipeline_state.json              # Pipeline state
│   └── metrics/                         # Performance metrics
│
├── 📁 outputs/                          # Generated outputs
│   ├── biopharma_drugs.csv              # Main drug database
│   ├── basic_export.csv                 # Basic data export
│   ├── drug_collection_summary.txt      # Collection summary
│   └── pipeline_drugs.txt               # Pipeline drugs
│
├── 📁 scripts/                          # Executable scripts
│   ├── 📁 main/                         # Main pipeline scripts
│   │   ├── __init__.py
│   │   ├── main.py                      # Original main script
│   │   ├── run_complete_pipeline.py     # Complete pipeline with change detection
│   │   ├── run_scheduled_pipeline.py    # Scheduled pipeline runner
│   │   ├── run_production.py            # Production runner
│   │   └── streamlit_app.py             # Web interface
│   │
│   ├── 📁 data_collection/              # Data collection scripts
│   │   ├── __init__.py
│   │   ├── extract_fda_indications.py
│   │   ├── populate_clinical_trials.py
│   │   ├── run_comprehensive_extraction.py
│   │   ├── run_entity_extraction.py
│   │   └── run_simple_extraction.py
│   │
│   ├── 📁 deployment/                   # Deployment scripts
│   │   ├── __init__.py
│   │   ├── biopartnering-pipeline.service
│   │   ├── biopartnering-pipeline-scheduled.service
│   │   ├── deploy.sh
│   │   └── run_pipeline_cron.sh
│   │
│   └── 📁 maintenance/                  # Maintenance scripts
│       ├── __init__.py
│       └── setup_environment.sh
│
├── 📁 src/                              # Source code
│   ├── __init__.py
│   ├── 📁 data_collection/              # Data collection modules
│   │   ├── __init__.py
│   │   ├── base_collector.py
│   │   ├── clinical_trials_collector.py
│   │   ├── company_website_collector.py
│   │   ├── drug_extractor.py
│   │   ├── drugs_collector.py
│   │   ├── fda_collector.py
│   │   └── orchestrator.py
│   │
│   ├── 📁 evaluation/                   # Evaluation modules
│   │   └── ragas_eval.py
│   │
│   ├── 📁 models/                       # Data models
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── entities.py
│   │
│   ├── 📁 monitoring/                   # Monitoring modules
│   │   ├── change_detector.py
│   │   ├── notifications.py
│   │   └── scheduler.py
│   │
│   ├── 📁 processing/                   # Data processing modules
│   │   ├── csv_export.py
│   │   └── pipeline.py
│   │
│   └── 📁 rag/                          # RAG system modules
│       ├── agent.py
│       ├── cache_manager.py
│       └── provider.py
│
└── 📁 tests/                            # Test files
    ├── 📁 unit/                         # Unit tests
    ├── 📁 integration/                  # Integration tests
    └── 📁 e2e/                          # End-to-end tests
```

## 🚀 Quick Start

### Main Entry Point
```bash
# Show help
python run_pipeline.py --help

# Run complete pipeline
python run_pipeline.py run

# Run with force refresh
python run_pipeline.py run --force

# Start web interface
python run_pipeline.py web

# Run scheduled pipeline
python run_pipeline.py schedule
```

### Individual Components
```bash
# Data collection only
python run_pipeline.py data-collect

# Processing only
python run_pipeline.py process

# Export only
python run_pipeline.py export
```

## 📋 Script Categories

### Main Scripts (`scripts/main/`)
- **`run_complete_pipeline.py`**: Complete pipeline with intelligent change detection
- **`run_scheduled_pipeline.py`**: Scheduled pipeline runner for production
- **`streamlit_app.py`**: Web interface for data exploration
- **`main.py`**: Original main pipeline script

### Data Collection Scripts (`scripts/data_collection/`)
- **`extract_fda_indications.py`**: Extract FDA drug indications
- **`populate_clinical_trials.py`**: Populate clinical trials data
- **`run_comprehensive_extraction.py`**: Comprehensive entity extraction
- **`run_entity_extraction.py`**: Basic entity extraction
- **`run_simple_extraction.py`**: Simple extraction workflow

### Deployment Scripts (`scripts/deployment/`)
- **`biopartnering-pipeline.service`**: Systemd service file
- **`biopartnering-pipeline-scheduled.service`**: Scheduled service file
- **`deploy.sh`**: Deployment script
- **`run_pipeline_cron.sh`**: Cron job script

### Maintenance Scripts (`scripts/maintenance/`)
- **`setup_environment.sh`**: Environment setup script

## 🔧 Configuration

### Environment Variables (`.env`)
```bash
# Database
DATABASE_URL=sqlite:///biopartnering_insights.db

# API Keys
FDA_API_KEY=your_fda_api_key
OPENAI_API_KEY=your_openai_api_key

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/pipeline.log
```

### Main Configuration (`config/config.py`)
- Database settings
- API configurations
- Logging settings
- Pipeline parameters

## 📊 Data Flow

1. **Data Collection** → Raw data from multiple sources
2. **Processing** → Entity extraction and linking
3. **Storage** → SQLite database
4. **Export** → CSV files for analysis
5. **Web Interface** → Interactive exploration

## 🚀 Deployment

### Development
```bash
python run_pipeline.py run
```

### Production (Systemd)
```bash
sudo systemctl enable biopartnering-pipeline-scheduled
sudo systemctl start biopartnering-pipeline-scheduled
```

### Production (Cron)
```bash
# Add to crontab
0 */6 * * * /path/to/scripts/deployment/run_pipeline_cron.sh
```

## 📈 Monitoring

- **Pipeline State**: `monitoring/pipeline_state.json`
- **Logs**: `monitoring/logs/`
- **Metrics**: `monitoring/metrics/`
- **Database**: `biopartnering_insights.db`

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/e2e/
```

## 📝 Documentation

- **README.md**: Main project documentation
- **PROJECT_STRUCTURE.md**: This file
- **PRD_Agentic_RAG_Pipeline_Biopartnering_Insights.md**: Product requirements
- **API Documentation**: `docs/api/`
- **User Guide**: `docs/user_guide/`
