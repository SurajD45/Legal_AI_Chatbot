from typing import Any, List, Optional, Union, TYPE_CHECKING
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

if TYPE_CHECKING:
    CORS_ORIGINS_TYPE = List[str]
else:
    CORS_ORIGINS_TYPE = Union[List[str], str]


class Settings(BaseSettings):
    # =====================
    # API KEYS
    # =====================
    GROQ_API_KEY: str = Field(..., description="Groq API key for LLM inference")
    GROQ_API_KEY_2: Optional[str] = Field(default=None, description="Optional extra Groq API key")
    GROQ_API_KEY_3: Optional[str] = Field(default=None, description="Optional extra Groq API key")
    GROQ_API_KEY_4: Optional[str] = Field(default=None, description="Optional extra Groq API key")
    GROQ_API_KEY_5: Optional[str] = Field(default=None, description="Optional extra Groq API key")
    HF_API_TOKEN: Optional[str] = Field(
        default=None,
        description="HuggingFace API token (optional, for rate-limited endpoints)",
    )

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
    # REDIS (UPSTASH)
    # =====================
    REDIS_URL: str = Field(..., description="Redis/Upstash connection URL")

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
    CORS_ORIGINS: CORS_ORIGINS_TYPE = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # =====================
    # MODEL CONFIG
    # =====================
    EMBEDDING_MODEL: str = Field(
        default="intfloat/multilingual-e5-base"
    )
    EMBEDDING_DIMENSION: int = Field(default=768)

    LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model ID",
    )

    # =====================
    # SEARCH / LIMITS
    # =====================
    DEFAULT_TOP_K: int = Field(default=5)
    DENSE_CANDIDATES: int = Field(default=20)
    BM25_CANDIDATES: int = Field(default=20)
    RRF_K: int = Field(default=60)
    MAX_CONTEXT_LENGTH: int = Field(default=4000)
    RATE_LIMIT_PER_MINUTE: int = Field(default=30)

    # =====================
    # SUPABASE AUTH
    # =====================
    SUPABASE_URL: str = Field(..., description="Supabase project URL")

    # =====================
    # VALIDATORS
    # =====================
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in {"development", "staging", "production"}:
            raise ValueError(
                "ENVIRONMENT must be one of: development, staging, production"
            )
        return v

    # =====================
    # HELPER METHODS
    # =====================
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance (fails fast if env is broken)
settings = Settings()