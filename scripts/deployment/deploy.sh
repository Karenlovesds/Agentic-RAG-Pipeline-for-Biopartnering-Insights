#!/bin/bash

# Biopartnering Insights Pipeline Deployment Script
# This script sets up the pipeline for production use

set -e

echo "🚀 Deploying Biopartnering Insights Pipeline..."

# Configuration
PROJECT_DIR="/home/ubuntu/Agentic-RAG-Pipeline-for-Biopartnering-Insights"
SERVICE_NAME="biopartnering-pipeline"
USER="ubuntu"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root"
    exit 1
fi

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Please install Miniconda first."
    exit 1
fi

# Create project directory if it doesn't exist
if [ ! -d "$PROJECT_DIR" ]; then
    echo "📁 Creating project directory..."
    mkdir -p "$PROJECT_DIR"
fi

# Copy project files
echo "📋 Copying project files..."
cp -r . "$PROJECT_DIR/"

# Change to project directory
cd "$PROJECT_DIR"

# Create conda environment if it doesn't exist
echo "🐍 Setting up conda environment..."
if ! conda env list | grep -q "pipe_env"; then
    conda create -n pipe_env python=3.11 -y
fi

# Activate environment and install dependencies
echo "📦 Installing dependencies..."
source ~/miniconda3/bin/activate pipe_env
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs data outputs

# Set up environment variables
echo "⚙️ Setting up environment variables..."
if [ ! -f .env ]; then
    cat > .env << EOF
# API Keys
OPENAI_API_KEY=your_openai_api_key_here

# Model Settings
MODEL_PROVIDER=openai
CHAT_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
OLLAMA_HOST=http://localhost:11434

# Database
DATABASE_URL=sqlite:///./biopartnering_insights.db
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Monitoring
NOTIFICATIONS_ENABLED=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
NOTIFICATION_RECIPIENTS=["your_email@gmail.com"]

# Collection Settings
MAX_CONCURRENT_REQUESTS=5
REQUEST_DELAY=1.0
USER_AGENT=Mozilla/5.0 (compatible; BiopartneringInsights/1.0)
EOF
    echo "📝 Created .env file. Please update it with your API keys and email settings."
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x run_production.py
chmod +x deploy/deploy.sh

# Install systemd service
echo "🔧 Installing systemd service..."
sudo cp deploy/biopartnering-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload

# Create log rotation configuration
echo "📝 Setting up log rotation..."
sudo tee /etc/logrotate.d/biopartnering-pipeline > /dev/null << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload $SERVICE_NAME
    endscript
}
EOF

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > monitor.sh << 'EOF'
#!/bin/bash

# Biopartnering Pipeline Monitoring Script

PROJECT_DIR="/home/ubuntu/Agentic-RAG-Pipeline-for-Biopartnering-Insights"
SERVICE_NAME="biopartnering-pipeline"

cd "$PROJECT_DIR"

case "$1" in
    start)
        echo "🚀 Starting $SERVICE_NAME..."
        sudo systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "⏹️ Stopping $SERVICE_NAME..."
        sudo systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "🔄 Restarting $SERVICE_NAME..."
        sudo systemctl restart $SERVICE_NAME
        ;;
    status)
        echo "📊 Status of $SERVICE_NAME:"
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        echo "📋 Recent logs:"
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    run-once)
        echo "🔄 Running pipeline once..."
        source ~/miniconda3/bin/activate pipe_env
        python run_production.py --mode once
        ;;
    check-changes)
        echo "🔍 Checking for changes..."
        source ~/miniconda3/bin/activate pipe_env
        python run_production.py --mode check
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|run-once|check-changes}"
        exit 1
        ;;
esac
EOF

chmod +x monitor.sh

# Create cron job for weekly maintenance
echo "⏰ Setting up cron job for weekly maintenance..."
(crontab -l 2>/dev/null; echo "0 2 * * 0 $PROJECT_DIR/monitor.sh run-once") | crontab -

echo "✅ Deployment completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update .env file with your API keys and email settings"
echo "2. Test the pipeline: ./monitor.sh run-once"
echo "3. Start the service: ./monitor.sh start"
echo "4. Check status: ./monitor.sh status"
echo "5. View logs: ./monitor.sh logs"
echo ""
echo "🔧 Management commands:"
echo "  ./monitor.sh start      - Start the service"
echo "  ./monitor.sh stop       - Stop the service"
echo "  ./monitor.sh restart    - Restart the service"
echo "  ./monitor.sh status     - Check service status"
echo "  ./monitor.sh logs       - View live logs"
echo "  ./monitor.sh run-once   - Run pipeline once"
echo "  ./monitor.sh check-changes - Check for website changes"
echo ""
echo "📧 To enable email notifications:"
echo "1. Update .env file with your email settings"
echo "2. Set NOTIFICATIONS_ENABLED=true"
echo "3. Restart the service: ./monitor.sh restart"
