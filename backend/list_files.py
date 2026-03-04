"""
List all uploaded files to find file_ids.
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

def list_uploaded_files():
    """List all uploaded files with their file_ids."""
    db = SessionLocal()
    
    try:
        files = db.query(UploadedFile).order_by(UploadedFile.upload_date.desc()).all()
        
        if not files:
            print("No uploaded files found in database.")
            print("\nTo upload a file, use:")
            print("  curl -X POST -F 'file=@your_file.pdf' http://localhost:8000/api/upload/pdf")
            return
        
        print(f"\n{'='*80}")
        print(f"UPLOADED FILES ({len(files)} total)")
        print(f"{'='*80}\n")
        
        for i, file in enumerate(files, 1):
            file_path = PathLib(file.file_path)
            exists = "✓" if file_path.exists() else "✗"
            
            print(f"{i}. File ID: {file.file_id}")
            print(f"   Filename: {file.original_filename}")
            print(f"   Status: {file.status}")
            print(f"   Size: {file.file_size / 1024:.1f} KB")
            print(f"   Uploaded: {file.upload_date}")
            print(f"   Path: {file.file_path} {exists}")
            print()
        
        print(f"{'='*80}")
        print("\nTo debug a file, use:")
        print(f"  python debug_pipeline.py <file_id>")
        print(f"\nExample:")
        if files:
            print(f"  python debug_pipeline.py {files[0].file_id}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    list_uploaded_files()

