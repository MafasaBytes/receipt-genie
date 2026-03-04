"""
Debug script to test the pipeline directly and see what's happening.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models.db_models import UploadedFile
from services.pipeline import process_pdf_pipeline

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def debug_pipeline(file_id: str):
    """Debug the pipeline for a specific file_id."""
    db = SessionLocal()
    
    try:
        # Check if file exists
        uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
        if not uploaded_file:
            print(f"ERROR: File not found: {file_id}")
            print("\nAvailable files:")
            files = db.query(UploadedFile).all()
            for f in files:
                print(f"  - {f.file_id}: {f.original_filename} ({f.status})")
            print("\nTo list all files, run: python list_files.py")
            return
        
        print(f"\n{'='*60}")
        print(f"DEBUGGING PIPELINE FOR FILE: {file_id}")
        print(f"{'='*60}")
        print(f"File: {uploaded_file.original_filename}")
        print(f"Path: {uploaded_file.file_path}")
        print(f"Status: {uploaded_file.status}")
        print(f"{'='*60}\n")
        
        def progress_callback(progress: int, message: str):
            print(f"[PROGRESS] {progress}%: {message}")
        
        # Run pipeline
        print("Starting pipeline...\n")
        receipts = process_pdf_pipeline(file_id, db, progress_callback)
        
        print(f"\n{'='*60}")
        print("PIPELINE RESULTS")
        print(f"{'='*60}")
        print(f"Total receipts extracted: {len(receipts) if receipts else 0}")
        
        if receipts:
            for i, receipt in enumerate(receipts, 1):
                print(f"\nReceipt {i}:")
                print(f"  ID: {receipt.get('id')}")
                print(f"  Merchant: {receipt.get('merchant_name')}")
                print(f"  Date: {receipt.get('date')}")
                print(f"  Total: {receipt.get('total_amount')}")
                print(f"  Image: {receipt.get('image_path')}")
        else:
            print("\n⚠ No receipts extracted!")
            print("Check the logs above for error messages.")
        
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_pipeline.py <file_id>")
        print("\nTo get a file_id, upload a PDF first:")
        print("  curl -X POST -F 'file=@your_file.pdf' http://localhost:8000/api/upload/pdf")
        sys.exit(1)
    
    file_id = sys.argv[1]
    debug_pipeline(file_id)

