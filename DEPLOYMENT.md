# 🚀 Deployment Guide

## Quick Deploy to Streamlit Community Cloud (Recommended)

### Prerequisites
- GitHub account
- OpenAI API key (for cloud deployment)

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

3. **Share with co-authors**
   - Your app will be available at: `https://your-app-name.streamlit.app`
   - Send this URL to your co-authors

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

## Notes

- **Streamlit Cloud**: Free, automatic HTTPS, easy sharing
- **ngrok**: Free tier, temporary URLs, good for testing
- **Ollama**: Only works locally, not suitable for cloud deployment
- **OpenAI**: Works everywhere, requires API key
