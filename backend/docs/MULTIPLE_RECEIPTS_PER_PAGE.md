# Multiple Receipts Per Page Detection

## Overview

The receipt detector has been updated to detect and extract **multiple receipts from a single image/page**. Previously, it only detected the largest receipt per page.

## How It Works

### Detection Process

1. **Contour Detection**: Finds all rectangular/contour regions in the image
2. **Filtering**: Filters contours by:
   - **Area**: Between 2% and 95% of image area (relaxed from 5% to handle smaller receipts when multiple are present)
   - **Aspect Ratio**: Height > width (typical receipt shape) OR large area (>10%) for square-ish receipts
3. **Non-Maximum Suppression**: Removes overlapping contours using IoU (Intersection over Union)
   - If two contours overlap by more than 30% (IoU > 0.3), only the larger one is kept
4. **Individual Processing**: Each non-overlapping contour is:
   - Approximated to a polygon
   - Perspective-corrected (if 4 corners detected)
   - Cropped and saved as a separate receipt image

### Output

- Each detected receipt is saved as: `{image_name}_receipt_{N}_cropped.png`
- All cropped receipt paths are returned as a list
- The pipeline processes each receipt independently (OCR + LLM extraction)

## Example

If a PDF page contains 3 receipts:
- Original: `page_1.png`
- Detected receipts:
  - `page_1_receipt_1_cropped.png`
  - `page_1_receipt_2_cropped.png`
  - `page_1_receipt_3_cropped.png`

All 3 receipts will be processed and extracted separately.

## Configuration

The detection parameters can be adjusted in `backend/services/receipt_detector.py`:

- **Area threshold**: `0.02 < area_ratio < 0.95` (2% to 95% of image)
- **Aspect ratio**: `aspect_ratio > 1.0` (height > width) OR `area_ratio > 0.1` (large receipts)
- **IoU threshold**: `0.3` (30% overlap threshold for non-maximum suppression)
- **Minimum size**: `100x100` pixels (receipts smaller than this are skipped)

## Troubleshooting

### Too Many False Positives

If the detector is finding too many non-receipt regions:
- Increase the minimum area threshold (e.g., from 0.02 to 0.05)
- Tighten the aspect ratio requirement (e.g., from 1.0 to 1.2)
- Increase the IoU threshold (e.g., from 0.3 to 0.5)

### Missing Some Receipts

If some receipts are not being detected:
- Decrease the minimum area threshold (e.g., from 0.02 to 0.01)
- Relax the aspect ratio requirement
- Check if receipts are too faint (may need preprocessing improvements)

### Overlapping Receipts

If receipts are overlapping and one is being filtered out:
- Decrease the IoU threshold (e.g., from 0.3 to 0.2)
- This will allow more overlapping contours to be kept

## Testing

Test with your PDF that has multiple receipts per page:

```bash
python test_receipt_detector.py path/to/your/file.pdf
```

Or test a single image:

```bash
python test_receipt_detector.py path/to/your/image.png
```

The test script will show:
- Number of receipts detected per page
- Bounding boxes and areas
- Paths to cropped receipt images

