"""
src/api/upload.py
─────────────────
Document ingestion + session-clear endpoints.

All routes require a valid Google ID token in the Authorization header.
The Pinecone namespace is derived server-side as f"user_{user_id}" —
any client-supplied namespace field is ignored, guaranteeing isolation.

Two POST variants (/upload and /upload/) avoid 307 redirects.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from src.core.auth import get_current_user
from src.core.exceptions import (
    CorruptDocumentError,
    EmbeddingError,
    EmptyExtractionError,
    IngestionError,
    UnsupportedMimeError,
    VisionExtractionError,
)
from src.services.upload_service import ACCEPTED_MIME_TYPES, ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Ingestion"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    status: str
    file_name: str
    chunks_indexed: int


class ClearResponse(BaseModel):
    status: str
    namespace: str


# ---------------------------------------------------------------------------
# Shared upload handler
# ---------------------------------------------------------------------------


async def _handle_upload(
    file: UploadFile,
    user_id: str,
) -> UploadResponse:
    """Shared implementation used by both POST route decorators."""

    # Server-side namespace — client cannot influence this
    namespace = f"user_{user_id}"

    mime_type: str = file.content_type or ""
    filename: str = file.filename or "unknown"

    # --- MIME validation ---
    if mime_type not in ACCEPTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type: '{mime_type}'. "
                f"Accepted types: {', '.join(sorted(ACCEPTED_MIME_TYPES))}."
            ),
        )

    logger.info(
        "Upload: user=%s  file='%s'  mime='%s'  namespace='%s'",
        user_id,
        filename,
        mime_type,
        namespace,
    )

    # --- Read bytes ---
    try:
        file_bytes: bytes = await file.read()
    except Exception as exc:
        logger.error("Failed to read upload '%s': %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (zero bytes).",
        )

    # --- Full ingestion pipeline ---
    try:
        chunks_indexed = ingest_document(
            file_bytes=file_bytes,
            mime_type=mime_type,
            file_name=filename,
            namespace=namespace,
        )
    except UnsupportedMimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (CorruptDocumentError, EmptyExtractionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except VisionExtractionError as exc:
        logger.error("Gemini Vision failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except EmbeddingError as exc:
        logger.error("Embedding failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except IngestionError as exc:
        logger.error("Pinecone upsert failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    logger.info(
        "Ingestion complete: %d chunk(s) for '%s' → namespace '%s'.",
        chunks_indexed,
        filename,
        namespace,
    )

    return UploadResponse(
        status="success",
        file_name=filename,
        chunks_indexed=chunks_indexed,
    )


# ---------------------------------------------------------------------------
# POST /upload  +  POST /upload/   — dual routes, no 307 redirect
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document (no trailing slash)",
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the vector store",
    description=(
        "Requires: Authorization: Bearer <Google ID token>. "
        "Accepts a PDF, JPEG, or PNG via multipart/form-data. "
        "Namespace is derived server-side from the verified user identity. "
        "Returns the count of indexed chunks."
    ),
)
async def upload_document(
    file: UploadFile,
    # namespace from client is accepted in the form but intentionally ignored —
    # the real namespace is derived from user_id inside _handle_upload.
    namespace: str = Form(default="ignored"),
    user_id: str = Depends(get_current_user),
) -> UploadResponse:
    return await _handle_upload(file=file, user_id=user_id)


# ---------------------------------------------------------------------------
# DELETE /upload/clear — wipe all vectors for the authenticated user
# ---------------------------------------------------------------------------


@router.delete(
    "/clear",
    response_model=ClearResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear all vectors for the current user",
    description=(
        "Requires: Authorization: Bearer <Google ID token>. "
        "Deletes every vector stored under the authenticated user's namespace. "
        "The namespace is derived server-side — no client input required."
    ),
)
def clear_namespace(
    user_id: str = Depends(get_current_user),
) -> ClearResponse:
    from src.services.vector import _get_index  # local import avoids circular dep

    namespace = f"user_{user_id}"

    try:
        index = _get_index()
        index.delete(delete_all=True, namespace=namespace)
        logger.info("Cleared namespace '%s' for user %s.", namespace, user_id)
    except Exception as exc:
        logger.error("Failed to clear namespace '%s': %s", namespace, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to clear namespace: {exc}",
        ) from exc

    return ClearResponse(status="cleared", namespace=namespace)
