
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.core.exceptions import (
    CorruptDocumentError,
    EmbeddingError,
    EmptyExtractionError,
    IngestionError,
    UnsupportedMimeError,
    VisionExtractionError,
)
from src.services import document, embedding, vector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Ingestion"])





ACCEPTED_MIME_TYPES: frozenset[str] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)


DEFAULT_NAMESPACE: str = "public"







class UploadResponse(BaseModel):

    filename: str
    mime_type: str
    chunks_extracted: int
    vectors_upserted: int
    namespace: str
    message: str







@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the vector store",
    description=(
        "Accepts a PDF, JPEG, or PNG file. Extracts text, chunks it, "
        "embeds the chunks with Gemini text-embedding-004, and upserts "
        "them into the Pinecone ask-echo-gemini index."
    ),
)
async def upload_document(file: UploadFile) -> UploadResponse:
    
    
    
    mime_type: str = file.content_type or ""

    if mime_type not in ACCEPTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type: '{mime_type}'. "
                f"Accepted types: {', '.join(sorted(ACCEPTED_MIME_TYPES))}."
            ),
        )

    filename: str = file.filename or "unknown"
    logger.info("Received upload: filename='%s', mime_type='%s'", filename, mime_type)

    
    
    
    try:
        file_bytes: bytes = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file '%s': %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (zero bytes).",
        )

    
    
    
    try:
        chunks: list[str] = document.process_document(file_bytes, mime_type)
    except UnsupportedMimeError as exc:
        
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (CorruptDocumentError, EmptyExtractionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except VisionExtractionError as exc:
        logger.error("Gemini vision failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    logger.info(
        "Extracted %d chunk(s) from '%s'.", len(chunks), filename
    )

    
    
    
    try:
        vectors: list[list[float]] = embedding.embed_chunks_batched(chunks)
    except EmbeddingError as exc:
        logger.error("Embedding failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    
    
    
    try:
        upserted = vector.upsert_vectors(
            chunks=chunks,
            vectors=vectors,
            namespace=DEFAULT_NAMESPACE,
            metadata_extra={
                "source_filename": filename,
                "mime_type": mime_type,
            },
        )
    except IngestionError as exc:
        logger.error("Pinecone upsert failure for '%s': %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    logger.info(
        "Successfully upserted %d vector(s) for '%s' into namespace '%s'.",
        upserted,
        filename,
        DEFAULT_NAMESPACE,
    )

    return UploadResponse(
        filename=filename,
        mime_type=mime_type,
        chunks_extracted=len(chunks),
        vectors_upserted=upserted,
        namespace=DEFAULT_NAMESPACE,
        message=f"Document '{filename}' ingested successfully.",
    )
