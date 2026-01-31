from fastapi import APIRouter
import httpx
from app.config import settings

router = APIRouter(prefix="/api", tags=["debug"])


@router.get("/test-groq")
async def test_groq_connectivity():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.groq.com")
            return {
                "status": "reachable",
                "status_code": response.status_code,
            }
    except Exception as e:
        return {
            "status": "blocked",
            "error": str(e),
        }


@router.get("/check-groq-key")
async def check_groq_key():
    key = settings.GROQ_API_KEY
    return {
        "key_exists": bool(key),
        "key_prefix": key[:10] if key else None,
        "key_length": len(key) if key else 0,
    }