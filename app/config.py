from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # =====================
    # API KEYS
    # =====================
    GROQ_API_KEY: str = Field(...)

    # =====================
    # QDRANT (CLOUD)
    # =====================
    QDRANT_URL: str = Field(...)
    QDRANT_API_KEY: str = Field(...)
    QDRANT_COLLECTION_NAME: str = Field(default="ipc_legal_docs")

    # =====================
    # REDIS
    # =====================
    REDIS_URL: str = Field(...)

    # =====================
    # APP
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
    LLM_MODEL: str = Field(default="llama3-70b-8192")

    # =====================
    # SEARCH
    # =====================
    DEFAULT_TOP_K: int = Field(default=5)
    MAX_CONTEXT_LENGTH: int = Field(default=4000)

    # =====================
    # RATE LIMIT
    # =====================
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
            raise ValueError("Invalid ENVIRONMENT")
        return v

    # =====================
    # HELPERS (THIS FIXES YOUR ERROR)
    # =====================
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


settings = Settings()
