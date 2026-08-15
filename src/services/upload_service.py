"""
src/services/upload_service.py
──────────────────────────────
Full RAG ingestion pipeline with page-level provenance.

Pipeline:
  1. Extract text page-by-page (pdfplumber → pypdf fallback for PDFs;
     Gemini Vision for images).
  2. Chunk each page independently with RecursiveCharacterTextSplitter
     (chunk_size=1000, chunk_overlap=150).
  3. Embed all chunks in batches via Gemini text-embedding.
  4. Upsert into Pinecone with rich per-chunk metadata:
       text, file_name, page_number, created_at (int Unix epoch).
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Final

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.exceptions import (
    CorruptDocumentError,
    EmbeddingError,
    EmptyExtractionError,
    IngestionError,
    UnsupportedMimeError,
    VisionExtractionError,
)
from src.services import embedding, vector
from src.services.document import _extract_image  # reuse existing Gemini Vision helper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_SIZE: Final[int] = 1000
CHUNK_OVERLAP: Final[int] = 150
MIN_PAGE_CHARS: Final[int] = 10  # pages with fewer chars are considered blank
ACCEPTED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)


# ---------------------------------------------------------------------------
# Internal data class
# ---------------------------------------------------------------------------

@dataclass
class _PageChunk:
    text: str
    page_number: int  # 1-indexed


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_pdf_pages(file_bytes: bytes) -> list[_PageChunk]:
    """
    Extract text page-by-page using pdfplumber.
    Falls back to pypdf (already a project dep) for pages where pdfplumber
    returns nothing (e.g. some encrypted / linearised PDFs).
    """
    page_chunks: list[_PageChunk] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                raise EmptyExtractionError("PDF has no pages.")

            # --- pdfplumber pass ---
            pdfplumber_texts: list[str | None] = []
            for page in pdf.pages:
                try:
                    pdfplumber_texts.append(page.extract_text() or "")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pdfplumber page error: %s", exc)
                    pdfplumber_texts.append(None)  # signal: needs fallback

    except EmptyExtractionError:
        raise
    except Exception as exc:
        raise CorruptDocumentError(f"pdfplumber could not open PDF: {exc}") from exc

    # --- pypdf fallback for blank/failed pages ---
    pypdf_texts: dict[int, str] = {}
    blank_indices = [i for i, t in enumerate(pdfplumber_texts) if not t]
    if blank_indices:
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfStreamError

            reader = PdfReader(io.BytesIO(file_bytes), strict=False)
            for i in blank_indices:
                if i < len(reader.pages):
                    try:
                        pypdf_texts[i] = reader.pages[i].extract_text() or ""
                    except PdfStreamError as exc:
                        logger.warning("pypdf fallback page %d error: %s", i + 1, exc)
                        pypdf_texts[i] = ""
        except Exception as exc:
            logger.warning("pypdf fallback init failed: %s", exc)

    # --- merge results ---
    for page_idx, plumber_text in enumerate(pdfplumber_texts):
        text = (plumber_text or pypdf_texts.get(page_idx, "")).strip()
        if len(text) >= MIN_PAGE_CHARS:
            page_chunks.append(_PageChunk(text=text, page_number=page_idx + 1))
        else:
            logger.debug("Page %d yielded no usable text — skipped.", page_idx + 1)

    if not page_chunks:
        raise EmptyExtractionError(
            "No extractable text found in this PDF. "
            "If it is a scanned document, re-upload as JPEG/PNG."
        )

    return page_chunks


def _extract_image_as_page(file_bytes: bytes, mime_type: str) -> list[_PageChunk]:
    """Wrap Gemini Vision result as a single page."""
    raw_text = _extract_image(file_bytes, mime_type)  # raises on failure
    return [_PageChunk(text=raw_text, page_number=1)]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_pages(pages: list[_PageChunk]) -> list[_PageChunk]:
    """
    Split each page's text with RecursiveCharacterTextSplitter.
    Each resulting sub-chunk inherits the originating page's page_number.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    result: list[_PageChunk] = []
    for page in pages:
        sub_chunks = splitter.split_text(page.text)
        for sub in sub_chunks:
            sub = sub.strip()
            if sub:
                result.append(_PageChunk(text=sub, page_number=page.page_number))

    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ingest_document(
    file_bytes: bytes,
    mime_type: str,
    file_name: str,
    namespace: str,
) -> int:
    """
    Full ingestion pipeline.

    Returns the number of vectors upserted into Pinecone.
    Raises domain exceptions on failure (caught by the API layer).
    """
    if not file_bytes:
        raise CorruptDocumentError("Uploaded file is empty (zero bytes).")

    if mime_type not in ACCEPTED_MIME_TYPES:
        raise UnsupportedMimeError(
            f"MIME type '{mime_type}' is not supported. "
            f"Accepted: {', '.join(sorted(ACCEPTED_MIME_TYPES))}"
        )

    # 1. Extract text (page-by-page)
    if mime_type == "application/pdf":
        pages = _extract_pdf_pages(file_bytes)
    else:
        pages = _extract_image_as_page(file_bytes, mime_type)

    logger.info(
        "Extracted %d non-blank page(s) from '%s'.", len(pages), file_name
    )

    # 2. Chunk each page independently
    chunks: list[_PageChunk] = _chunk_pages(pages)

    if not chunks:
        raise EmptyExtractionError("Document produced no usable text chunks after splitting.")

    logger.info("Produced %d chunk(s) from '%s'.", len(chunks), file_name)

    # 3. Embed all chunk texts in batches
    chunk_texts = [c.text for c in chunks]
    try:
        vectors_list = embedding.embed_chunks_batched(chunk_texts)
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(f"Unexpected embedding error: {exc}") from exc

    # 4. Build per-chunk Pinecone records with full metadata
    now_ts: int = int(time.time())
    records = [
        {
            "text": chunk.text,
            "file_name": file_name,
            "page_number": chunk.page_number,
            "created_at": now_ts,
            # internal fields used by query retrieval
            "source_filename": file_name,
            "mime_type": mime_type,
        }
        for chunk in chunks
    ]

    # 5. Upsert into Pinecone
    try:
        upserted = vector.upsert_records(
            chunk_texts=chunk_texts,
            vectors=vectors_list,
            metadata_list=records,
            namespace=namespace,
        )
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Unexpected upsert error: {exc}") from exc

    logger.info(
        "Upserted %d vector(s) for '%s' into namespace '%s'.",
        upserted,
        file_name,
        namespace,
    )
    return upserted
