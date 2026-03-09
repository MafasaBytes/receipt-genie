"""
PDF processing utilities using pypdfium2.
"""
from pathlib import Path
from typing import List
import pypdfium2 as pdfium
from PIL import Image
import io
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def crop_to_content(pil_image: Image.Image, margin_px: int = 20) -> Image.Image:
    """
    Crop whitespace around receipt content in a PDF-rendered image.

    Only crops if removing at least 10% of the image area so that
    already-tight images are left untouched.
    """
    img_array = np.array(pil_image)

    # Sample border pixels to detect background colour (median of edges)
    top = img_array[0, :]
    bottom = img_array[-1, :]
    left = img_array[:, 0]
    right = img_array[:, -1]
    border_pixels = np.concatenate([top, bottom, left, right], axis=0)
    bg_color = np.median(border_pixels, axis=0).astype(np.uint8)

    # Mask of pixels that differ from background by more than threshold
    diff = np.abs(img_array.astype(np.int16) - bg_color.astype(np.int16))
    if diff.ndim == 3:
        diff = diff.max(axis=2)  # max channel difference
    mask = (diff > 30).astype(np.uint8) * 255

    coords = cv2.findNonZero(mask)
    if coords is None:
        # Entire image is background – return as-is
        return pil_image

    x, y, w, h = cv2.boundingRect(coords)

    # Add margin, clamped to image bounds
    img_h, img_w = img_array.shape[:2]
    x1 = max(0, x - margin_px)
    y1 = max(0, y - margin_px)
    x2 = min(img_w, x + w + margin_px)
    y2 = min(img_h, y + h + margin_px)

    # Only crop if removing at least 10% of area
    content_area = (x2 - x1) * (y2 - y1)
    total_area = img_w * img_h
    if content_area >= total_area * 0.9:
        return pil_image

    logger.debug(
        f"Cropping PDF image from {img_w}x{img_h} to {x2-x1}x{y2-y1} "
        f"(saved {100 - content_area / total_area * 100:.0f}% area)"
    )
    return pil_image.crop((x1, y1, x2, y2))


def pdf_to_images(pdf_path: Path, output_dir: Path) -> List[Path]:
    """
    Convert PDF pages to images.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save images
        
    Returns:
        List of paths to generated images
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    
    try:
        # Open PDF
        pdf = pdfium.PdfDocument(str(pdf_path))
        
        # Convert each page to image
        for page_num in range(len(pdf)):
            page = pdf.get_page(page_num)
            
            # Render page to image (200 DPI — good balance of quality vs size)
            bitmap = page.render(scale=200/72)  # 72 is default DPI
            pil_image = bitmap.to_pil()
            pil_image = crop_to_content(pil_image)

            # Save image
            image_filename = f"{pdf_path.stem}_page_{page_num + 1}.png"
            image_path = output_dir / image_filename
            pil_image.save(image_path, "PNG")
            image_paths.append(image_path)
            
            # Clean up
            bitmap.close()
            page.close()
        
        pdf.close()
        
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}")
    
    return image_paths


def get_pdf_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        count = len(pdf)
        pdf.close()
        return count
    except Exception:
        return 0

