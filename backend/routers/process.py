"""
Receipt processing endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid

from database import get_db
from models.db_models import UploadedFile, Receipt, ProcessingJob
from models.receipt import ProcessResponse, JobStatusResponse, ReceiptListResponse, ReceiptResponse
from services.pipeline import process_pdf_pipeline
from utils.responses import success_response, error_response
import json

router = APIRouter(prefix="/process", tags=["Process"])


# In-memory job status (in production, use Redis or database)
_job_status = {}


def update_job_status(job_id: str, status: str, progress: int, error_message: str = None):
    """Update job status in memory."""
    if job_id in _job_status:
        _job_status[job_id]["status"] = status
        _job_status[job_id]["progress"] = progress
        if error_message:
            _job_status[job_id]["error_message"] = error_message


def process_pdf_background(
    job_id: str,
    file_id: str,
    db: Session
):
    """Background task for processing PDF."""
    try:
        update_job_status(job_id, "processing", 0)
        
        def progress_callback(progress: int, message: str):
            update_job_status(job_id, "processing", progress)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[{job_id}] {progress}%: {message}")
        
        # Run pipeline
        receipts = process_pdf_pipeline(file_id, db, progress_callback)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[{job_id}] Pipeline completed. Extracted {len(receipts) if receipts else 0} receipt(s)")
        
        if not receipts or len(receipts) == 0:
            logger.warning(f"[{job_id}] No receipts extracted! Check logs for details.")
            update_job_status(job_id, "completed", 100, "No receipts extracted - check logs")
        else:
            update_job_status(job_id, "completed", 100)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[{job_id}] Pipeline failed: {str(e)}")
        logger.exception("Full error traceback:")
        update_job_status(job_id, "failed", 0, str(e))


@router.post("/pdf", response_model=ProcessResponse)
async def process_pdf(
    file_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Process a PDF file and extract receipts.
    
    This endpoint starts a background job and returns a job_id.
    Use /process/status/{job_id} to check progress.
    """
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create job record
    job = ProcessingJob(
        job_id=job_id,
        file_id=file_id,
        status="pending"
    )
    db.add(job)
    db.commit()
    
    # Initialize job status
    _job_status[job_id] = {
        "job_id": job_id,
        "file_id": file_id,
        "status": "pending",
        "progress": 0,
        "error_message": None
    }
    
    # Add background task
    background_tasks.add_task(process_pdf_background, job_id, file_id, db)
    
    return ProcessResponse(
        job_id=job_id,
        file_id=file_id,
        status="pending",
        message="Processing started. Use /process/status/{job_id} to check progress."
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get the status of a processing job."""
    # Check in-memory status
    if job_id not in _job_status:
        # Check database
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=job.job_id,
            file_id=job.file_id,
            status=job.status,
            progress=job.progress,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at
        )
    
    status_data = _job_status[job_id]
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    
    return JobStatusResponse(
        job_id=status_data["job_id"],
        file_id=status_data["file_id"],
        status=status_data["status"],
        progress=status_data["progress"],
        error_message=status_data.get("error_message"),
        created_at=job.created_at if job else None,
        completed_at=job.completed_at if job else None
    )


@router.get("/receipts/{file_id}", response_model=ReceiptListResponse)
async def get_receipts(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Get all extracted receipts for a file."""
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get receipts
    receipts = db.query(Receipt).filter(Receipt.file_id == file_id).order_by(Receipt.receipt_number).all()
    
    receipt_list = []
    for receipt in receipts:
        items = json.loads(receipt.items) if receipt.items else []
        receipt_list.append(ReceiptResponse(
            id=receipt.id,
            file_id=receipt.file_id,
            receipt_number=receipt.receipt_number,
            merchant_name=receipt.merchant_name,
            date=receipt.date,
            total_amount=receipt.total_amount,
            tax_amount=receipt.tax_amount,
            subtotal=receipt.subtotal,
            items=items,
            payment_method=receipt.payment_method,
            address=receipt.address,
            phone=receipt.phone,
            raw_text=receipt.raw_text,
            image_path=receipt.image_path,
            confidence_score=receipt.confidence_score,
            extraction_date=receipt.extraction_date
        ))
    
    return ReceiptListResponse(
        file_id=file_id,
        receipts=receipt_list,
        total=len(receipt_list)
    )

