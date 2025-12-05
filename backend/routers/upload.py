"""
File upload endpoints.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path

from database import get_db
from models.db_models import UploadedFile
from models.receipt import UploadResponse
from utils.file_manager import save_uploaded_file
from utils.responses import success_response, error_response
from config import settings

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/pdf", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF file for processing.
    
    Returns:
        UploadResponse with file_id
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Read file content
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        # Check file size
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum of {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Save file
        file_id, file_path = save_uploaded_file(file_content, file.filename)
        
        # Create database record
        db_file = UploadedFile(
            file_id=file_id,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            status="uploaded"
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        return UploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=file_size,
            message="File uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )

