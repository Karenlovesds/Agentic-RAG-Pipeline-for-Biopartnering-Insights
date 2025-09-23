#!/bin/bash

# Build script for Biopartnering Insights Pipeline Docker container

set -e

echo "🐳 Building Biopartnering Insights Pipeline Docker container..."

# Build the Docker image
docker build -t biopartnering-insights:latest .

echo "✅ Docker image built successfully!"
echo ""
echo "🚀 Available commands:"
echo "  docker run -p 8501:8501 biopartnering-insights                    # Start dashboard"
echo "  docker run -p 8501:8501 biopartnering-insights full              # Run full pipeline"
echo "  docker run -p 8501:8501 biopartnering-insights collect           # Run data collection"
echo "  docker run -p 8501:8501 biopartnering-insights process           # Run data processing"
echo "  docker run -p 8501:8501 biopartnering-insights export            # Export data"
echo ""
echo "📊 Or use Docker Compose:"
echo "  docker-compose up --build                                         # Build and start"
echo "  docker-compose up -d --build                                      # Run in background"
echo ""
echo "🌐 Dashboard will be available at: http://localhost:8501"
