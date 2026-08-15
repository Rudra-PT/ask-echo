"""
src/api/query.py
─────────────────
Document query endpoint.

Requires a valid Google ID token in the Authorization header.
The Pinecone namespace is derived server-side as f"user_{user_id}" —
any namespace field in the request body is ignored.

Registered on both /query and /query/ to prevent 307 redirect issues.
Response: {"answer": str, "sources": list[dict]}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.auth import get_current_user
from src.core.exceptions import EmbeddingError, IngestionError
from src.services import retrieval

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Retrieval"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The natural-language question to answer from the document store.",
        examples=["What does this document say about the revenue growth?"],
    )
    # namespace is accepted for API compatibility but overridden server-side
    namespace: str = Field(
        default="ignored",
        description="Ignored — namespace is derived from the authenticated user's identity.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve (1–20, default: 5).",
    )


class QueryResponse(BaseModel):
    answer: str = Field(
        description=(
            "Gemini's grounded answer. Every key fact is cited inline as "
            "[Source: filename.pdf, Page X]. Returns a standard 'not found' "
            "message when the context lacks enough information."
        )
    )
    sources: list[dict] = Field(
        description=(
            "Ranked list of retrieved chunk metadata. Each entry contains: "
            "rank, id, score, file_name, page_number, source_filename, "
            "mime_type, created_at, text_preview."
        )
    )


# ---------------------------------------------------------------------------
# Shared handler
# ---------------------------------------------------------------------------


async def _handle_query(
    body: QueryRequest,
    user_id: str,
) -> QueryResponse:
    """Core logic — namespace is always derived from user_id."""

    # Server-side namespace override — client cannot influence this
    namespace = f"user_{user_id}"

    logger.info(
        "Query: user=%s  namespace=%r  top_k=%d  query=%r",
        user_id,
        namespace,
        body.top_k,
        body.query[:80],
    )

    try:
        result = retrieval.answer_query(
            query=body.query,
            namespace=namespace,
            top_k=body.top_k,
        )
    except EmbeddingError as exc:
        logger.error("Embedding failure during query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to embed query: {exc}",
        )
    except IngestionError as exc:
        logger.error("Pinecone query failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vector store query failed: {exc}",
        )
    except RuntimeError as exc:
        logger.error("Gemini generation failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
    )


# ---------------------------------------------------------------------------
# Routes — both "" and "/" registered to avoid 307 redirects
# ---------------------------------------------------------------------------

_ROUTE_KWARGS = dict(
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the document store and get a grounded answer",
    description=(
        "Requires: Authorization: Bearer <Google ID token>. "
        "Embeds the query with Gemini text-embedding (768-dim), retrieves the "
        "top-K most relevant chunks from the authenticated user's Pinecone namespace, "
        "and asks Gemini to answer strictly from the retrieved context. "
        "Each fact is cited inline as [Source: filename.pdf, Page X]."
    ),
)


@router.post("", include_in_schema=False, **_ROUTE_KWARGS)
@router.post("/", **_ROUTE_KWARGS)
async def query_documents(
    body: QueryRequest,
    user_id: str = Depends(get_current_user),
) -> QueryResponse:
    return await _handle_query(body=body, user_id=user_id)
