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
                
                # Extract text from rec_texts field
                rec_texts = ocr_result.get('rec_texts', [])
                if rec_texts and isinstance(rec_texts, list):
                    # Join all recognized text lines
                    extracted_text = '\n'.join(str(text) for text in rec_texts if text)
                    logger.debug(f"PaddleOCR extracted {len(rec_texts)} text segments, {len(extracted_text)} characters")
                    
                    if extracted_text.strip():
                        return extracted_text.strip()
                    else:
                        logger.warning("PaddleOCR returned empty text")
                else:
                    logger.warning("PaddleOCR result missing rec_texts field")
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
        text = pytesseract.image_to_string(img, lang='nld+eng')  # Dutch + English
        if text.strip():
            logger.debug(f"pytesseract extracted {len(text)} characters")
            return text.strip()
    except ImportError:
        logger.debug("pytesseract not available")
    except Exception as e:
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

