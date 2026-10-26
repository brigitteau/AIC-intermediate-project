"""Extract page-aware text from syllabus PDFs using pdfplumber.

``parse_pdf(source)`` returns one record per non-empty page, with one-based
page numbers: ``[{"page": 1, "text": "..."}, ...]``. This format is
accepted directly by :func:`chunk.chunk_text`.
"""

from os import PathLike
from typing import BinaryIO, Union

import pdfplumber


PDFSource = Union[str, PathLike, BinaryIO]


def parse_pdf(source: PDFSource) -> list[dict[str, object]]:
    """Extract readable text from a PDF path or binary file-like object.

    Empty pages are skipped while original, one-based page numbers are kept.
    Raises ``ValueError`` for invalid input/PDFs and ``RuntimeError`` when
    pdfplumber cannot extract the document.
    """
    if not isinstance(source, (str, PathLike)) and not hasattr(source, "read"):
        raise ValueError("source must be a PDF path or a binary file-like object")

    try:
        if hasattr(source, "seek"):
            source.seek(0)
        with pdfplumber.open(source) as pdf:
            records = []
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    records.append({"page": page_number, "text": text.strip()})
            return records
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Could not read a valid PDF: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to extract text from PDF: {exc}") from exc
