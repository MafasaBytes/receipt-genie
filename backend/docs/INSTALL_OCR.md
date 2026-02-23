# Installing OCR for Real Text Extraction

## Current Status

The OCR engine is currently using placeholder text, which is why all receipts return the same data ("Sample Store", etc.).

## Solution: Install Real OCR

You have two options:

### Option 1: PaddleOCR (Recommended)

PaddleOCR is more accurate and works well with receipts.

**Install:**
```bash
pip install paddlepaddle paddleocr
```

**Note:** First installation downloads models (~100MB), so it may take a few minutes.

**Language Support:**
- For Dutch receipts, use `OCR_LANG="en"` (works reasonably well)
- Or install Dutch language pack if available

### Option 2: pytesseract (Alternative)

Tesseract OCR is lighter but may be less accurate.

**Install:**
```bash
# Install Python package
pip install pytesseract

# Install Tesseract binary:
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr
```

**For Dutch:**
```bash
# Install Dutch language pack
# Windows: Download from Tesseract installer
# macOS: brew install tesseract-lang
# Linux: sudo apt-get install tesseract-ocr-nld
```

## After Installation

Once installed, the OCR engine will automatically detect and use it. No code changes needed!

**Test:**
```bash
python debug_pipeline.py YOUR_FILE_ID
```

You should see:
- Real OCR text extracted from images
- Different data for each receipt
- Actual merchant names, dates, amounts

## Current Behavior

- **Without OCR installed**: Returns placeholder text (same for all receipts)
- **With PaddleOCR**: Extracts real text from images
- **With pytesseract**: Falls back to pytesseract if PaddleOCR not available

## Troubleshooting

### PaddleOCR Installation Issues

If installation fails:
```bash
# Try CPU-only version (lighter)
pip install paddlepaddle-cpu paddleocr
```

### pytesseract "TesseractNotFoundError"

Make sure Tesseract binary is installed and in PATH:
```bash
# Check if tesseract is available
tesseract --version
```

### Low OCR Accuracy

- Ensure images are high quality (300 DPI recommended)
- Check image contrast and brightness
- Try different OCR languages
- Consider image preprocessing (already done in receipt detector)

## Next Steps

1. Install PaddleOCR: `pip install paddlepaddle paddleocr`
2. Re-run pipeline: `python debug_pipeline.py YOUR_FILE_ID`
3. Check extracted text in logs
4. Verify different receipts have different data

