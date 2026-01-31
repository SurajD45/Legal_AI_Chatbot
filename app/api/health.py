"""Health check API endpoints."""

from fastapi import APIRouter

from app.models import HealthResponse
from app.config import settings
from app.core import get_retriever
from app.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    SAFE for Qdrant Cloud (no config parsing).
    """
    services = {}

    # -------------------------
    # QDRANT (SAFE CHECK)
    # -------------------------
    try:
        retriever = get_retriever()
        exists = retriever.client.collection_exists(
            retriever.collection_name
        )

        if exists:
            services["qdrant"] = {
                "status": "healthy",
                "collection": retriever.collection_name,
            }
        else:
            services["qdrant"] = {
                "status": "unhealthy",
                "error": "Collection not found"
            }

    except Exception as e:
        services["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)[:120],
        }

    # -------------------------
    # EMBEDDING MODEL
    # -------------------------
    try:
        retriever = get_retriever()
        if retriever._model is not None:
            services["embedding_model"] = {
                "status": "healthy",
                "model": settings.EMBEDDING_MODEL,
            }
        else:
            services["embedding_model"] = {
                "status": "not_loaded",
                "note": "Model loads on first query",
            }
    except Exception as e:
        services["embedding_model"] = {
            "status": "degraded",
            "error": str(e)[:120],
        }

    overall_status = (
        "healthy"
        if services.get("qdrant", {}).get("status") == "healthy"
        else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        services=services,
    )


@router.get("/")
async def root():
    return {
        "name": "Legal AI Assistant API",
        "version": "1.0.0",
        "description": "Indian Penal Code AI Assistant with RAG",
        "docs": "/docs",
        "health": "/health",
    }
