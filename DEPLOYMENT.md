# 🚀 Deployment Guide

## Quick Deploy to Streamlit Community Cloud (Recommended)

### Prerequisites
- GitHub account
- OpenAI API key (for cloud deployment)
- Ground truth data file (`data/Pipeline_Ground_Truth.xlsx`)

### Steps

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Deploy to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "Deploy an app"
   - Select your repository
   - Set main file: `scripts/main/streamlit_app.py`
   - Add secrets:
     ```
     OPENAI_API_KEY = your_openai_api_key_here
     MODEL_PROVIDER = openai
     CHAT_MODEL = gpt-4o-mini
     EMBED_MODEL = text-embedding-3-small
     ```
   - **Important**: Ensure your ground truth file (`data/Pipeline_Ground_Truth.xlsx`) is included in the repository

3. **Share with co-authors**
   - Your app will be available at: `https://your-app-name.streamlit.app`
   - Send this URL to your co-authors

## Docker Deployment (Recommended for Production)

### Prerequisites
- Docker installed ([installation guide](https://docs.docker.com/get-docker/))
- Docker Compose (optional)

### Steps

1. **Build and run with Docker**
   ```bash
   # Build the image
   docker build -t biopartnering-insights .
   
   # Run with Docker Compose (recommended)
   docker-compose up --build
   
   # Or run directly
   docker run -p 8501:8501 biopartnering-insights
   ```

2. **Access the application**
   - Open your browser to: `http://localhost:8501`
   - All features including Ground Truth validation and Business Intelligence dashboards will be available

3. **Production deployment**
   ```bash
   # Run in background
   docker-compose up -d --build
   
   # Check status
   docker-compose ps
   
   # View logs
   docker-compose logs -f
   ```

## Alternative: Self-Hosted with ngrok (Free)

### For local testing with co-authors:

1. **Install ngrok**
   ```bash
   brew install ngrok  # macOS
   # or download from ngrok.com
   ```

2. **Run your app**
   ```bash
   streamlit run scripts/main/streamlit_app.py
   ```

3. **Expose with ngrok**
   ```bash
   ngrok http 8501
   ```

4. **Share the ngrok URL** (e.g., `https://abc123.ngrok.io`)

## Environment Variables

Create a `.env` file for local development:
```
OPENAI_API_KEY=your_openai_api_key_here
MODEL_PROVIDER=openai
CHAT_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
```

## Features Available in Each Deployment

### Streamlit Cloud
- ✅ Web Dashboard
- ✅ RAG Agent
- ✅ Ground Truth Validation
- ✅ Business Intelligence Dashboards
- ✅ Company Overlap Analysis
- ✅ Priority-Based Company Analysis
- ✅ Business Efficiency Analysis
- ✅ Ground Truth RAG Integration
- ✅ Cross-Source Validation
- ❌ Local data collection (requires external triggers)

### Docker Deployment
- ✅ Web Dashboard
- ✅ RAG Agent
- ✅ Ground Truth Validation
- ✅ Business Intelligence Dashboards
- ✅ Company Overlap Analysis
- ✅ Priority-Based Company Analysis
- ✅ Business Efficiency Analysis
- ✅ Ground Truth RAG Integration
- ✅ Cross-Source Validation
- ✅ Full data collection pipeline
- ✅ Production-ready with health checks

### Local Development
- ✅ All features available
- ✅ Full development capabilities
- ✅ Real-time debugging

## Notes

- **Streamlit Cloud**: Free, automatic HTTPS, easy sharing, limited to web interface
- **Docker**: Production-ready, full feature set, requires Docker installation ([guide](https://docs.docker.com/get-docker/))
- **ngrok**: Free tier, temporary URLs, good for testing
- **Ollama**: Only works locally, not suitable for cloud deployment
- **OpenAI**: Works everywhere, requires API key
