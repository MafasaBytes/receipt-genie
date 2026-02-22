"""
Test script specifically for the classical CV receipt detector.
Tests the detector directly and verifies it's working correctly.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.receipt_detector import detect_receipts
from services.pdf_utils import pdf_to_images
from config import settings
import cv2
import numpy as np

def test_detector_on_image(image_path: Path):
    """Test the receipt detector on a single image."""
    print(f"\n{'='*60}")
    print(f"Testing Receipt Detector: {image_path.name}")
    print(f"{'='*60}")
    
    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        return False
    
    # Load image to get dimensions
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        return False
    
    height, width = img.shape[:2]
    print(f"Image dimensions: {width}x{height}")
    
    # Run detection
    print("\nRunning receipt detection...")
    try:
        cropped_paths = detect_receipts(image_path)
        
        print(f"\n✓ Detection completed!")
        print(f"  Found {len(cropped_paths)} receipt(s)")
        
        for i, path in enumerate(cropped_paths, 1):
            path_obj = Path(path)
            print(f"\n  Receipt {i}:")
            print(f"    Path: {path}")
            
            if path_obj.exists():
                # Check if it's the original or a cropped version
                if path == str(image_path):
                    print(f"    Type: Original image (fallback)")
                    print(f"    Size: {path_obj.stat().st_size / 1024:.1f} KB")
                else:
                    print(f"    Type: Cropped receipt")
                    print(f"    Size: {path_obj.stat().st_size / 1024:.1f} KB")
                    
                    # Get cropped image dimensions
                    cropped_img = cv2.imread(str(path_obj))
                    if cropped_img is not None:
                        ch, cw = cropped_img.shape[:2]
                        print(f"    Dimensions: {cw}x{ch}")
                        
                        # Calculate crop ratio
                        original_area = width * height
                        cropped_area = cw * ch
                        crop_ratio = (cropped_area / original_area) * 100
                        print(f"    Crop ratio: {crop_ratio:.1f}% of original")
            else:
                print(f"    WARNING: File not found!")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Detection failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_detector_on_pdf(pdf_path: Path):
    """Test the receipt detector on a PDF (converts to images first)."""
    print(f"\n{'='*60}")
    print(f"Testing Receipt Detector on PDF: {pdf_path.name}")
    print(f"{'='*60}")
    
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return False
    
    # Convert PDF to images
    print("\nConverting PDF to images...")
    try:
        images_dir = settings.TEMP_DIR / "test_images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        image_paths = pdf_to_images(pdf_path, images_dir)
        print(f"✓ Converted {len(image_paths)} page(s) to images")
        
        if not image_paths:
            print("ERROR: No images extracted from PDF")
            return False
        
        # Test detector on each image
        results = []
        for i, image_path in enumerate(image_paths, 1):
            print(f"\n{'='*60}")
            print(f"Page {i}/{len(image_paths)}")
            print(f"{'='*60}")
            result = test_detector_on_image(image_path)
            results.append(result)
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total pages: {len(image_paths)}")
        print(f"Successful detections: {sum(results)}")
        print(f"Failed detections: {len(results) - sum(results)}")
        
        return all(results)
        
    except Exception as e:
        print(f"\n✗ Error processing PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("\n" + "="*60)
    print("CLASSICAL CV RECEIPT DETECTOR - TEST SUITE")
    print("="*60)
    print("\nThis script tests the new classical CV receipt detector")
    print("designed for faint, greyish, low-contrast Dutch receipts.")
    
    print("\nOptions:")
    print("1. Test on a single image file")
    print("2. Test on a PDF file (converts to images first)")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        image_path = input("Enter path to image file: ").strip()
        if image_path:
            test_detector_on_image(Path(image_path))
        else:
            print("No path provided.")
    
    elif choice == "2":
        pdf_path = input("Enter path to PDF file: ").strip()
        if pdf_path:
            test_detector_on_pdf(Path(pdf_path))
        else:
            print("No path provided.")
    
    elif choice == "3":
        print("Exiting...")
        return
    
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()

