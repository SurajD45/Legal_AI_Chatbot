from fastapi import APIRouter
import httpx

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