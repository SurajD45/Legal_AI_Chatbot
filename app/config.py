"""
Configuration module for Legal AI Assistant.

Loads all settings from environment variables with validation.
Fails fast if critical configuration is missing.
"""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional  

class Settings(BaseSettings):
    """
    Application settings with validation.
    
    All values are loaded from environment variables.
    Use .env file for local development.
    """
    
    # API Keys
    GROQ_API_KEY: str = Field(..., description="Groq API key for LLM")
    
    # Qdrant Configuration
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant host")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant port")
    QDRANT_COLLECTION_NAME: str = Field(
        default="ipc_legal_docs",
        description="Qdrant collection name"
    )
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")


    # Application Settings
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    
    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated allowed origins"
    )
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=10,
        description="Max requests per minute per IP"
    )
    
    # Model Configuration
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence transformer model"
    )
    LLM_MODEL: str = Field(
        default="llama3-70b-8192",
        description="Groq LLM model"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=1024,
        description="Embedding vector dimension"
    )
    
    # Search Configuration
    DEFAULT_TOP_K: int = Field(default=5, description="Default top-k for retrieval")
    MAX_CONTEXT_LENGTH: int = Field(
        default=4000,
        description="Max context length for LLM"
    )
    
    @validator("CORS_ORIGINS")
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins into list."""
        return [origin.strip() for origin in v.split(",")]
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is valid."""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
# This will fail fast if required env vars are missing
settings = Settings()