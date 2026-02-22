"""
PDF text extraction using langchain-community's PyPDFLoader.

Extracts text per page. For scanned PDFs with little/no selectable text,
signals that the page needs OCR fallback.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH_FOR_EXTRACTION = 40


def extract_text_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extract text from each page of a PDF using langchain PyPDFLoader.

    Returns a list of dicts, one per page:
        {
            "page_number": int (1-based),
            "text": str,
            "has_text": bool (True if enough text for LLM extraction),
        }
    """
    from langchain_community.document_loaders import PyPDFLoader

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    loader = PyPDFLoader(str(pdf_path))
    documents = loader.load()

    pages: List[Dict[str, Any]] = []
    for doc in documents:
        page_num = doc.metadata.get("page", len(pages)) + 1
        text = (doc.page_content or "").strip()
        pages.append({
            "page_number": page_num,
            "text": text,
            "has_text": len(text) >= MIN_TEXT_LENGTH_FOR_EXTRACTION,
        })

    logger.info(
        f"Extracted text from {len(pages)} page(s) of {pdf_path.name} "
        f"({sum(1 for p in pages if p['has_text'])} with sufficient text)"
    )
    return pages


def extract_text_from_pdf_safe(pdf_path: Path) -> Optional[List[Dict[str, Any]]]:
    """Same as extract_text_from_pdf but returns None on failure."""
    try:
        return extract_text_from_pdf(pdf_path)
    except Exception as e:
        logger.warning(f"langchain PDF text extraction failed: {e}")
        return None
