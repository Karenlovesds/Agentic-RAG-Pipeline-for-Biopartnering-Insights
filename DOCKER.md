# 🐳 Docker Setup for Biopartnering Insights Pipeline

Quick guide to run the Biopartnering Insights Pipeline using Docker.

## 📋 Prerequisites

- Docker installed on your system
- Docker Compose (optional, for easier management)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Using Docker Directly

```bash
# Build the image
docker build -t biopartnering-insights .

# Run the dashboard
docker run -p 8501:8501 biopartnering-insights

# Run with data persistence
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/biopartnering_insights.db:/app/biopartnering_insights.db \
  biopartnering-insights
```

## 🎯 Available Commands

```bash
# Dashboard (default)
docker run -p 8501:8501 biopartnering-insights

# Initialize database
docker run biopartnering-insights init

# Data collection
docker run biopartnering-insights collect

# Data processing
docker run biopartnering-insights process

# Export data
docker run biopartnering-insights export

# Full pipeline
docker run biopartnering-insights full
```

## 📁 Data Persistence

Mount volumes to persist data between container restarts:

```bash
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/biopartnering_insights.db:/app/biopartnering_insights.db \
  biopartnering-insights
```

## 🔧 Configuration

### Environment Variables

```bash
docker run -p 8501:8501 \
  -e PYTHONPATH=/app \
  -e STREAMLIT_SERVER_PORT=8501 \
  -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  biopartnering-insights
```

### Custom Configuration

```bash
docker run -p 8501:8501 \
  -v $(pwd)/config:/app/config \
  biopartnering-insights
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   docker run -p 8502:8501 biopartnering-insights
   ```

2. **Check container logs**
   ```bash
   docker logs <container_id>
   ```

3. **Debug mode**
   ```bash
   docker run -it biopartnering-insights /bin/bash
   ```

## 📚 Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Streamlit Deployment](https://docs.streamlit.io/deploy)
