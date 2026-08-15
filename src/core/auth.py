"""
src/core/auth.py
────────────────
FastAPI dependency that verifies Google ID tokens and extracts `user_id`.

Usage in route handlers:
    from src.core.auth import get_current_user

    @router.post("/")
    async def my_endpoint(user_id: str = Depends(get_current_user)):
        namespace = f"user_{user_id}"
        ...

The dependency reads the `Authorization: Bearer <token>` header, verifies
the JWT against Google's public keys using the configured GOOGLE_CLIENT_ID,
and returns the `sub` claim (a stable, unique Google user identifier).

Returns HTTP 401 on any verification failure.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from src.core.config import settings

logger = logging.getLogger(__name__)

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
# auto_error=False lets us return a clean 401 instead of FastAPI's default 403
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """
    FastAPI dependency — verifies the Google ID token and returns `user_id`.

    Args:
        credentials: Parsed Bearer token from the Authorization header.

    Returns:
        The `sub` claim string (stable Google user identifier).

    Raises:
        HTTPException 401: If the header is missing, malformed, or the token
                           fails Google's verification.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Please sign in with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # ValueError is raised for any invalid/expired/wrong-audience token
        logger.warning("Google ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Google token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error verifying Google token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id: str = id_info.get("sub", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verified but contains no user identifier (sub claim missing).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Authenticated user_id=%s", user_id)
    return user_id
