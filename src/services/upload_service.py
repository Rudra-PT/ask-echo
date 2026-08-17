"""
src/services/upload_service.py
──────────────────────────────
Full RAG ingestion pipeline with page-level provenance.
"""

from __future__ import annotations

import io
import logging
import re
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
from src.services.document import _extract_image

logger = logging.getLogger(__name__)

CHUNK_SIZE: Final[int] = 1000
CHUNK_OVERLAP: Final[int] = 150
MIN_PAGE_CHARS: Final[int] = 10
ACCEPTED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)


@dataclass
class _PageChunk:
    text: str
    page_number: int  # 1-indexed


def _clean_text(text: str) -> str:
    """Normalize whitespace and fix common PDF line-break artifacts."""
    # Fix hyphenated words broken across lines (e.g. "docu-\nment" -> "document")
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    # Collapse multiple blank lines to a double newline
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_pages(file_bytes: bytes) -> list[_PageChunk]:
    """Extract text page-by-page using pdfplumber with pypdf fallback."""
    page_chunks: list[_PageChunk] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                raise EmptyExtractionError("PDF has no pages.")

            pdfplumber_texts: list[str | None] = []
            for page in pdf.pages:
                try:
                    pdfplumber_texts.append(page.extract_text() or "")
                except Exception as exc:
                    logger.warning("pdfplumber page extraction error: %s", exc)
                    pdfplumber_texts.append(None)

    except EmptyExtractionError:
        raise
    except Exception as exc:
        raise CorruptDocumentError(f"pdfplumber could not open PDF: {exc}") from exc

    # pypdf fallback for blank or failed pages
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

    # Merge extracted text and filter empty pages
    for page_idx, plumber_text in enumerate(pdfplumber_texts):
        raw_text = plumber_text or pypdf_texts.get(page_idx, "")
        cleaned = _clean_text(raw_text)
        if len(cleaned) >= MIN_PAGE_CHARS:
            page_chunks.append(_PageChunk(text=cleaned, page_number=page_idx + 1))
        else:
            logger.debug("Page %d yielded no usable text — skipped.", page_idx + 1)

    if not page_chunks:
        raise EmptyExtractionError(
            "No extractable text found in this PDF. "
            "If it is a scanned document, re-upload as JPEG/PNG."
        )

    return page_chunks


def _extract_image_as_page(file_bytes: bytes, mime_type: str) -> list[_PageChunk]:
    """Wrap Gemini Vision OCR result as a single page."""
    raw_text = _extract_image(file_bytes, mime_type)
    cleaned = _clean_text(raw_text)
    return [_PageChunk(text=cleaned, page_number=1)]


def _chunk_pages(pages: list[_PageChunk]) -> list[_PageChunk]:
    """Split each page's text while preserving its originating page number."""
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
            cleaned_sub = sub.strip()
            if cleaned_sub:
                result.append(_PageChunk(text=cleaned_sub, page_number=page.page_number))

    return result


def ingest_document(
    file_bytes: bytes,
    mime_type: str,
    file_name: str,
    namespace: str,
) -> int:
    """Full RAG document ingestion pipeline."""
    if not file_bytes:
        raise CorruptDocumentError("Uploaded file is empty (zero bytes).")

    if mime_type not in ACCEPTED_MIME_TYPES:
        raise UnsupportedMimeError(
            f"MIME type '{mime_type}' is not supported. "
            f"Accepted: {', '.join(sorted(ACCEPTED_MIME_TYPES))}"
        )

    # 1. Extract text
    if mime_type == "application/pdf":
        pages = _extract_pdf_pages(file_bytes)
    else:
        pages = _extract_image_as_page(file_bytes, mime_type)

    logger.info("Extracted %d non-blank page(s) from '%s'.", len(pages), file_name)

    # 2. Chunk text
    chunks: list[_PageChunk] = _chunk_pages(pages)
    if not chunks:
        raise EmptyExtractionError("Document produced no usable text chunks after splitting.")

    logger.info("Produced %d chunk(s) from '%s'.", len(chunks), file_name)

    # 3. Embed chunks in batches
    chunk_texts = [c.text for c in chunks]
    try:
        vectors_list = embedding.embed_chunks_batched(chunk_texts)
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(f"Unexpected embedding error: {exc}") from exc

    # 4. Prepare metadata for Pinecone index
    now_ts: int = int(time.time())
    total_chunks = len(chunks)
    records = [
        {
            "text": chunk.text,
            "file_name": file_name,
            "page_number": chunk.page_number,
            "chunk_index": idx,
            "total_chunks": total_chunks,
            "created_at": now_ts,
            "source_filename": file_name,
            "mime_type": mime_type,
        }
        for idx, chunk in enumerate(chunks, 1)
    ]

    # 5. Upsert into Pinecone index
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
