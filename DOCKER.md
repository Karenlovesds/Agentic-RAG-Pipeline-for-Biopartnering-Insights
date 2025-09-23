# 🐳 Docker Setup for Biopartnering Insights Pipeline

This document explains how to run the Biopartnering Insights Pipeline using Docker.

## 📋 Prerequisites

- Docker installed on your system
- Docker Compose (optional, for easier management)

> **Note**: If you don't have Docker installed, please visit [Docker's official installation guide](https://docs.docker.com/get-docker/) for your operating system.

## 🚀 Quick Start

### Option 1: Using Docker Compose (Recommended)

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

### Option 2: Using Docker directly

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

The Docker container supports several commands:

### 1. Dashboard (Default)
```bash
docker run -p 8501:8501 biopartnering-insights dashboard
# or simply
docker run -p 8501:8501 biopartnering-insights
```

### 2. Initialize Database
```bash
docker run biopartnering-insights init
```

### 3. Data Collection
```bash
docker run biopartnering-insights collect
```

### 4. Data Processing
```bash
docker run biopartnering-insights process
```

### 5. Export Data
```bash
docker run biopartnering-insights export
```

### 6. Full Pipeline
```bash
docker run biopartnering-insights full
```

## 📁 Data Persistence

To persist data between container restarts, mount the following volumes:

```bash
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/monitoring:/app/monitoring \
  -v $(pwd)/biopartnering_insights.db:/app/biopartnering_insights.db \
  biopartnering-insights
```

## 🔧 Configuration

### Environment Variables

You can set the following environment variables:

```bash
docker run -p 8501:8501 \
  -e PYTHONPATH=/app \
  -e STREAMLIT_SERVER_PORT=8501 \
  -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  biopartnering-insights
```

### Custom Configuration

To use custom configuration files, mount them:

```bash
docker run -p 8501:8501 \
  -v $(pwd)/config:/app/config \
  biopartnering-insights
```

## 🏗️ Development

### Building for Development

```bash
# Build with development dependencies
docker build -t biopartnering-insights:dev .

# Run with volume mounts for development
docker run -p 8501:8501 \
  -v $(pwd):/app \
  biopartnering-insights:dev
```

### Debugging

```bash
# Run with interactive shell
docker run -it biopartnering-insights /bin/bash

# Check container logs
docker logs <container_id>

# Execute commands in running container
docker exec -it <container_id> /bin/bash
```

## 📊 Monitoring

The container includes health checks:

```bash
# Check container health
docker ps

# View health check logs
docker inspect <container_id> | grep -A 10 Health
```

## 🚀 Production Deployment

### Using Docker Compose

```yaml
version: '3.8'
services:
  biopartnering-pipeline:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./outputs:/app/outputs
      - ./biopartnering_insights.db:/app/biopartnering_insights.db
    restart: unless-stopped
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
```

### Using Docker Swarm

```bash
# Deploy stack
docker stack deploy -c docker-compose.yml biopartnering

# Scale service
docker service scale biopartnering_biopartnering-pipeline=3
```

## 🔍 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Use different port
   docker run -p 8502:8501 biopartnering-insights
   ```

2. **Permission denied**
   ```bash
   # Fix permissions
   chmod +x docker-entrypoint.sh
   ```

3. **Database connection issues**
   ```bash
   # Check database file permissions
   ls -la biopartnering_insights.db
   ```

4. **Container won't start**
   ```bash
   # Check logs
   docker logs <container_id>
   
   # Run with debug mode
   docker run -it biopartnering-insights /bin/bash
   ```

### Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs biopartnering-pipeline

# Follow logs in real-time
docker-compose logs -f
```

## 📈 Performance

### Resource Limits

```yaml
services:
  biopartnering-pipeline:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Optimization

- Use multi-stage builds for smaller images
- Leverage Docker layer caching
- Use .dockerignore to exclude unnecessary files
- Consider using Alpine Linux base image for smaller size

## 🔒 Security

### Best Practices

1. **Don't run as root**
   ```dockerfile
   RUN adduser --disabled-password --gecos '' appuser
   USER appuser
   ```

2. **Use specific versions**
   ```dockerfile
   FROM python:3.11-slim
   ```

3. **Scan for vulnerabilities**
   ```bash
   docker scan biopartnering-insights
   ```

4. **Use secrets for sensitive data**
   ```yaml
   services:
     biopartnering-pipeline:
       secrets:
         - db_password
   ```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Streamlit Deployment](https://docs.streamlit.io/deploy)
- [Python Docker Best Practices](https://pythonspeed.com/docker/)
