# 🚀 Setup Guide for New Team Members

This guide will help your coworker get the Biopartnering Insights Pipeline up and running quickly.

## 📋 Prerequisites

Before starting, ensure you have:

- **Python 3.11+** (recommended: 3.11 or 3.12)
- **Git** (for cloning the repository)
- **Conda** (recommended) or **pip** (for package management)
- **Ollama** (for local AI models) OR **OpenAI API key** (for cloud models)
- **Docker** (optional, for containerized deployment)
- **PostgreSQL** (for database storage)
- **Ground Truth Data** (Pipeline_Ground_Truth.xlsx file for validation)

## 🔧 Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Agentic-RAG-Pipeline-for-Biopartnering-Insights.git
cd Agentic-RAG-Pipeline-for-Biopartnering-Insights
```

### 2. Set Up Python Environment

#### Option A: Using Conda (Recommended)
```bash
# Create conda environment
conda create -n biopartnering python=3.11 -y
conda activate biopartnering

# Install dependencies
pip install -r requirements.txt
```

#### Option B: Using pip + venv
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Create .env file
touch .env  # On Windows: type nul > .env
```

### 4. Set Up Ground Truth Data

Ensure the `data/Pipeline_Ground_Truth.xlsx` file is present for validation and business intelligence features:

```bash
# Verify ground truth file exists
ls -la data/Pipeline_Ground_Truth.xlsx
```

### 5. Verify Output Structure

The pipeline generates consolidated output files:

```bash
# Check for main output files
ls -la outputs/
# Should show:
# - drugs_dashboard.csv (consolidated drug data)
# - drug_collection_summary.txt (pipeline summary)
# - validation_results.json (ground truth validation)
# - company_overlap_analysis.csv (overlap analysis)
```

Add the following content to `.env`:

```env
# Required: Choose ONE of the following options

# Option 1: OpenAI (Cloud-based, requires API key)
OPENAI_API_KEY=your_openai_api_key_here
MODEL_PROVIDER=openai
CHAT_MODEL=gpt-4
EMBED_MODEL=text-embedding-3-small

# Option 2: Ollama (Local, free)
# MODEL_PROVIDER=ollama
# CHAT_MODEL=gpt-oss:20b
# EMBED_MODEL=nomic-embed-text
# OLLAMA_HOST=http://localhost:11434

# Database settings (defaults are fine)
DATABASE_URL=sqlite:///./biopartnering_insights.db
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Optional: Logging and performance
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=5
REQUEST_DELAY=1.0
```

### 4. Set Up AI Models

#### Option A: Using OpenAI (Easier)
1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. Add it to your `.env` file as shown above
3. Skip to Step 5

#### Option B: Using Ollama (Free, Local)
1. **Install Ollama:**
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows
   # Download from https://ollama.ai/download
   ```

2. **Start Ollama service:**
   ```bash
   ollama serve
   ```

3. **Download required models:**
   ```bash
   # In a new terminal
   ollama pull gpt-oss:20b
   ollama pull nomic-embed-text
   ```

4. **Update your `.env` file** to use Ollama (uncomment the Ollama section)

### 5. Initialize the Database

```bash
# Create database tables
python -c "from src.models.database import Base, engine; Base.metadata.create_all(engine)"
```

### 6. Test the Setup

```bash
# Test the pipeline
python run_pipeline.py --help

# Test maintenance (optional)
python run_pipeline.py maintenance

# Test data collection (optional)
python run_pipeline.py data-collect

# Test validation (optional)
python scripts/validation/run_validation.py
```

### 7. Launch the Web Interface

```bash
# Start the Streamlit dashboard
streamlit run scripts/main/streamlit_app.py
```

The dashboard will be available at: `http://localhost:8501`

## 🎯 Quick Start Commands

Once set up, here are the most useful commands:

```bash
# Run complete pipeline
python run_pipeline.py run

# Run with force refresh
python run_pipeline.py run --force

# Run individual components
python run_pipeline.py maintenance    # Database cleanup
python run_pipeline.py data-collect  # Data collection
python run_pipeline.py process       # Data processing
python run_pipeline.py export        # Export CSV files

# Validation and analysis
python scripts/validation/run_validation.py  # Run ground truth validation
python scripts/analysis/overlap_analysis.py  # Run company overlap analysis

# Start web interface
python run_pipeline.py web

# Docker deployment (alternative)
docker-compose up --build  # Start with Docker
docker run -p 8501:8501 biopartnering-insights  # Run single container

# Using Makefile (alternative)
make run          # Run complete pipeline
make maintenance  # Run maintenance
make web          # Start web interface
make docker       # Build and run with Docker
```

## 🔍 Troubleshooting

### Common Issues

#### 1. "No module named 'scripts.main'" Error
```bash
# Make sure you're in the project root directory
cd /path/to/Agentic-RAG-Pipeline-for-Biopartnering-Insights
python run_pipeline.py --help
```

#### 2. Ollama Connection Error
```bash
# Check if Ollama is running
ollama list

# Start Ollama if not running
ollama serve

# Check if models are installed
ollama list
```

#### 3. OpenAI API Error
```bash
# Check your API key in .env file
cat .env | grep OPENAI_API_KEY

# Test API key
python -c "import openai; print('API key valid')"
```

#### 4. Database Errors
```bash
# Recreate database
rm biopartnering_insights.db
python -c "from src.models.database import Base, engine; Base.metadata.create_all(engine)"
```

#### 5. Port Already in Use
```bash
# Kill existing Streamlit process
pkill -f streamlit

# Or use different port
streamlit run scripts/main/streamlit_app.py --server.port 8502
```

### Getting Help

1. **Check logs:**
   ```bash
   tail -f logs/biopartnering_insights.log
   ```

2. **Run with verbose output:**
   ```bash
   python run_pipeline.py run --verbose
   ```

3. **Check system status:**
   ```bash
   python -c "from src.models.database import get_db; print('Database OK')"
   ```

## 📊 What You'll Get

After successful setup, you'll have:

- **Web Dashboard**: Interactive interface at `http://localhost:8501`
- **Database**: SQLite database with collected biopharma data
- **CSV Exports**: Structured data files in `outputs/` directory
- **RAG Agent**: AI-powered query system for biopartnering insights
- **Ground Truth Validation**: Compare pipeline data against curated ground truth
- **Business Intelligence**: Market analysis, business analysis, company overlap analysis, and priority-based company breakdowns
- **Docker Support**: Containerized deployment option
- **Maintenance System**: Automated data quality management

## 🎉 Next Steps

1. **Explore the Dashboard**: Navigate through the different sections
2. **Try the RAG Agent**: Ask questions about biopharma drugs and companies
3. **Run Data Collection**: Collect fresh data from various sources
4. **Check Ground Truth Validation**: Compare pipeline data against curated ground truth
5. **Explore Business Intelligence**: Use Market Analysis, Business Analysis, and Company Overlap Analysis dashboards
6. **Check Exports**: Review the generated CSV files
7. **Read the Documentation**: Check `docs/` folder for detailed guides

## 📞 Support

If you encounter issues:

1. Check this setup guide first
2. Review the logs in `logs/biopartnering_insights.log`
3. Check the main README.md for additional information
4. Contact the team for assistance

---

**Happy Biopartnering! 🧬🚀**


