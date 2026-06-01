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
    """
    Returns rate limit string for SlowAPI.
    Falls back safely if env var is missing.
    """
    limit = getattr(settings, "RATE_LIMIT_PER_MINUTE", 30)
    return f"{limit}/minute"


# ============================================
# JWT AUTHENTICATION (ES256 + JWKS)
# ============================================
from typing import Optional
import time
import httpx
from jose import jwt
from jose.exceptions import JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

class JWKSKeyManager:
    """Manages fetching, caching, and rate-limited refreshing of Supabase JWKS keys."""
    
    def __init__(self, supabase_url: str):
        self.jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        self._keys = {}
        self._last_fetched = 0.0
        self._cooldown_seconds = 30.0  # Throttle refresh to prevent JWKS endpoint flooding (DoS)

    def _fetch_keys(self) -> None:
        try:
            logger.info("fetching_jwks_keys", url=self.jwks_url)
            self._last_fetched = time.time()
            response = httpx.get(self.jwks_url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            new_keys = {}
            for key in data.get("keys", []):
                kid = key.get("kid")
                if kid:
                    new_keys[kid] = key
                    
            self._keys = new_keys
            logger.info("jwks_keys_fetched_successfully", count=len(new_keys), kids=list(new_keys.keys()))
        except Exception as e:
            logger.error("failed_to_fetch_jwks_keys", error=str(e))
            # Don't fail completely if we have cached keys
            if not self._keys:
                raise HTTPException(status_code=500, detail="Failed to retrieve authentication keys")

    def get_key(self, kid: str) -> dict:
        if kid not in self._keys:
            now = time.time()
            time_since_last_fetch = now - self._last_fetched
            
            if time_since_last_fetch < self._cooldown_seconds:
                logger.warning(
                    "jwks_refresh_throttled",
                    time_remaining=self._cooldown_seconds - time_since_last_fetch,
                    kid=kid
                )
                raise HTTPException(
                    status_code=401,
                    detail="Authentication keys rotated recently or invalid key ID provided"
                )
                
            logger.info("jwks_cache_miss_triggering_refresh", kid=kid)
            self._fetch_keys()
            
        key = self._keys.get(kid)
        if not key:
            logger.warning("jwks_key_not_found_after_refresh", kid=kid)
            raise HTTPException(status_code=401, detail="Invalid token signing key")
            
        return key


# Initialize the global JWKS manager
jwks_manager = JWKSKeyManager(settings.SUPABASE_URL)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Dependency to verify Supabase JWT using ES256 with dynamic JWKS keys.
    Returns the authenticated sub (user_id UUID).
    Enforces a strict 401 response for all authentication failures.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning("auth_header_missing")
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("auth_header_invalid_format", header=auth_header)
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = parts[1]
    try:
        # 1. Parse header without verification to extract kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            logger.warning("jwt_header_missing_kid")
            raise HTTPException(status_code=401, detail="Invalid token: missing kid in header")
            
        # 2. Get verification public key matching kid
        key = jwks_manager.get_key(kid)
        
        # 3. Verify signature and claims
        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        
        # 4. Extract and validate user identifier (sub)
        user_id: str = payload.get("sub")
        if not user_id:
            logger.warning("jwt_payload_missing_sub")
            raise HTTPException(status_code=401, detail="Invalid token: sub claim is missing")
            
        return user_id
        
    except JWTError as e:
        logger.warning("jwt_signature_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
    except HTTPException:
        # Re-raise FastAPIs HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error("jwt_unexpected_error", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")