"""
src/services/retrieval.py
─────────────────────────
RAG query pipeline.

Steps:
  1. Embed the user query with Gemini text-embedding.
  2. Query Pinecone (include_metadata=True) in the requested namespace.
  3. Format context blocks with SOURCE / Page headers.
  4. Generate a grounded answer with gemini-flash-latest, instructing
     inline citations as [Source: filename.pdf, Page X].
  5. Return {"answer": str, "sources": list[dict]}.
"""

from __future__ import annotations

import logging
from typing import Final

from google import genai
from google.genai import types as genai_types

from src.core.config import settings
from src.core.exceptions import EmbeddingError, IngestionError
from src.services.embedding import embed_chunks
from src.services.vector import query_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOP_K: Final[int] = 5
GENERATION_MODEL: Final[str] = "models/gemini-flash-latest"
DEFAULT_NAMESPACE: Final[str] = "public"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE: Final[str] = """\
You are Ask-Echo, a precise document-grounded assistant.

STRICT RULES — follow every rule without exception:
1. Answer ONLY using information explicitly present in the CONTEXT DOCUMENTS below.
2. For every key fact you state, cite its source inline using this exact format:
   [Source: <filename>, Page <page_number>]
   Example: "The report found a 12 % growth rate [Source: annual_report.pdf, Page 4]."
3. If the context does not contain enough information to fully answer the question,
   respond with exactly:
   "I couldn't find information about that in your uploaded documents."
   Do NOT guess, speculate, or use external knowledge under any circumstances.
4. Be concise and factual. Do not pad, repeat, or summarise beyond what is asked.
5. If multiple sources support the same fact, cite all of them.

CONTEXT DOCUMENTS:
{context}
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_context(matches: list[dict]) -> str:
    """
    Format Pinecone matches into numbered context blocks for the system prompt.

    Each block uses the header:
        --- SOURCE: {file_name} | Page {page_number} ---
    so the model can produce precise inline citations.
    """
    if not matches:
        return "No relevant context found."

    blocks: list[str] = []
    for i, match in enumerate(matches, 1):
        meta = match.get("metadata", {})

        # Support both new metadata keys (file_name / page_number set by
        # upload_service) and legacy keys (source_filename) for backward compat.
        file_name = (
            meta.get("file_name")
            or meta.get("source_filename")
            or "unknown_source"
        )
        page_number = meta.get("page_number", "?")
        text = meta.get("text", "").strip()

        header = f"--- SOURCE: {file_name} | Page {page_number} ---"
        blocks.append(f"[{i}] {header}\n{text}")

    return "\n\n".join(blocks)


def _build_sources(matches: list[dict]) -> list[dict]:
    """
    Build the structured sources list returned in the API response.

    Each entry contains the full metadata dict enriched with rank and score,
    so the frontend can render file name, page number, preview, etc.
    """
    sources: list[dict] = []
    for i, match in enumerate(matches, 1):
        meta = match.get("metadata", {})
        text = meta.get("text", "")

        sources.append(
            {
                # Ranking / retrieval info
                "rank": i,
                "id": match.get("id", ""),
                "score": match.get("score", 0.0),
                # New metadata fields (set by upload_service)
                "file_name": meta.get("file_name") or meta.get("source_filename", "unknown"),
                "page_number": meta.get("page_number", None),
                # Legacy / supplementary fields
                "source_filename": meta.get("source_filename", "unknown"),
                "mime_type": meta.get("mime_type", "unknown"),
                "created_at": meta.get("created_at", None),
                # Text preview for UI display
                "text_preview": text[:200] if text else "",
            }
        )
    return sources


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def answer_query(
    query: str,
    namespace: str = DEFAULT_NAMESPACE,
    top_k: int = TOP_K,
) -> dict:
    """
    Full RAG pipeline: embed → retrieve → generate → return.

    Returns:
        {
            "answer":          str,
            "sources":         list[dict],   # one entry per retrieved chunk
            "query":           str,
            "namespace":       str,
            "chunks_retrieved": int,
        }
    """
    if not query or not query.strip():
        raise ValueError("Query string cannot be empty.")

    # 1. Embed the query
    try:
        query_embeddings = embed_chunks([query])
        if not query_embeddings:
            raise EmbeddingError("Embedding API returned an empty list for the query.")
        query_vector = query_embeddings[0]
    except EmbeddingError:
        raise
    except Exception as exc:
        logger.error("Unexpected error generating query embedding: %s", exc)
        raise EmbeddingError(f"Embedding failed: {exc}") from exc

    # 2. Query Pinecone (include_metadata=True handled inside query_index)
    try:
        matches = query_index(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
        )
    except IngestionError:
        raise
    except Exception as exc:
        logger.error("Unexpected error querying vector index: %s", exc)
        raise IngestionError(f"Vector search failed: {exc}") from exc

    logger.info(
        "Retrieved %d match(es) from namespace '%s' for query: %r",
        len(matches),
        namespace,
        query[:80],
    )

    # 3. Format context with SOURCE / Page headers
    context_str = _format_context(matches)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)

    # 4. Generate grounded answer with Gemini
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=query,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        answer: str = response.text.strip()

    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        raise RuntimeError(f"Generation error: {exc}") from exc

    # 5. Build and return full payload
    sources = _build_sources(matches)
    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "namespace": namespace,
        "chunks_retrieved": len(matches),
    }
