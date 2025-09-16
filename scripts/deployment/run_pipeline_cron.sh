#!/bin/bash
# Biopartnering Insights Pipeline Cron Job
# Run every 6 hours with intelligent change detection

# Set environment
export PATH="/Users/mingyuezheng/miniconda3/envs/pipe_env/bin:$PATH"
cd /Users/mingyuezheng/Agentic-RAG-Pipeline-for-Biopartnering-Insights

# Activate conda environment
source /Users/mingyuezheng/miniconda3/bin/activate pipe_env

# Run pipeline once with change detection
python run_scheduled_pipeline.py --once --verbose

# Log completion
echo "$(date): Pipeline cron job completed" >> logs/pipeline_cron.log
