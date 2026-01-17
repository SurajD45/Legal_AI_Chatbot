"""
Main FastAPI application for Legal AI Assistant.
Production-safe startup using lifespan.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.utils import setup_logging, get_logger, LegalAIException
from app.dependencies import limiter
from app.api import health, chat
from app.models import ErrorResponse

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup_begin", environment=settings.ENVIRONMENT)

    try:
        from app.core.retriever import get_retriever
        retriever = get_retriever()

        # SAFE connectivity check (NO schema parsing)
        retriever.client.get_collections()

        logger.info("qdrant_connection_ok")

    except Exception as e:
        logger.warning("qdrant_unavailable_at_startup", error=str(e))
        # IMPORTANT: DO NOT crash the app

    yield

    logger.info("shutdown_begin")


app = FastAPI(
    title="Legal AI Assistant",
    description="Indian Penal Code AI Assistant with RAG",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development() else None,
    redoc_url="/redoc" if settings.is_development() else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)
app.include_router(chat.router)

# Static frontend
try:
    app.mount("/static", StaticFiles(directory="frontend", html=True), name="frontend")
except Exception:
    logger.warning("frontend_not_mounted")


@app.exception_handler(LegalAIException)
async def legal_ai_exception_handler(request: Request, exc: LegalAIException):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=type(exc).__name__,
            message=exc.message,
            details=exc.details,
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message="Unexpected server error",
            details={},
        ).dict(),
    )
