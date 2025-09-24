# Biopartnering Insights Pipeline - Makefile

.PHONY: help install run run-force schedule web data-collect process export test clean setup

# Default target
help:
	@echo "Biopartnering Insights Pipeline - Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  setup          Set up the environment and install dependencies"
	@echo "  install        Install Python dependencies"
	@echo ""
	@echo "Pipeline Operations:"
	@echo "  run            Run complete pipeline once"
	@echo "  run-force      Run complete pipeline with force refresh"
	@echo "  schedule       Run scheduled pipeline (continuous)"
	@echo "  web            Start web interface"
	@echo ""
	@echo "Individual Components:"
	@echo "  maintenance    Run database maintenance only"
	@echo "  data-collect   Run data collection only"
	@echo "  process        Run processing only"
	@echo "  export         Run exports only"
	@echo ""
	@echo "Development:"
	@echo "  test           Run all tests"
	@echo "  clean          Clean temporary files"
	@echo "  logs           View recent logs"
	@echo ""

# Setup
setup: install
	@echo "Setting up environment..."
	@mkdir -p logs outputs monitoring/logs
	@echo "Environment setup complete!"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Dependencies installed!"

# Pipeline operations
run:
	@echo "Running complete pipeline..."
	python run_pipeline.py run

run-force:
	@echo "Running complete pipeline with force refresh..."
	python run_pipeline.py run --force

schedule:
	@echo "Starting scheduled pipeline..."
	python run_pipeline.py schedule

web:
	@echo "Starting web interface..."
	python run_pipeline.py web

# Individual components
maintenance:
	@echo "Running database maintenance..."
	python run_pipeline.py maintenance

data-collect:
	@echo "Running data collection..."
	python run_pipeline.py data-collect

process:
	@echo "Running processing..."
	python run_pipeline.py process

export:
	@echo "Running exports..."
	python run_pipeline.py export

# Development
test:
	@echo "Running tests..."
	python -m pytest tests/ -v

clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	@echo "Cleanup complete!"

logs:
	@echo "Recent pipeline logs:"
	@tail -n 50 monitoring/logs/*.log 2>/dev/null || echo "No logs found"

# Database operations
db-reset:
	@echo "Resetting database..."
	rm -f biopartnering_insights.db
	python run_pipeline.py run --force

db-backup:
	@echo "Backing up database..."
	cp biopartnering_insights.db "backup_$(shell date +%Y%m%d_%H%M%S).db"

# Production deployment
deploy:
	@echo "Deploying to production..."
	@chmod +x scripts/deployment/deploy.sh
	./scripts/deployment/deploy.sh

# Service management
service-install:
	@echo "Installing systemd service..."
	sudo cp scripts/deployment/biopartnering-pipeline-scheduled.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable biopartnering-pipeline-scheduled
	@echo "Service installed!"

service-start:
	@echo "Starting service..."
	sudo systemctl start biopartnering-pipeline-scheduled

service-stop:
	@echo "Stopping service..."
	sudo systemctl stop biopartnering-pipeline-scheduled

service-status:
	@echo "Service status:"
	sudo systemctl status biopartnering-pipeline-scheduled

# Monitoring
status:
	@echo "Pipeline Status:"
	@echo "=================="
	@echo "Database size: $(shell du -h biopartnering_insights.db 2>/dev/null || echo 'Not found')"
	@echo "Output files: $(shell ls -la outputs/ 2>/dev/null | wc -l) files"
	@echo "Log files: $(shell ls -la monitoring/logs/ 2>/dev/null | wc -l) files"
	@echo "Last run: $(shell cat monitoring/pipeline_state.json 2>/dev/null | grep last_run | cut -d'"' -f4 || echo 'Unknown')"

