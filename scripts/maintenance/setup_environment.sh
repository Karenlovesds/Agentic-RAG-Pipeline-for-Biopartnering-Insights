#!/bin/bash

# Biopartnering Insights Pipeline - Environment Setup Script
# This script sets up the complete environment including Ollama

echo "🧬 Setting up Biopartnering Insights Pipeline Environment"
echo "=================================================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Please install Miniconda or Anaconda first."
    echo "   Download from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo "📦 Creating conda environment 'pipe_env'..."
conda create -n pipe_env python=3.11 -y

# Activate environment
echo "🔄 Activating environment..."
source ~/miniconda3/bin/activate pipe_env

# Install Python dependencies
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

# Install Ollama
echo "🦙 Installing Ollama..."

# Detect OS and install Ollama
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "   Detected macOS, installing Ollama via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ollama
    else
        echo "   Homebrew not found. Installing Ollama manually..."
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "   Detected Linux, installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "   Unsupported OS: $OSTYPE"
    echo "   Please install Ollama manually from: https://ollama.ai/download"
fi

# Start Ollama service
echo "🚀 Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to start
echo "⏳ Waiting for Ollama to start..."
sleep 5

# Pull required models
echo "📥 Pulling required Ollama models..."
ollama pull llama3.1
ollama pull nomic-embed-text

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p data outputs logs chroma_db

# Initialize database
echo "🗄️ Initializing database..."
python -c "
from src.models.database import engine, Base
Base.metadata.create_all(bind=engine)
print('✅ Database initialized successfully')
"

# Test installation
echo "🧪 Testing installation..."
python -c "
from src.rag.provider import build_provider
from src.models.database import get_db

# Test provider
provider = build_provider('ollama', 'llama3.1', 'nomic-embed-text')
print('✅ Ollama provider working')

# Test database
db = get_db()
print('✅ Database connection working')
db.close()
"

echo ""
echo "🎉 Environment setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Activate environment: conda activate pipe_env"
echo "   2. Start Ollama: ollama serve"
echo "   3. Run Streamlit app: streamlit run streamlit_app.py"
echo "   4. Open browser to: http://localhost:8501"
echo ""
echo "🔧 Environment details:"
echo "   - Conda environment: pipe_env"
echo "   - Python version: 3.11"
echo "   - Ollama models: llama3.1, nomic-embed-text"
echo "   - Database: SQLite (biopartnering_insights.db)"
echo ""
echo "💡 To stop Ollama: kill $OLLAMA_PID"
