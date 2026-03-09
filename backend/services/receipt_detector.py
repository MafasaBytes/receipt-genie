"""
Receipt detection service.

Legacy module — contour-based multi-receipt detection has been removed.
The agreement is one receipt per page, so the pipeline now OCRs the full
page image directly without cropping.

detect_receipts() is kept as a thin fallback that simply returns the
original image path, in case any external code still calls it.
"""
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


def detect_receipts(image_path: Path) -> List[str]:
    """
    Return the image as-is (single receipt per page).

    Previously this ran contour detection, morphology, slicing, etc.
    That logic has been removed because:
      - The client agreement is one receipt per page.
      - The old multi-receipt contour pipeline fragmented single receipts
        into tiny blobs that were rejected, causing fallback to the
        original image anyway.

    Args:
        image_path: Path to the page image.

    Returns:
        [str(image_path)]  — the unchanged page.
    """
    logger.info(f"Single-receipt mode: returning full page image {image_path}")
    return [str(image_path)]
