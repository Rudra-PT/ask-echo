
from __future__ import annotations

import logging
import time
import uuid
from typing import Final

from pinecone import Pinecone, Index

from src.core.config import settings
from src.core.exceptions import IngestionError

logger = logging.getLogger(__name__)






INDEX_NAME: Final[str] = "ask-echo-gemini"



UPSERT_BATCH_SIZE: Final[int] = 100






_pinecone_client: Pinecone | None = None
_index: Index | None = None


def _get_index() -> Index:
    global _pinecone_client, _index  

    if _index is not None:
        return _index

    try:
        _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)
        _index = _pinecone_client.Index(INDEX_NAME)
        logger.info("Connected to Pinecone index '%s'.", INDEX_NAME)
    except Exception as exc:
        raise IngestionError(
            f"Failed to connect to Pinecone index '{INDEX_NAME}': {exc}"
        ) from exc

    return _index







def upsert_vectors(
    chunks: list[str],
    vectors: list[list[float]],
    namespace: str,
    metadata_extra: dict | None = None,
) -> int:
    if not chunks or not vectors:
        raise ValueError("chunks and vectors must both be non-empty.")

    if len(chunks) != len(vectors):
        raise ValueError(
            f"Mismatch: {len(chunks)} chunks but {len(vectors)} vectors. "
            "They must correspond 1-to-1."
        )

    index = _get_index()
    extra: dict = metadata_extra or {}

    
    now_ts: float = time.time()
    records = [
        {
            "id": str(uuid.uuid4()),
            "values": vector,
            "metadata": {
                "text": chunk,
                "created_at": now_ts,
                **extra,
            },
        }
        for chunk, vector in zip(chunks, vectors)
    ]

    total_upserted = 0

    
    for batch_start in range(0, len(records), UPSERT_BATCH_SIZE):
        batch = records[batch_start : batch_start + UPSERT_BATCH_SIZE]
        try:
            response = index.upsert(vectors=batch, namespace=namespace)
            upserted_count: int = getattr(response, "upserted_count", len(batch))
            total_upserted += upserted_count
            logger.debug(
                "Upserted batch %d–%d (%d vectors) into namespace '%s'.",
                batch_start,
                batch_start + len(batch) - 1,
                upserted_count,
                namespace,
            )
        except Exception as exc:
            raise IngestionError(
                f"Pinecone upsert failed at batch starting index {batch_start}: {exc}"
            ) from exc

    logger.info(
        "Upsert complete: %d vector(s) → index '%s', namespace '%s'.",
        total_upserted,
        INDEX_NAME,
        namespace,
    )
    return total_upserted


def query_index(
    vector: list[float],
    namespace: str,
    top_k: int = 5,
) -> list[dict]:
    index = _get_index()

    try:
        response = index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )
    except Exception as exc:
        raise IngestionError(
            f"Pinecone query failed in namespace '{namespace}': {exc}"
        ) from exc

    matches = []
    for match in response.matches:
        meta: dict = match.metadata or {}
        matches.append(
            {
                "id": match.id,
                "score": round(match.score, 6),
                "text": meta.get("text", ""),
                "metadata": meta,
            }
        )

    logger.debug(
        "Pinecone query returned %d match(es) from namespace '%s'.",
        len(matches),
        namespace,
    )
    return matches
