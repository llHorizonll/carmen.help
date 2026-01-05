"""
Configuration module for Carmen.help backend.
Loads environment variables and provides configuration settings.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

# Get the project root directory (parent of backend)
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    app_name: str = "Carmen.help API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Z.ai LLM Configuration
    zai_api_key: str = ""
    zai_api_base: str = "https://api.z.ai/api/paas/v4/"
    zai_model: str = "glm-4"
    zai_max_tokens: int = 4096
    zai_temperature: float = 0.7

    # Vector Database Configuration
    chroma_persist_dir: str = "./data/chroma"
    vector_collection: str = "carmen_docs"

    # RAG Configuration
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7
    rag_context_max_tokens: int = 4000

    # CORS Configuration
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Docs Configuration
    docs_site_url: str = "https://docscarmencloud.vercel.app"

    class Config:
        env_file = str(ENV_FILE)
        extra = "ignore"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


# Load settings once at import time
settings = Settings()
