# ============================================
# FILE: app/dependencies.py
# ============================================
"""
FastAPI dependencies for request handling.
"""

from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def get_rate_limit_string() -> str:
    """Get rate limit string for SlowAPI."""
    return f"{settings.RATE_LIMIT_PER_MINUTE}/minute"