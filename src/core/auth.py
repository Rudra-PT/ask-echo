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

# Known Google Client IDs for Ask-Echo (development and production)
KNOWN_CLIENT_IDS = {
    "885053465809-tq1idfh7lck5fgap3ulj7nm35juc7fli.apps.googleusercontent.com",
    "885053465809-e51va13du7qu3g5316r8dn0vklbg40mo.apps.googleusercontent.com",
}

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
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token.strip()

    # Google ID Token must be a valid raw JWT (3 base64url segments separated by exactly 2 dots)
    if token.count(".") != 2:
        logger.warning(
            "Rejected token that is not a valid 3-part Google ID Token JWT (dots=%d)",
            token.count("."),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format: expected a Google JWT ID token with 3 segments. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cryptographically verify the token with Google (signature, expiration, issuer)
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=None,  # Verified manually below to support all project client IDs
        )
    except ValueError as exc:
        logger.warning("Google ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Google ID token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error verifying Google ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Validate that the token audience matches an allowed Ask-Echo client ID
    env_cids = {cid.strip() for cid in settings.GOOGLE_CLIENT_ID.split(",") if cid.strip()}
    allowed_audiences = env_cids | KNOWN_CLIENT_IDS

    token_aud: str = str(id_info.get("aud", ""))
    is_valid_aud = (
        token_aud in allowed_audiences
        or token_aud.startswith("885053465809-")
    )

    if not is_valid_aud:
        logger.warning("Google ID token audience mismatch: %s", token_aud)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google token audience mismatch: {token_aud}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = id_info.get("sub", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verified but contains no user identifier (sub claim missing).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Authenticated user_id=%s", user_id)
    return user_id
