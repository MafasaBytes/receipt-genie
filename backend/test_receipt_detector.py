"""
Test script for the receipt detector (single-receipt-per-page mode).

Verifies that detect_receipts returns the original image path unchanged.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.receipt_detector import detect_receipts


def test_detector_on_image(image_path: Path):
    """Test the receipt detector returns the original image unchanged."""
    print(f"\nTesting: {image_path.name}")

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        return False

    result = detect_receipts(image_path)
    assert result == [str(image_path)], f"Expected [{image_path}], got {result}"
    print(f"  OK — returned original image path")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_detector_on_image(Path(sys.argv[1]))
    else:
        print("Usage: python test_receipt_detector.py <image_path>")
