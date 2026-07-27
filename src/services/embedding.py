
from __future__ import annotations

import logging
from typing import Final

from google import genai

from src.core.config import settings
from src.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)






EMBEDDING_MODEL: Final[str] = "gemini-embedding-001"



OUTPUT_DIMENSIONALITY: Final[int] = 768


EXPECTED_DIMENSIONS: Final[int] = OUTPUT_DIMENSIONALITY


MAX_BATCH_SIZE: Final[int] = 100







def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.GOOGLE_API_KEY)


def _validate_vector(vector: list[float], chunk_index: int) -> None:
    if len(vector) != EXPECTED_DIMENSIONS:
        raise EmbeddingError(
            f"Chunk {chunk_index}: expected {EXPECTED_DIMENSIONS}-dimensional "
            f"embedding but received {len(vector)} dimensions. "
            "Check that the model has not changed its output format."
        )







def embed_chunks(chunks: list[str]) -> list[list[float]]:
    if not chunks:
        raise ValueError("No chunks to embed: the input list is empty.")

    if len(chunks) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch too large: received {len(chunks)} chunks but the maximum "
            f"per call is {MAX_BATCH_SIZE}. Split your input into smaller batches."
        )

    client = _get_client()

    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=chunks,
            config={"output_dimensionality": OUTPUT_DIMENSIONALITY},
        )
    except Exception as exc:
        raise EmbeddingError(
            f"Gemini embedding API call failed: {exc}"
        ) from exc

    
    if not result.embeddings:
        raise EmbeddingError(
            "The Gemini API returned an empty embeddings list. "
            "This may indicate a quota issue or an API-side error."
        )

    vectors: list[list[float]] = []

    for i, embedding in enumerate(result.embeddings):
        vector: list[float] = list(embedding.values)
        _validate_vector(vector, chunk_index=i)
        vectors.append(vector)

    logger.debug(
        "Embedded %d chunk(s) → %d-dimensional vectors via %s (truncated from 3072)",
        len(chunks),
        EXPECTED_DIMENSIONS,
        EMBEDDING_MODEL,
    )

    return vectors


def embed_chunks_batched(
    chunks: list[str],
    batch_size: int = MAX_BATCH_SIZE,
) -> list[list[float]]:
    if not chunks:
        raise ValueError("No chunks to embed: the input list is empty.")

    if batch_size <= 0:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size}.")

    all_vectors: list[list[float]] = []

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        logger.debug(
            "Embedding batch %d–%d of %d chunks",
            batch_start,
            batch_start + len(batch) - 1,
            len(chunks),
        )
        batch_vectors = embed_chunks(batch)
        all_vectors.extend(batch_vectors)

    return all_vectors
