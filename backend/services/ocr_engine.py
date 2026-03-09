"""
OCR service using Tesseract for text extraction.

PaddleOCR was the original engine but PaddlePaddle 3.x crashes on
Python 3.13 with a NotImplementedError in the oneDNN executor.
Tesseract is used as the primary (and only) OCR engine now.
"""
from pathlib import Path
import logging
from config import settings

logger = logging.getLogger(__name__)

# Maximum pixel dimension before we downscale.
# PaddleOCR had a 4000px limit; Tesseract handles large images but
# accuracy drops and memory usage spikes above ~4000px on a side.
MAX_IMAGE_SIDE = 4000


def _prepare_image(image_path: Path):
    """
    Open an image and downscale if either dimension exceeds MAX_IMAGE_SIDE.
    Returns a PIL Image ready for OCR.
    """
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size

    if max(w, h) > MAX_IMAGE_SIDE:
        scale = MAX_IMAGE_SIDE / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        logger.info(
            f"Downscaling image from {w}x{h} to {new_w}x{new_h} "
            f"(max side {MAX_IMAGE_SIDE}px)"
        )
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Convert to RGB if needed (Tesseract doesn't handle RGBA well)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    return img


def run_ocr(image_path: Path) -> str:
    """
    Extract text from an image using Tesseract OCR.

    - Downscales oversized images (>4000px) to avoid memory/accuracy issues.
    - Tries Dutch+English first, falls back to English only.

    Args:
        image_path: Path to the image file.

    Returns:
        Extracted text as a string.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        import pytesseract
    except ImportError:
        logger.error(
            "pytesseract is not installed. Install with: pip install pytesseract"
        )
        return ""

    img = _prepare_image(image_path)

    # Try Dutch+English, fall back to English only
    try:
        text = pytesseract.image_to_string(img, lang="nld+eng")
    except Exception:
        text = pytesseract.image_to_string(img, lang="eng")

    text = text.strip()

    if text:
        logger.info(
            f"Tesseract extracted {len(text)} chars from {image_path.name}"
        )
    else:
        logger.warning(f"Tesseract found no text in {image_path.name}")

    return text


def is_ocr_available() -> bool:
    """Check if Tesseract OCR is available."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
