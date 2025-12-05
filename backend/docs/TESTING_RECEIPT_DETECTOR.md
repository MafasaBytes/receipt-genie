# Testing the Classical CV Receipt Detector

## Quick Test Options

### Option 1: Test Detector Directly (Recommended)

Test the receipt detector without going through the full API:

```bash
python test_receipt_detector.py
```

This script allows you to:
- Test on a single image file
- Test on a PDF file (converts to images first)
- See detailed information about detection results
- Verify cropped receipt images are created

**Example:**
```
1. Test on a single image file
2. Test on a PDF file (converts to images first)
3. Exit

Enter choice (1-3): 2
Enter path to PDF file: path/to/receipts.pdf
```

### Option 2: Test Full Pipeline via API

Test the complete backend including the new detector:

```bash
python test_backend.py
```

This will:
- Upload a PDF
- Process it through the full pipeline
- Show detection results
- Display extracted receipts
- Export to CSV/Excel

### Option 3: Manual API Testing

```bash
# 1. Upload PDF
curl -X POST -F "file=@your_receipts.pdf" http://localhost:8000/api/upload/pdf

# 2. Process (use file_id from step 1)
curl -X POST "http://localhost:8000/api/process/pdf?file_id=YOUR_FILE_ID"

# 3. Check status
curl "http://localhost:8000/api/process/status/YOUR_JOB_ID"

# 4. Get results
curl "http://localhost:8000/api/process/receipts/YOUR_FILE_ID"
```

## What to Look For

### Successful Detection
- ✅ Cropped receipt images created in `temp/{file_id}_images/`
- ✅ Files named `*_receipt_cropped.png`
- ✅ Receipts extracted and saved to database
- ✅ Image paths in receipt data

### Fallback Behavior
- ✅ If detection fails, original image path is used
- ✅ Processing continues without errors
- ✅ Full page is processed as receipt

### Detection Quality
- **Good**: Receipt is clearly cropped, perspective corrected
- **Fallback**: Original image used (detection couldn't find receipt)
- **Check logs**: Look for "No contours found" or "No valid contours found"

## Expected Output

### From `test_receipt_detector.py`:

```
============================================================
Testing Receipt Detector: receipt_page_1.png
============================================================
Image dimensions: 1654x2339

Running receipt detection...

✓ Detection completed!
  Found 1 receipt(s)

  Receipt 1:
    Path: temp/test_images/receipt_page_1_receipt_cropped.png
    Type: Cropped receipt
    Size: 245.3 KB
    Dimensions: 800x1200
    Crop ratio: 25.3% of original
```

### From `test_backend.py`:

```
Checking for cropped receipt images...
============================================================
Found 1 cropped receipt image(s):
  - receipt_page_1_receipt_cropped.png (245.3 KB)

✓ Found 1 receipt(s)

  Receipt 1:
    Merchant: Sample Store
    Date: 2024-01-15
    Total: $27.54
    Items: 2
    Image: temp/xxx_images/receipt_page_1_receipt_cropped.png
    Confidence: 1.0
```

## Troubleshooting

### No Cropped Images Found
- Check if detection is using fallback (original image)
- Verify image has clear borders/edges
- Check logs for detection errors
- Try adjusting image contrast/preprocessing

### Detection Fails
- **Check image quality**: Faint receipts may need preprocessing
- **Verify borders**: Receipt should have visible edges
- **Check aspect ratio**: Should be taller than wide
- **Area check**: Receipt should be 5-95% of image

### Processing Errors
- Ensure backend server is running
- Check database connection
- Verify Ollama is running (for LLM extraction)
- Check temp directory permissions

## Performance

Expected detection times:
- **Single image**: 0.5-2 seconds
- **PDF page**: 1-3 seconds (including conversion)
- **Full PDF (10 pages)**: 10-30 seconds

## Next Steps

1. Test with your actual receipt images
2. Verify cropped receipts look correct
3. Check OCR quality on cropped images
4. Adjust detection parameters if needed (in `receipt_detector.py`)

