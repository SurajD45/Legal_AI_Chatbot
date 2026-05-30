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
    Reports status of Qdrant and embedding configuration.
    """
    services = {}

    # -------------------------
    # QDRANT
    # -------------------------
    try:
        retriever = get_retriever()
        collections = retriever.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if retriever.collection_name in collection_names:
            collection_info = retriever.client.get_collection(
                collection_name=retriever.collection_name
            )
            services["qdrant"] = {
                "status": "healthy",
                "collection": retriever.collection_name,
                "points_count": collection_info.points_count,
            }
        else:
            services["qdrant"] = {
                "status": "unhealthy",
                "error": f"Collection '{retriever.collection_name}' not found",
            }

    except Exception as e:
        services["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)[:120],
        }

    # -------------------------
    # EMBEDDING (HF Inference API)
    # -------------------------
    services["embedding"] = {
        "status": "configured",
        "model": settings.EMBEDDING_MODEL,
        "provider": "huggingface_inference_api",
        "note": "Embeddings are generated on-demand via HF API",
    }

    # -------------------------
    # LLM (Groq)
    # -------------------------
    services["llm"] = {
        "status": "configured",
        "model": settings.LLM_MODEL,
        "provider": "groq",
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