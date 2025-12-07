"""
Test OCR engine in isolation.
"""
import sys
from pathlib import Path
from services.ocr_engine import run_ocr, initialize_ocr_engine
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ocr_engine(image_path: str):
    """Test OCR engine on a single image."""
    image_path_obj = Path(image_path)
    
    if not image_path_obj.exists():
        logger.error(f"Image file not found: {image_path}")
        return
    
    logger.info(f"=" * 60)
    logger.info(f"Testing OCR Engine")
    logger.info(f"=" * 60)
    logger.info(f"Image: {image_path}")
    logger.info(f"File size: {image_path_obj.stat().st_size / 1024:.2f} KB")
    logger.info("")
    
    # Initialize OCR engine
    logger.info("Initializing OCR engine...")
    try:
        initialize_ocr_engine()
        logger.info("[OK] OCR engine initialized")
    except Exception as e:
        logger.error(f"[FAILED] OCR engine initialization failed: {str(e)}")
        logger.exception("Initialization error details:")
        return
    
    # Run OCR
    logger.info("")
    logger.info("Running OCR...")
    try:
        ocr_text = run_ocr(image_path_obj)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("OCR RESULTS")
        logger.info("=" * 60)
        logger.info(f"Text length: {len(ocr_text)} characters")
        logger.info(f"Text preview (first 500 chars):")
        logger.info("-" * 60)
        logger.info(ocr_text[:500])
        logger.info("-" * 60)
        logger.info("")
        logger.info("Full text:")
        logger.info("-" * 60)
        logger.info(ocr_text)
        logger.info("-" * 60)
        
        # Check if it's placeholder text
        placeholder_indicators = [
            "This is placeholder OCR text",
            "OCR engine not configured",
            "Please install"
        ]
        
        is_placeholder = any(indicator in ocr_text for indicator in placeholder_indicators)
        
        if is_placeholder:
            logger.warning("⚠️  WARNING: OCR returned placeholder text!")
            logger.warning("   This means OCR is not working properly.")
            logger.warning("   Check if PaddleOCR or pytesseract is installed.")
        else:
            logger.info("✓ OCR appears to be working (not placeholder text)")
        
        # Analyze text quality
        if len(ocr_text.strip()) == 0:
            logger.warning("⚠️  WARNING: OCR returned empty text!")
        elif len(ocr_text.strip()) < 50:
            logger.warning(f"⚠️  WARNING: OCR text is very short ({len(ocr_text.strip())} chars)")
        else:
            logger.info(f"✓ OCR text length looks reasonable ({len(ocr_text.strip())} chars)")
        
        # Check for common receipt keywords
        receipt_keywords = [
            "total", "totaal", "sum", "date", "datum",
            "vat", "btw", "tax", "eur", "€", "$", "£"
        ]
        found_keywords = [kw for kw in receipt_keywords if kw.lower() in ocr_text.lower()]
        if found_keywords:
            logger.info(f"✓ Found receipt keywords: {', '.join(found_keywords)}")
        else:
            logger.warning("⚠️  No common receipt keywords found in OCR text")
        
        return ocr_text
        
    except Exception as e:
        logger.error(f"[FAILED] OCR failed: {str(e)}")
        logger.exception("OCR error details:")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ocr_engine.py <image_path>")
        print("Example: python test_ocr_engine.py temp/crops/receipt_123.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    test_ocr_engine(image_path)

