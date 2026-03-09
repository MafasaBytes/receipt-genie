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


def _detect_receipt_region(img):
    """
    Detect and crop to the receipt region within a larger page/scan.

    Receipts scanned on an A4 bed or rendered from a PDF often sit in the
    centre with large empty margins.  Tesseract's full-page segmentation
    (PSM 3) is confused by all that whitespace.  This function finds the
    dense text block (the receipt) and crops to it, giving Tesseract a
    tight, receipt-shaped image to work with.

    Strategy:
      1. Skip small images — if both dimensions are under 1000px the image
         is likely already cropped or is a direct receipt photo.
      2. Grayscale → binary (Otsu) to separate ink from paper.
      3. Heavy morphological closing to merge characters → lines → one blob.
      4. Find the largest contour by area — that's the receipt.
      5. Crop to its bounding rect with margin.

    Returns the cropped PIL Image, or the original if no useful region found.
    """
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        if len(arr.shape) == 3:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = arr

        img_h, img_w = gray.shape

        # Small images are already tight — nothing to crop.
        if img_w < 1000 and img_h < 1000:
            return img

        # --- Step 1: binary threshold (Otsu handles varied exposures) ---
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )

        # --- Step 2: heavy morphological close to merge text into one blob ---
        # The kernel must bridge gaps between lines.  Receipt line-spacing at
        # 200 DPI is ~20-40px.  A vertical kernel of img_h//20 (≈100px on A4)
        # with 3 iterations comfortably bridges that.
        kw = max(img_w // 20, 20)
        kh = max(img_h // 20, 20)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)

        # --- Step 3: find the largest contour ---
        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        # Sanity: if the bounding rect already covers >85% of page, skip.
        bbox_area = w * h
        total_area = img_w * img_h
        if bbox_area >= total_area * 0.85:
            return img

        # If the detected region is tiny (<2% of page), it's noise.
        if bbox_area < total_area * 0.02:
            return img

        # --- Step 4: add margin (5% of crop dimension, min 20px) ---
        margin_x = max(int(w * 0.05), 20)
        margin_y = max(int(h * 0.05), 20)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img_w, x + w + margin_x)
        y2 = min(img_h, y + h + margin_y)

        cropped_area = (x2 - x1) * (y2 - y1)

        # Only crop if removing >10% of the page
        if cropped_area >= total_area * 0.90:
            return img

        pct_saved = 100 - (cropped_area / total_area * 100)
        logger.info(
            f"Receipt region detected: {w}x{h} in {img_w}x{img_h} page "
            f"(cropping saves {pct_saved:.0f}% area)"
        )
        return img.crop((x1, y1, x2, y2))

    except Exception as e:
        logger.warning(f"Receipt region detection failed, using full image: {e}")
        return img


def _preprocess_for_ocr(img):
    """
    Preprocess a PIL Image for better OCR accuracy on receipts.
    Applies grayscale, adaptive threshold, optional sharpening, and deskew.
    Falls back to the original image on any failure.
    """
    try:
        import cv2
        import numpy as np

        arr = np.array(img)

        # 1. Grayscale
        if len(arr.shape) == 3:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = arr

        # 2. Adaptive threshold — handles variable background on thermal paper
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, blockSize=15, C=10,
        )

        # 3. Light sharpen only if image is low-contrast (stddev < 80)
        if np.std(gray) < 80:
            kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
            thresh = cv2.filter2D(thresh, -1, kernel)
            thresh = np.clip(thresh, 0, 255).astype(np.uint8)

        # 4. Simple deskew via minAreaRect
        coords = np.column_stack(np.where(thresh < 255))
        if len(coords) > 50:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            # minAreaRect returns angles in [-90, 0); normalise
            if angle < -45:
                angle = 90 + angle
            if 0.5 <= abs(angle) <= 15:
                (h, w) = thresh.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                thresh = cv2.warpAffine(
                    thresh, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

        from PIL import Image as PILImage
        return PILImage.fromarray(thresh)

    except Exception as e:
        logger.warning(f"OCR preprocessing failed, using original image: {e}")
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
    img = _detect_receipt_region(img)
    img = _preprocess_for_ocr(img)

    # Try Dutch+English, fall back to English only
    try:
        text = pytesseract.image_to_string(img, lang="nld+eng", config="--dpi 200")
    except Exception:
        text = pytesseract.image_to_string(img, lang="eng", config="--dpi 200")

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
