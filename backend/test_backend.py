"""
Test script for the Receipt Scanner backend.
Tests all endpoints with actual data.
"""
import sys
import requests
import time
import json
from pathlib import Path

# Add backend directory to Python path for imports
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from config import settings

BASE_URL = "http://localhost:8000/api"

def print_response(title, response):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text}")
    print(f"{'='*60}\n")

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get("http://localhost:8000/health")
    print_response("Health Check", response)
    return response.status_code == 200

def test_upload_pdf(pdf_path: Path):
    """Test PDF upload endpoint."""
    print(f"Testing PDF upload with: {pdf_path}")
    
    if not pdf_path.exists():
        print(f"ERROR: PDF file not found: {pdf_path}")
        return None
    
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        response = requests.post(f"{BASE_URL}/upload/pdf", files=files)
    
    print_response("Upload PDF", response)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("file_id") if isinstance(data, dict) else data.get("data", {}).get("file_id")
    return None

def test_process_pdf(file_id: str):
    """Test PDF processing endpoint."""
    print(f"Testing PDF processing for file_id: {file_id}")
    
    response = requests.post(
        f"{BASE_URL}/process/pdf",
        params={"file_id": file_id}
    )
    
    print_response("Process PDF", response)
    
    if response.status_code == 200:
        data = response.json()
        job_id = data.get("job_id") if isinstance(data, dict) else data.get("data", {}).get("job_id")
        return job_id
    return None

def test_job_status(job_id: str, max_wait=120):
    """Test job status endpoint and wait for completion."""
    print(f"Monitoring job status for job_id: {job_id}")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/process/status/{job_id}")
        
        if response.status_code == 200:
            data = response.json()
            status_data = data if isinstance(data, dict) else data.get("data", {})
            
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress", 0)
            
            print(f"  Status: {status} | Progress: {progress}%", end="\r")
            
            if status == "completed":
                print("\n✓ Processing completed!")
                print_response("Job Status (Final)", response)
                return True
            elif status == "failed":
                print("\n✗ Processing failed!")
                print_response("Job Status (Failed)", response)
                return False
        
        time.sleep(2)
    
    print("\n⚠ Timeout waiting for job completion")
    return False

def test_get_receipts(file_id: str):
    """Test get receipts endpoint."""
    print(f"Fetching receipts for file_id: {file_id}")
    
    response = requests.get(f"{BASE_URL}/process/receipts/{file_id}")
    print_response("Get Receipts", response)
    
    if response.status_code == 200:
        data = response.json()
        receipts_data = data if isinstance(data, dict) else data.get("data", {})
        receipts = receipts_data.get("receipts", [])
        print(f"\n✓ Found {len(receipts)} receipt(s)")
        
        for i, receipt in enumerate(receipts, 1):
            print(f"\n  Receipt {i}:")
            print(f"    Merchant: {receipt.get('merchant_name', 'N/A')}")
            print(f"    Date: {receipt.get('date', 'N/A')}")
            print(f"    Total: ${receipt.get('total_amount', 0):.2f}")
            print(f"    Items: {len(receipt.get('items', []))}")
            print(f"    Image: {receipt.get('image_path', 'N/A')}")
            print(f"    Confidence: {receipt.get('confidence_score', 'N/A')}")
        
        return receipts
    return []

def test_export_csv(file_id: str, output_path: Path):
    """Test CSV export endpoint."""
    print(f"Testing CSV export for file_id: {file_id}")
    
    response = requests.get(f"{BASE_URL}/export/csv", params={"file_id": file_id})
    
    if response.status_code == 200:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✓ CSV exported to: {output_path}")
        return True
    else:
        print_response("Export CSV", response)
        return False

def test_export_excel(file_id: str, output_path: Path):
    """Test Excel export endpoint."""
    print(f"Testing Excel export for file_id: {file_id}")
    
    response = requests.get(f"{BASE_URL}/export/excel", params={"file_id": file_id})
    
    if response.status_code == 200:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✓ Excel exported to: {output_path}")
        return True
    else:
        print_response("Export Excel", response)
        return False

def check_cropped_receipts(file_id: str):
    """Check for cropped receipt images in temp directory."""
    print(f"\n{'='*60}")
    print("Checking for cropped receipt images...")
    print(f"{'='*60}")
    
    temp_dir = settings.TEMP_DIR
    images_dir = temp_dir / f"{file_id}_images"
    
    if images_dir.exists():
        cropped_files = list(images_dir.glob("*_receipt_cropped.png"))
        print(f"Found {len(cropped_files)} cropped receipt image(s):")
        for f in cropped_files:
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name} ({size_kb:.1f} KB)")
        return len(cropped_files)
    else:
        print("Images directory not found.")
        return 0

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("RECEIPT SCANNER BACKEND - TEST SUITE")
    print("Testing with Classical CV Receipt Detector")
    print("="*60)
    
    # Check if server is running
    try:
        if not test_health():
            print("ERROR: Server is not responding. Make sure the backend is running:")
            print("  python main.py")
            return
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server. Make sure the backend is running:")
        print("  python main.py")
        return
    
    # Get PDF file path
    print("\n" + "-"*60)
    print("NOTE: This test uses the new classical CV receipt detector")
    print("designed for faint, low-contrast Dutch receipts.")
    print("-"*60)
    pdf_path = input("\nEnter path to PDF file (or press Enter to skip upload test): ").strip()
    
    if not pdf_path:
        print("\nSkipping upload test. You can test manually using:")
        print("  curl -X POST -F 'file=@your_file.pdf' http://localhost:8000/api/upload/pdf")
        print("\nOr test the detector directly with:")
        print("  python test_receipt_detector.py")
        return
    
    pdf_path = Path(pdf_path)
    
    # Run tests
    try:
        # 1. Upload PDF
        file_id = test_upload_pdf(pdf_path)
        if not file_id:
            print("ERROR: Upload failed. Cannot continue.")
            return
        
        # 2. Process PDF
        job_id = test_process_pdf(file_id)
        if not job_id:
            print("ERROR: Processing failed to start. Cannot continue.")
            return
        
        # 3. Wait for processing
        if not test_job_status(job_id):
            print("WARNING: Processing did not complete successfully.")
        
        # 4. Check for cropped receipt images
        check_cropped_receipts(file_id)
        
        # 5. Get receipts
        receipts = test_get_receipts(file_id)
        
        if receipts:
            # 6. Export CSV
            csv_path = Path("test_exports") / f"{file_id}_receipts.csv"
            test_export_csv(file_id, csv_path)
            
            # 7. Export Excel
            excel_path = Path("test_exports") / f"{file_id}_receipts.xlsx"
            test_export_excel(file_id, excel_path)
        
        print("\n" + "="*60)
        print("TEST SUITE COMPLETED")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

