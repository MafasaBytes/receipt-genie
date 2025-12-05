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
            logger.debug(f"Running PaddleOCR on: {image_path}")
            # Note: cls parameter not supported in this version
            result = ocr_engine.ocr(str(image_path))
            
            if result and len(result) > 0 and result[0]:
                # PaddleOCR 3.x returns OCRResult objects (dict-like)
                ocr_result = result[0]
                
                # Try multiple methods to extract text
                extracted_text = None
                
                # Method 1: Extract from rec_texts field (preferred)
                rec_texts = ocr_result.get('rec_texts', [])
                if rec_texts and isinstance(rec_texts, list):
                    extracted_text = '\n'.join(str(text) for text in rec_texts if text)
                    logger.debug(f"PaddleOCR extracted {len(rec_texts)} text segments from rec_texts, {len(extracted_text)} characters")
                
                # Method 2: Try to extract from dt_polys or other fields if rec_texts is missing
                if not extracted_text or not extracted_text.strip():
                    # Check if result has a different structure (older PaddleOCR versions)
                    if isinstance(ocr_result, (list, tuple)):
                        # Old format: list of [bbox, (text, confidence)]
                        text_lines = []
                        for item in ocr_result:
                            if isinstance(item, (list, tuple)) and len(item) >= 2:
                                text_info = item[1]
                                if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                    text_lines.append(str(text_info[0]))
                        if text_lines:
                            extracted_text = '\n'.join(text_lines)
                            logger.debug(f"PaddleOCR extracted {len(text_lines)} text lines from old format")
                    
                    # Method 3: Try to get text from any text-related fields
                    if not extracted_text or not extracted_text.strip():
                        # Check for other possible text fields
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
                
                if extracted_text and extracted_text.strip():
                    return extracted_text.strip()
                else:
                    logger.warning("PaddleOCR returned empty or no text")
            else:
                logger.warning("PaddleOCR returned no results")
                
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
    placeholder = f"""
    RECEIPT TEXT NOT EXTRACTED
    Image: {image_path.name}
    Note: Install PaddleOCR or pytesseract for real OCR
    Install: pip install paddlepaddle paddleocr
    Or: pip install pytesseract
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

