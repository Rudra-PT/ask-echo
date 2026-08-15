"""
src/api/upload.py
─────────────────
Document ingestion endpoint.

Accepts a PDF, JPEG, or PNG via multipart/form-data, extracts text
page-by-page (pdfplumber → pypdf fallback for PDFs; Gemini Vision for
images), splits into chunks, embeds with Gemini, and upserts into Pinecone
under the caller-supplied namespace.

Two route variants are registered so both /upload and /upload/ work
without a 307 redirect (redirect_slashes=False is set on the app).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

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
# Response schema
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    status: str
    file_name: str
    chunks_indexed: int


class ClearResponse(BaseModel):
    status: str
    namespace: str


# ---------------------------------------------------------------------------
# Handler — registered on both "" and "/" so neither triggers a redirect
# ---------------------------------------------------------------------------


async def _handle_upload(file: UploadFile, namespace: str) -> UploadResponse:
    """Shared implementation used by both route decorators."""

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
        "Upload received: filename='%s', mime='%s', namespace='%s'",
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
        "Ingestion complete: %d chunk(s) indexed for '%s' → namespace '%s'.",
        chunks_indexed,
        filename,
        namespace,
    )

    return UploadResponse(
        status="success",
        file_name=filename,
        chunks_indexed=chunks_indexed,
    )


# Dual decorators so both /upload and /upload/ are served without a redirect.
@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document (no trailing slash)",
    include_in_schema=False,  # hide duplicate from OpenAPI docs
)
@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the vector store",
    description=(
        "Accepts a PDF, JPEG, or PNG via multipart/form-data. "
        "Extracts text page-by-page, splits into chunks (size=1000, overlap=150), "
        "embeds with Gemini, and upserts into Pinecone under the given namespace. "
        "Returns the count of indexed chunks."
    ),
)
async def upload_document(
    file: UploadFile,
    namespace: str = Form(..., description="Pinecone namespace to upsert vectors into."),
) -> UploadResponse:
    return await _handle_upload(file=file, namespace=namespace)


# ---------------------------------------------------------------------------
# DELETE /upload/clear — wipe all vectors in a namespace
# ---------------------------------------------------------------------------


@router.delete(
    "/clear",
    response_model=ClearResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear all vectors in a session namespace",
    description=(
        "Deletes every vector stored under the given Pinecone namespace. "
        "Used to reset a user session so the next upload starts fresh."
    ),
)
def clear_namespace(
    namespace: str = Query(
        ...,
        description="Pinecone namespace whose vectors should be deleted.",
    ),
) -> ClearResponse:
    from src.services.vector import _get_index  # local import avoids circular dep

    if not namespace or not namespace.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="namespace query parameter must not be empty.",
        )

    try:
        index = _get_index()
        index.delete(delete_all=True, namespace=namespace)
        logger.info("Cleared all vectors in namespace '%s'.", namespace)
    except Exception as exc:
        logger.error("Failed to clear namespace '%s': %s", namespace, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to clear namespace: {exc}",
        ) from exc

    return ClearResponse(status="cleared", namespace=namespace)
