
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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
        examples=["What does this document say about the ingestion pipeline?"],
    )
    namespace: str = Field(
        default="public",
        description="Pinecone namespace to search (default: 'public').",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve (1–20, default: 5).",
    )


class SourceCitation(BaseModel):

    rank: int = Field(description="Retrieval rank (1 = most relevant).")
    id: str = Field(description="Pinecone record UUID.")
    score: float = Field(description="Cosine similarity score (0–1).")
    source_filename: str = Field(description="Original filename of the ingested document.")
    mime_type: str = Field(description="MIME type of the source document.")
    text_preview: str = Field(description="First 120 characters of the matched chunk.")


class QueryResponse(BaseModel):

    query: str = Field(description="Echo of the original query.")
    answer: str = Field(description="Gemini's grounded answer, citing sources inline.")
    sources: list[SourceCitation] = Field(
        description="Ranked list of document chunks used to generate the answer."
    )
    namespace: str = Field(description="Pinecone namespace that was searched.")
    chunks_retrieved: int = Field(description="Number of chunks retrieved from Pinecone.")







@router.post(
    "/",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the document store and get a grounded answer",
    description=(
        "Embeds the query using gemini-embedding-001 (768-dim), retrieves the "
        "top-K most relevant chunks from Pinecone, and asks Gemini 2.5 Flash "
        "to answer strictly from the retrieved context. Returns the answer and "
        "full source metadata for every cited chunk."
    ),
)
async def query_documents(body: QueryRequest) -> QueryResponse:
    logger.info(
        "Query request: query=%r  namespace=%r  top_k=%d",
        body.query,
        body.namespace,
        body.top_k,
    )

    try:
        result = retrieval.answer_query(
            query=body.query,
            namespace=body.namespace,
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

    return QueryResponse(**result)
