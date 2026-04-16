import uuid
from typing import Any

import httpx
import jwt
from jwt.algorithms import ECAlgorithm
from fastapi import HTTPException, status

from app.core.config import settings

# ---------------------------------------------------------------------------
# JWKS cache — fetched once per process start
# ---------------------------------------------------------------------------
_jwks_cache: dict[str, Any] | None = None


def _get_jwks_public_key() -> Any:
    """Fetch the EC public key from Supabase's JWKS endpoint (cached)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            timeout=5,
        )
        resp.raise_for_status()
        jwks = resp.json()
        # Use the first key in the set
        key_data = jwks["keys"][0]
        _jwks_cache = ECAlgorithm.from_jwk(key_data)
        return _jwks_cache
    except Exception:
        return None


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """
    Verify a Supabase-issued JWT.

    Newer Supabase projects use ES256 (ECDSA P-256) with a per-project key pair.
    Older projects use HS256 with the project JWT secret.
    We try ES256 first (via JWKS), then fall back to HS256.

    Returns the decoded payload on success.
    Raises HTTPException 401 on any failure.
    """
    try:
        payload = _try_decode(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate sub claim is a non-empty valid UUID
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sub claim is not a valid UUID.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def _try_decode(token: str) -> dict[str, Any]:
    """Try ES256 first, then HS256."""
    # ── ES256 via JWKS ────────────────────────────────────────────────────
    public_key = _get_jwks_public_key()
    if public_key is not None:
        try:
            return jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                audience="authenticated",
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            pass  # fall through to HS256

    # ── HS256 fallback (older Supabase projects) ──────────────────────────
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
