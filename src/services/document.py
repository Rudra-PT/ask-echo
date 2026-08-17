"""
src/services/document.py
────────────────────────
Document extraction and chunking utilities.
"""

from __future__ import annotations

import io
import logging
from typing import Final

from google import genai
from google.genai import types as genai_types
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from src.core.config import settings
from src.core.exceptions import (
    CorruptDocumentError,
    EmptyExtractionError,
    UnsupportedMimeError,
    VisionExtractionError,
)

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)

MIN_PDF_CHARS: Final[int] = 50
VISION_MODEL: Final[str] = "models/gemini-flash-latest"

LEGIBILITY_FAILURE_PHRASES: Final[tuple[str, ...]] = (
    "no text",
    "cannot read",
    "unable to read",
    "illegible",
    "blurry",
    "cannot determine",
    "no visible text",
    "i cannot",
    "no readable text",
    "no written",
)

CHUNK_SIZE: Final[int] = 1000
CHUNK_OVERLAP: Final[int] = 200


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract full raw text from a PDF document using pypdf."""
    stream = io.BytesIO(file_bytes)

    try:
        reader = PdfReader(stream, strict=False)
    except PdfReadError as exc:
        raise CorruptDocumentError(
            f"PDF structure is corrupt and cannot be parsed: {exc}"
        ) from exc
    except Exception as exc:
        raise CorruptDocumentError(f"Failed to open file as a PDF: {exc}") from exc

    extracted_parts: list[str] = []
    for page_index, page in enumerate(reader.pages):
        try:
            page_text: str | None = page.extract_text()
            if page_text:
                extracted_parts.append(page_text)
        except PdfStreamError as exc:
            logger.warning("Skipping page %d due to stream error: %s", page_index, exc)
        except Exception as exc:
            logger.warning("Unexpected error on page %d, skipping: %s", page_index, exc)

    full_text = "\n".join(extracted_parts).strip()

    if len(full_text) < MIN_PDF_CHARS:
        raise EmptyExtractionError(
            "The PDF contains no extractable text. "
            "If it is a scanned document, re-upload it as an image (JPEG/PNG)."
        )

    return full_text


def _extract_image(file_bytes: bytes, mime_type: str) -> str:
    """Extract text from an image using Gemini Vision OCR."""
    if not file_bytes:
        raise CorruptDocumentError("Image file is empty (zero bytes).")

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    image_part = genai_types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )

    prompt = (
        "Extract and transcribe every piece of text visible in this image. "
        "Return only the raw text, preserving line breaks where meaningful. "
        "If there is no readable text in the image, respond with exactly: "
        "'No readable text found.'"
    )

    try:
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[prompt, image_part],
        )
    except Exception as exc:
        raise VisionExtractionError(f"Gemini Vision API call failed: {exc}") from exc

    response_text: str | None = getattr(response, "text", None)
    if not response_text or not response_text.strip():
        raise EmptyExtractionError(
            "No text was detected in the image. "
            "The image may be blank or the model returned no output."
        )

    if any(phrase in response_text.lower() for phrase in LEGIBILITY_FAILURE_PHRASES):
        raise EmptyExtractionError(
            "The image appears to contain no legible text. "
            "Try uploading a higher-resolution scan."
        )

    return response_text.strip()


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    """Route document bytes to the appropriate extractor based on MIME type."""
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise UnsupportedMimeError(
            f"MIME type '{mime_type}' is not supported. "
            f"Accepted types: {', '.join(sorted(SUPPORTED_MIME_TYPES))}"
        )

    if mime_type == "application/pdf":
        return _extract_pdf(file_bytes)

    return _extract_image(file_bytes, mime_type)


def chunk_text(text: str) -> list[str]:
    """Split raw text into overlapping chunks."""
    if not text or not text.strip():
        raise EmptyExtractionError("Cannot chunk empty text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[str] = splitter.split_text(text)
    return [c.strip() for c in chunks if c.strip()]


def process_document(file_bytes: bytes, mime_type: str) -> list[str]:
    """Extract and chunk document content in one step."""
    raw_text = extract_text(file_bytes, mime_type)
    return chunk_text(raw_text)
