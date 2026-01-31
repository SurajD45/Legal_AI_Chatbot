from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # =====================
    # API KEYS
    # =====================
    GROQ_API_KEY: str = Field(default="", description="Groq API key (deprecated)")
    OPENROUTER_API_KEY: str = Field(..., description="OpenRouter API key")

    # =====================
    # QDRANT (CLOUD ONLY)
    # =====================
    QDRANT_URL: str = Field(..., description="Qdrant Cloud URL")
    QDRANT_API_KEY: str = Field(..., description="Qdrant Cloud API Key")
    QDRANT_COLLECTION_NAME: str = Field(
        default="ipc_legal_docs",
        description="Qdrant collection name",
    )

    # =====================
    # REDIS (SINGLE SOURCE)
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
        default="meta-llama/llama-3.3-70b-instruct:free"
    )

    # =====================
    # SEARCH / LIMITS
    # =====================
    DEFAULT_TOP_K: int = Field(default=5)
    MAX_CONTEXT_LENGTH: int = Field(default=4000)
    RATE_LIMIT_PER_MINUTE: int = Field(default=30)

    # =====================
    # VALIDATORS
    # =====================
    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors(cls, v: str) -> List[str]:
        return [x.strip() for x in v.split(",") if x.strip()]

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in {"development", "staging", "production"}:
            raise ValueError(
                "ENVIRONMENT must be one of: development, staging, production"
            )
        return v

    # =====================
    # HELPER METHODS (CRITICAL)
    # =====================
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance (fails fast if env is broken)
settings = Settings()
