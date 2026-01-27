"""
Configuration module for Legal AI Assistant.

Loads all settings from environment variables with validation.
Fails fast if critical configuration is missing.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional


class Settings(BaseSettings):
    # =====================
    # API KEYS
    # =====================
    GROQ_API_KEY: str = Field(..., description="Groq API key for LLM")

    # =====================
    # QDRANT
    # =====================
    QDRANT_HOST: str = Field(default="localhost")
    QDRANT_PORT: int = Field(default=6333)
    QDRANT_COLLECTION_NAME: str = Field(default="ipc_legal_docs")

    # =====================
    # REDIS (IMPORTANT)
    # =====================
    REDIS_URL: str = Field(..., description="Redis connection URL")

    # =====================
    # APP SETTINGS
    # =====================
    ENVIRONMENT: str = Field(default="development")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # =====================
    # CORS
    # =====================
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000"
    )

    # =====================
    # MODEL CONFIG
    # =====================
    EMBEDDING_MODEL: str = Field(
        default="intfloat/multilingual-e5-base"
    )
    EMBEDDING_DIMENSION: int = Field(default=768)

    LLM_MODEL: str = Field(
        default="llama3-70b-8192"
    )

    # =====================
    # SEARCH CONFIG
    # =====================
    DEFAULT_TOP_K: int = Field(default=5)
    MAX_CONTEXT_LENGTH: int = Field(default=4000)

    @validator("CORS_ORIGINS")
    def parse_cors(cls, v: str) -> List[str]:
        return [x.strip() for x in v.split(",")]

    @validator("ENVIRONMENT")
    def validate_env(cls, v: str) -> str:
        if v not in {"development", "staging", "production"}:
            raise ValueError("Invalid ENVIRONMENT")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

    
    # =====================
    # RATE LIMITING
    # =====================
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=30,
        description="Max requests per minute per IP"
    )


settings = Settings()
