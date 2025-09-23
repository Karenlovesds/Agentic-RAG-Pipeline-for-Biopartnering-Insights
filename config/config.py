"""Configuration settings for the Biopartnering Insights pipeline."""

import os
from pathlib import Path
from typing import List, Optional
import csv
from pydantic import Field
from pydantic_settings import BaseSettings
from loguru import logger


class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Model provider settings
    model_provider: str = Field("ollama", env="MODEL_PROVIDER")
    chat_model: str = Field("gpt-oss:20b", env="CHAT_MODEL")
    embed_model: str = Field("nomic-embed-text", env="EMBED_MODEL")
    ollama_host: str = Field("http://localhost:11434", env="OLLAMA_HOST")
    
    # Database settings
    database_url: str = Field("sqlite:///./biopartnering_insights.db", env="DATABASE_URL")
    chroma_persist_directory: str = Field("./chroma_db", env="CHROMA_PERSIST_DIRECTORY")
    
    # Data collection settings
    max_concurrent_requests: int = Field(5, env="MAX_CONCURRENT_REQUESTS")
    request_delay: float = Field(1.0, env="REQUEST_DELAY")
    user_agent: str = Field("Mozilla/5.0 (compatible; BiopartneringInsights/1.0)", env="USER_AGENT")
    
    # Data sources
    clinical_trials_base_url: str = "https://clinicaltrials.gov/api/v2/studies"
    drugs_com_base_url: str = "https://www.drugs.com"
    fda_base_url: str = "https://www.fda.gov"
    
    
    # Evaluation settings
    evaluation_sample_size: int = Field(100, env="EVALUATION_SAMPLE_SIZE")
    ragas_threshold: float = Field(0.8, env="RAGAS_THRESHOLD")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("./logs/biopartnering_insights.log", env="LOG_FILE")
    
    # Data refresh schedule
    refresh_schedule: str = "weekly"  # weekly, daily, or manual
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Create necessary directories
Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("outputs").mkdir(parents=True, exist_ok=True)


def get_target_companies(csv_path: str = "data/companies.csv") -> List[str]:
    """Return target companies from CSV file.

    The CSV is expected to have a header with a 'Company' column.
    Returns empty list if CSV is not found or invalid.
    """
    path = Path(csv_path)
    if path.exists():
        try:
            companies: List[str] = []
            seen = set()
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("Company") or "").strip()
                    if name and name not in seen:
                        companies.append(name)
                        seen.add(name)
            return companies
        except Exception as e:
            logger.error(f"Error reading companies CSV: {e}")
    else:
        logger.warning(f"Companies CSV not found at {csv_path}")
    
    return []

