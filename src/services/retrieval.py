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

TOP_K: Final[int] = 5
GENERATION_MODEL: Final[str] = "models/gemini-2.5-flash"
DEFAULT_NAMESPACE: Final[str] = "public"

SYSTEM_PROMPT_TEMPLATE: Final[str] = """You are Ask-Echo, a precise document-grounded assistant.

RULES (follow strictly):
1. Answer ONLY using information explicitly present in the CONTEXT DOCUMENTS below.
2. If the context does not contain enough information to answer the question, respond:
   "I could not find an answer in the provided documents."
3. Do NOT use any external knowledge, make assumptions, or speculate beyond the context.
4. When you use a fact from a document, cite it inline as [Source: <filename>].
5. Be concise and factual. Do not pad your answer.

CONTEXT DOCUMENTS:
{context}
"""


def _format_context(matches: list[dict]) -> str:
    """Format Pinecone matches into a numbered context block for the prompt."""
    if not matches:
        return "No relevant context found."

    context_blocks = []
    for i, match in enumerate(matches, 1):
        metadata = match.get("metadata", {})
        filename = metadata.get("source_filename", "unknown_source")
        text = metadata.get("text", "")
        context_blocks.append(f"[{i}] [Source: {filename}]\n{text}")

    return "\n\n".join(context_blocks)


def _build_sources(matches: list[dict]) -> list[dict]:
    """Build a structured list of source citations from Pinecone matches."""
    sources = []
    for i, match in enumerate(matches, 1):
        metadata = match.get("metadata", {})
        text = metadata.get("text", "")
        sources.append(
            {
                "rank": i,
                "id": match.get("id"),
                "score": match.get("score"),
                "source_filename": metadata.get("source_filename", "unknown"),
                "mime_type": metadata.get("mime_type", "unknown"),
                "text_preview": text[:120] if text else "",
            }
        )
    return sources


def answer_query(
    query: str,
    namespace: str = DEFAULT_NAMESPACE,
    top_k: int = TOP_K,
) -> dict:
    """Run the full RAG pipeline for a user query."""
    if not query or not query.strip():
        raise ValueError("Query string cannot be empty.")

    # 1. Embed query
    try:
        query_embeddings = embed_chunks([query])
        if not query_embeddings:
            raise EmbeddingError("Failed to generate query embedding.")
        query_vector = query_embeddings[0]
    except Exception as e:
        logger.error(f"Error generating embedding for query: {e}")
        raise EmbeddingError(f"Embedding failed: {e}") from e

    # 2. Query Pinecone
    try:
        matches = query_index(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
        )
    except Exception as e:
        logger.error(f"Error querying vector index: {e}")
        raise IngestionError(f"Vector search failed: {e}") from e

    # 3. Construct prompt
    context_str = _format_context(matches)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)

    # 4. Generate answer with Gemini
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

        answer = response.text
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise RuntimeError(f"Generation error: {e}") from e

    # 5. Return payload
    sources = _build_sources(matches)
    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "namespace": namespace,
        "chunks_retrieved": len(matches),
    }
