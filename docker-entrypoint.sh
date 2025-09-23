#!/bin/bash
set -e

echo "🚀 Starting Biopartnering Insights Pipeline..."
echo "🐳 Docker Version: $(docker --version 2>/dev/null || echo 'Not available in container')"
echo "🐍 Python Version: $(python --version)"

# Function to check if port is available
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        echo "⚠️  Port $port is already in use"
        return 1
    else
        echo "✅ Port $port is available"
        return 0
    fi
}

# Function to run database initialization
init_database() {
    echo "📊 Initializing database..."
    python -c "
import sys
import os
sys.path.append('/app')
try:
    from src.models.database import create_tables, get_db
    create_tables()
    print('✅ Database initialized successfully')
except Exception as e:
    print(f'❌ Database initialization failed: {e}')
    sys.exit(1)
"
}

# Function to run data collection
run_data_collection() {
    echo "📥 Running data collection..."
    python run_pipeline.py data-collect
}

# Function to run processing
run_processing() {
    echo "⚙️ Running data processing..."
    python run_pipeline.py process
}

# Function to export data
export_data() {
    echo "📤 Exporting data..."
    python run_pipeline.py export
}

# Function to start Streamlit
start_dashboard() {
    echo "🌐 Starting dashboard..."
    echo "🔍 Checking port availability..."
    check_port 8501 || echo "⚠️  Port 8501 may be in use, but continuing..."
    
    echo "🚀 Starting Streamlit server..."
    exec python scripts/main/streamlit_app.py
}

# Main execution logic
case "${1:-dashboard}" in
    "init")
        init_database
        ;;
    "collect")
        init_database
        run_data_collection
        ;;
    "process")
        init_database
        run_processing
        ;;
    "export")
        init_database
        export_data
        ;;
    "full")
        init_database
        run_data_collection
        run_processing
        export_data
        ;;
    "dashboard"|"")
        init_database
        start_dashboard
        ;;
    *)
        echo "Available commands:"
        echo "  init      - Initialize database only"
        echo "  collect   - Run data collection"
        echo "  process   - Run data processing"
        echo "  export    - Export data to CSV"
        echo "  full      - Run full pipeline (collect + process + export)"
        echo "  dashboard - Start dashboard (default)"
        echo ""
        echo "Usage: docker run <image> [command]"
        exit 1
        ;;
esac
