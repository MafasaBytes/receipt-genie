"""
Quick test to check if a file_id exists and show its details.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from database import SessionLocal
from models.db_models import UploadedFile
from pathlib import Path as PathLib

def test_file_id(file_id: str):
    """Test if a file_id exists and show details."""
    db = SessionLocal()
    
    try:
        uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
        
        if not uploaded_file:
            print(f"\n✗ File ID not found: {file_id}")
            print("\nListing all available files:")
            files = db.query(UploadedFile).all()
            if files:
                for f in files:
                    print(f"  - {f.file_id}: {f.original_filename}")
            else:
                print("  No files in database.")
            return False
        
        print(f"\n{'='*60}")
        print(f"FILE DETAILS: {file_id}")
        print(f"{'='*60}")
        print(f"Filename: {uploaded_file.original_filename}")
        print(f"Status: {uploaded_file.status}")
        print(f"Size: {uploaded_file.file_size / 1024:.1f} KB")
        print(f"Uploaded: {uploaded_file.upload_date}")
        print(f"Path: {uploaded_file.file_path}")
        
        file_path = PathLib(uploaded_file.file_path)
        if file_path.exists():
            print(f"File exists: ✓ ({file_path.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"File exists: ✗ (NOT FOUND)")
        
        print(f"{'='*60}\n")
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_file_id.py <file_id>")
        print("\nTo list all files, run: python list_files.py")
        sys.exit(1)
    
    file_id = sys.argv[1]
    test_file_id(file_id)

