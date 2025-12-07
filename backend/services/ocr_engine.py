"""
OCR service using PaddleOCR for text extraction.
"""
from pathlib import Path
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

# Global OCR engine instance (lazy loaded)
_ocr_engine = None


def initialize_ocr_engine():
    """
    Initialize PaddleOCR engine (lazy loading).
    
    Returns:
        PaddleOCR instance or None if not available
    """
    global _ocr_engine
    
    if _ocr_engine is not None:
        return _ocr_engine
    
    try:
        from paddleocr import PaddleOCR
        logger.info("Initializing PaddleOCR...")
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang=settings.OCR_LANG
            # Note: show_log parameter may not be available in all versions
        )
        logger.info("PaddleOCR initialized successfully")
        return _ocr_engine
    except ImportError:
        logger.warning("PaddleOCR not installed. Install with: pip install paddlepaddle paddleocr")
        return None
    except Exception as e:
        logger.error(f"Error initializing PaddleOCR: {str(e)}")
        return None


def run_ocr(image_path: Path) -> str:
    """
    Extract text from an image using OCR.
    
    Tries PaddleOCR first, falls back to pytesseract if available,
    otherwise returns placeholder text.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text as a string
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Try PaddleOCR first
    ocr_engine = initialize_ocr_engine()
    if ocr_engine is not None:
        try:
            logger.info(f"Running PaddleOCR on: {image_path}")
            # Note: cls parameter not supported in this version
            result = ocr_engine.ocr(str(image_path))
            
            # Debug: Log the raw result structure
            logger.info(f"PaddleOCR raw result type: {type(result)}")
            if result:
                logger.info(f"PaddleOCR result length: {len(result)}")
                if len(result) > 0:
                    logger.info(f"PaddleOCR result[0] type: {type(result[0])}")
                    if isinstance(result[0], dict):
                        logger.info(f"PaddleOCR result[0] keys: {list(result[0].keys())[:10]}")
                    logger.info(f"PaddleOCR result[0] content preview: {str(result[0])[:500]}")
            
            # Debug: Log the raw result structure
            logger.debug(f"PaddleOCR raw result type: {type(result)}")
            if result:
                logger.debug(f"PaddleOCR result length: {len(result)}")
                if len(result) > 0:
                    logger.debug(f"PaddleOCR result[0] type: {type(result[0])}")
                    logger.debug(f"PaddleOCR result[0] content (first 500 chars): {str(result[0])[:500]}")
            
            if result and len(result) > 0:
                # PaddleOCR can return different formats depending on version
                # Handle both new format (OCRResult dict) and old format (list of tuples)
                
                extracted_text = None
                
                # Check if result[0] is a dict (new format) or list (old format)
                first_result = result[0]
                
                if isinstance(first_result, dict):
                    # New format: OCRResult object (dict-like)
                    ocr_result = first_result
                    
                    # Method 1: Extract from rec_texts field (preferred for new format)
                    rec_texts = ocr_result.get('rec_texts', [])
                    if rec_texts and isinstance(rec_texts, list):
                        extracted_text = '\n'.join(str(text) for text in rec_texts if text)
                        logger.debug(f"PaddleOCR extracted {len(rec_texts)} text segments from rec_texts, {len(extracted_text)} characters")
                    
                    # Method 2: Try other text fields
                    if not extracted_text or not extracted_text.strip():
                        for key in ['text', 'ocr_text', 'detected_text', 'lines']:
                            if key in ocr_result:
                                value = ocr_result[key]
                                if isinstance(value, list):
                                    extracted_text = '\n'.join(str(v) for v in value if v)
                                elif isinstance(value, str):
                                    extracted_text = value
                                if extracted_text and extracted_text.strip():
                                    logger.debug(f"PaddleOCR extracted text from {key} field")
                                    break
                
                elif isinstance(first_result, (list, tuple)):
                    # Old format: list of [bbox, (text, confidence)] tuples
                    text_lines = []
                    for item in first_result:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            # item[0] is bbox, item[1] is (text, confidence)
                            text_info = item[1]
                            if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                text_lines.append(str(text_info[0]))
                            elif isinstance(text_info, str):
                                text_lines.append(text_info)
                    if text_lines:
                        extracted_text = '\n'.join(text_lines)
                        logger.debug(f"PaddleOCR extracted {len(text_lines)} text lines from old format")
                
                # Also check if result itself is a list of lists (nested structure)
                if not extracted_text or not extracted_text.strip():
                    text_lines = []
                    for page_result in result:
                        if isinstance(page_result, list):
                            for item in page_result:
                                if isinstance(item, (list, tuple)) and len(item) >= 2:
                                    text_info = item[1]
                                    if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                        text_lines.append(str(text_info[0]))
                                    elif isinstance(text_info, str):
                                        text_lines.append(text_info)
                    if text_lines:
                        extracted_text = '\n'.join(text_lines)
                        logger.debug(f"PaddleOCR extracted {len(text_lines)} text lines from nested format")
                
                if extracted_text and extracted_text.strip():
                    logger.info(f"PaddleOCR successfully extracted {len(extracted_text)} characters")
                    return extracted_text.strip()
                else:
                    logger.warning("PaddleOCR returned empty or no text")
                    # Additional debugging: try to inspect result structure
                    if result and len(result) > 0:
                        logger.debug(f"Result structure details: {type(result[0])}, keys: {result[0].keys() if isinstance(result[0], dict) else 'N/A'}")
                        logger.debug(f"Full result (first 1000 chars): {str(result)[:1000]}")
            else:
                logger.warning("PaddleOCR returned no results")
                if result is None:
                    logger.debug("PaddleOCR result is None")
                elif len(result) == 0:
                    logger.debug("PaddleOCR result is empty list")
                
        except Exception as e:
            logger.error(f"PaddleOCR error: {str(e)}")
            logger.exception("PaddleOCR exception details")
    
    # Fallback to pytesseract if available
    try:
        import pytesseract
        from PIL import Image
        logger.debug(f"Falling back to pytesseract for: {image_path}")
        img = Image.open(image_path)
        # Try Dutch+English, fallback to English only if Dutch not available
        try:
            text = pytesseract.image_to_string(img, lang='nld+eng')
        except Exception:
            # If Dutch language pack not available, use English only
            text = pytesseract.image_to_string(img, lang='eng')
        if text.strip():
            logger.debug(f"pytesseract extracted {len(text)} characters")
            return text.strip()
    except ImportError:
        # pytesseract not installed - this is optional, only log at debug level
        logger.debug("pytesseract not available (optional dependency)")
    except Exception as e:
        # Check if it's a "not installed" error vs other error
        error_str = str(e).lower()
        if 'tesseract' in error_str and ('not installed' in error_str or 'not found' in error_str):
            logger.debug(f"pytesseract/tesseract not installed: {str(e)}")
        else:
            logger.warning(f"pytesseract error: {str(e)}")
    
    # Final fallback: return placeholder with image info
    logger.warning(f"Using placeholder OCR text for: {image_path.name}")
    logger.warning("PaddleOCR found no text in image. This may indicate:")
    logger.warning("  - Image is too small or low quality")
    logger.warning("  - Image contains no readable text")
    logger.warning("  - Image needs preprocessing (contrast, brightness)")
    placeholder = f"""
    RECEIPT TEXT NOT EXTRACTED
    Image: {image_path.name}
    PaddleOCR detected no text in this image.
    This may be due to image quality, size, or lack of readable text.
    Note: Tesseract OCR binary is not installed (pytesseract package is installed but needs Tesseract executable).
    """
    return placeholder.strip()


def is_ocr_available() -> bool:
    """
    Check if OCR is available (PaddleOCR or pytesseract).
    
    Returns:
        True if OCR is available, False otherwise
    """
    ocr_engine = initialize_ocr_engine()
    if ocr_engine is not None:
        return True
    
    try:
        import pytesseract
        return True
    except ImportError:
        return False

