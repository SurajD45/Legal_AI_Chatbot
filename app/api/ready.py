from fastapi import APIRouter
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["readiness"])


@router.get("/ready")
def readiness():
    """
    Readiness probe.
    Indicates whether the service is ready to serve real traffic.
    """
    status = {"ready": True, "checks": {}}

    # ---- Qdrant check ----
    try:
        from app.core.retriever import get_retriever
        retriever = get_retriever()

        # lightweight check (no embeddings)
        retriever.client.get_collections()

        status["checks"]["qdrant"] = "ok"
    except Exception as e:
        logger.warning("qdrant_not_ready", error=str(e))
        status["ready"] = False
        status["checks"]["qdrant"] = "unavailable"

    # ---- Embedding model (optional, lazy) ----
    try:
        _ = retriever.model  # lazy load if not loaded
        status["checks"]["embedding_model"] = "ok"
    except Exception as e:
        logger.warning("embedding_model_not_ready", error=str(e))
        status["ready"] = False
        status["checks"]["embedding_model"] = "unavailable"

    return status
