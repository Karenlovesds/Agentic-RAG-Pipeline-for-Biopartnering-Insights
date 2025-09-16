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
- **🔄 Change Detection**: Intelligent skipping of unchanged data for efficiency

## 🗂️ Project Structure

The project is organized into logical directories for better maintainability:

```
📁 scripts/                    # Executable scripts
├── 📁 main/                   # Main pipeline scripts
│   ├── run_complete_pipeline.py    # Complete pipeline with change detection
│   ├── run_scheduled_pipeline.py   # Scheduled pipeline runner
│   ├── streamlit_app.py            # Web interface
│   └── main.py                     # Original main script
├── 📁 data_collection/        # Data collection scripts  
│   ├── extract_fda_indications.py
│   ├── populate_clinical_trials.py
│   └── run_*_extraction.py
├── 📁 deployment/             # Deployment configurations
│   ├── biopartnering-pipeline.service
│   ├── deploy.sh
│   └── run_pipeline_cron.sh
└── 📁 maintenance/            # Maintenance utilities
    └── setup_environment.sh

📁 src/                        # Source code modules
├── 📁 data_collection/        # Data collection logic
├── 📁 processing/             # Data processing
├── 📁 rag/                    # RAG system
├── 📁 models/                 # Data models
├── 📁 monitoring/             # Monitoring modules
└── 📁 evaluation/             # Evaluation framework

📁 config/                     # Configuration files
📁 docs/                       # Documentation
📁 monitoring/                 # Logs and monitoring
📁 outputs/                    # Generated outputs
📁 data/                       # Input data files
📁 tests/                      # Test files
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Conda or virtual environment
- API keys for OpenAI and FDA

### Installation

#### Option 1: Quick Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd Agentic-RAG-Pipeline-for-Biopartnering-Insights

# Quick setup
make setup

# Edit environment variables
cp .env.example .env
# Edit .env with your API keys
```

#### Option 2: Manual Setup
```bash
# Clone the repository
git clone <repository-url>
cd Agentic-RAG-Pipeline-for-Biopartnering-Insights

# Create conda environment
conda create -n pipe_env python=3.11 -y
conda activate pipe_env

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

## 🚀 Running the Pipeline

### Main Entry Point (Recommended)
```bash
# Show all available commands
python run_pipeline.py --help

# Run complete pipeline once
python run_pipeline.py run

# Run with force refresh
python run_pipeline.py run --force

# Start web interface
python run_pipeline.py web

# Run scheduled pipeline
python run_pipeline.py schedule

# Run individual components
python run_pipeline.py data-collect
python run_pipeline.py process
python run_pipeline.py export
```

### Using Make Commands
```bash
# Show all available commands
make help

# Run complete pipeline
make run

# Run with force refresh
make run-force

# Start web interface
make web

# Run individual components
make data-collect
make process
make export

# Development commands
make test
make clean
make logs
make status
```

### Individual Scripts
```bash
# Run complete pipeline with change detection
python scripts/main/run_complete_pipeline.py

# Run scheduled pipeline
python scripts/main/run_scheduled_pipeline.py

# Start web interface
python scripts/main/streamlit_app.py
```

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

## 📊 Data Flow

1. **Data Collection** → Raw data from multiple sources
2. **Processing** → Entity extraction and linking
3. **Storage** → SQLite database
4. **Export** → CSV files for analysis
5. **Web Interface** → Interactive exploration

## 🚀 Production Deployment

### Systemd Service
```bash
# Install service
make service-install

# Start service
make service-start

# Check status
make service-status
```

### Cron Job
```bash
# Add to crontab (runs every 6 hours)
0 */6 * * * /path/to/scripts/deployment/run_pipeline_cron.sh
```

## 📈 Monitoring

- **Pipeline State**: `monitoring/pipeline_state.json`
- **Logs**: `monitoring/logs/`
- **Database**: `biopartnering_insights.db`
- **Outputs**: `outputs/`

## 🧪 Testing

```bash
# Run all tests
make test

# Or directly
python -m pytest tests/
```

## 📝 Documentation

- **README.md**: This file
- **PROJECT_STRUCTURE.md**: Detailed project structure
- **PRD_Agentic_RAG_Pipeline_Biopartnering_Insights.md**: Product requirements
- **API Documentation**: `docs/api/`
- **User Guide**: `docs/user_guide/`

## 🔄 Change Detection & Efficiency

The pipeline includes intelligent change detection that:
- **Skips unchanged data**: Only processes new or modified data
- **Tracks state**: Maintains pipeline state in `monitoring/pipeline_state.json`
- **Forces refresh**: Use `--force` flag to refresh all data
- **Time-based refresh**: Automatically refreshes every 24 hours

## 🛠️ Development

### Adding New Data Sources
1. Create collector in `src/data_collection/`
2. Add to orchestrator in `src/data_collection/orchestrator.py`
3. Update configuration in `config/config.py`

### Adding New Processing Steps
1. Add processing logic in `src/processing/`
2. Update pipeline in `scripts/main/run_complete_pipeline.py`
3. Add tests in `tests/`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions or issues:
1. Check the documentation in `docs/`
2. Review the logs in `monitoring/logs/`
3. Check the pipeline status with `make status`
4. Open an issue on GitHub

---

**Built with ❤️ for the biotech community**