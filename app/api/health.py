"""Health check API endpoints."""

from fastapi import APIRouter
from qdrant_client.http.exceptions import UnexpectedResponse

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
    
    Returns service status and checks dependent services.
    """
    services = {}
    
    # Check Qdrant connection
    try:
        retriever = get_retriever()
        collection_info = retriever.client.get_collection(retriever.collection_name)
        services["qdrant"] = {
            "status": "healthy",
            "collection": retriever.collection_name,
            "vectors_count": collection_info.vectors_count
        }
    except UnexpectedResponse:
        services["qdrant"] = {
            "status": "unhealthy",
            "error": "Collection not found - run indexing script"
        }
    except Exception as e:
        services["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check embedding model (DON'T trigger loading)
    try:
        retriever = get_retriever()
        # Check if model is already loaded, don't trigger loading
        if retriever._model is not None:
            services["embedding_model"] = {
                "status": "healthy",
                "model": settings.EMBEDDING_MODEL
            }
        else:
            services["embedding_model"] = {
                "status": "not_loaded",
                "note": "Model loads on first query"
            }
    except Exception as e:
        # Bound error message to 100 chars
        error_msg = str(e)[:100]
        services["embedding_model"] = {
            "status": "degraded",
            "error": error_msg
        }
    
    overall_status = "healthy" if all(
        s.get("status") == "healthy" for s in services.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        services=services
    )


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Legal AI Assistant API",
        "version": "1.0.0",
        "description": "Indian Penal Code AI Assistant with RAG",
        "docs": "/docs",
        "health": "/health"
    }