# Image File Support

## Overview

The backend now supports both **PDF files** and **image files** for receipt processing. When an image is uploaded, the system automatically skips the PDF conversion step and processes the image directly.

## Supported Image Formats

- **PNG** (.png)
- **JPEG/JPG** (.jpg, .jpeg)
- **BMP** (.bmp)
- **TIFF** (.tiff, .tif)
- **WEBP** (.webp)

## How It Works

### Upload Endpoint

Two endpoints are available:
- `/api/upload/file` - Generic endpoint (recommended)
- `/api/upload/pdf` - Legacy endpoint (still works for both PDFs and images)

Both endpoints accept PDFs and images.

### Processing Pipeline

The pipeline automatically detects the file type:

1. **If PDF**: 
   - Converts PDF to images (one image per page)
   - Processes each page image

2. **If Image**:
   - Skips PDF conversion
   - Processes the image directly
   - Detects and extracts receipts from the image

### Example Flow

**PDF Upload:**
```
PDF → Convert to Images → Detect Receipts → OCR → LLM → Database
```

**Image Upload:**
```
Image → Detect Receipts → OCR → LLM → Database
```

## Frontend Support

The frontend `FileUploader` component now accepts:
- PDF files
- Image files (PNG, JPG, JPEG, BMP, TIFF, WEBP)

Users can drag-and-drop or browse for either PDF or image files.

## API Usage

### Upload Image

```bash
curl -X POST "http://localhost:8000/api/upload/file" \
  -F "file=@receipt.png"
```

### Process Image

```bash
# Same as PDF processing
curl -X POST "http://localhost:8000/api/process/pdf?file_id={file_id}"
```

## Benefits

1. **Faster Processing**: Images skip PDF conversion, saving time
2. **Direct Upload**: Users can upload single receipt images directly
3. **Flexibility**: Supports both multi-page PDFs and single images
4. **Same Pipeline**: All processing steps (detection, OCR, LLM) work the same way

## Notes

- Image files are copied to the temp directory for consistency
- Multiple receipts can still be detected in a single image (if multiple receipts are present)
- File size limits apply to both PDFs and images (default: 50MB)
- All image formats are processed the same way through the receipt detection pipeline

