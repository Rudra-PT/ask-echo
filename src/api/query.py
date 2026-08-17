"""
src/api/query.py
────────────────
Document query endpoint with grounded answer generation.
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


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The natural-language question to answer from the document store.",
    )
    namespace: str = Field(
        default="ignored",
        description="Ignored — namespace is derived from the authenticated user identity.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve (1–20, default: 5).",
    )


class QueryResponse(BaseModel):
    answer: str = Field(
        description="Grounded answer with inline citation tags."
    )
    sources: list[dict] = Field(
        description="Ranked list of retrieved chunk metadata."
    )


async def _handle_query(
    body: QueryRequest,
    user_id: str,
) -> QueryResponse:
    namespace = f"user_{user_id}"

    logger.info(
        "Query: user=%s namespace=%r top_k=%d query=%r",
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


_ROUTE_KWARGS = dict(
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the document store and get a grounded answer",
    description="Retrieves top-K relevant chunks from Pinecone and generates a grounded response.",
)


@router.post("", include_in_schema=False, **_ROUTE_KWARGS)
@router.post("/", **_ROUTE_KWARGS)
async def query_documents(
    body: QueryRequest,
    user_id: str = Depends(get_current_user),
) -> QueryResponse:
    return await _handle_query(body=body, user_id=user_id)
