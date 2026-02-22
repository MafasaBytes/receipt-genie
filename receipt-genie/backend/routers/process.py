"""
Receipt processing endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid

from database import get_db
from models.db_models import UploadedFile, Receipt, ProcessingJob
from models.receipt import (
    ProcessResponse, JobStatusResponse, ReceiptListResponse, ReceiptResponse,
    EnhancedReceiptListResponse, PageStat, ReceiptUpdate
)
from services.pipeline import process_pdf_pipeline
from services.vector_store import index_receipt as vs_index_receipt, get_store_stats
from utils.responses import success_response, error_response
import json
import logging

logger = logging.getLogger(__name__)

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
        
        # Run pipeline - now returns enhanced response with stats
        result = process_pdf_pipeline(file_id, db, progress_callback)
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Handle both old format (list) and new format (dict with stats)
        if isinstance(result, dict):
            receipts = result.get("receipts", [])
            logger.info(f"[{job_id}] Pipeline completed. Extracted {len(receipts)} receipt(s) from {result.get('receipts_detected', 0)} detected")
        else:
            # Legacy format - list of receipts
            receipts = result if result else []
            logger.info(f"[{job_id}] Pipeline completed. Extracted {len(receipts)} receipt(s)")
        
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


@router.get("/receipts/{file_id}", response_model=EnhancedReceiptListResponse)
async def get_receipts(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Get all extracted receipts for a file with enhanced stats."""
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get receipts
    receipts = db.query(Receipt).filter(Receipt.file_id == file_id).order_by(Receipt.receipt_number).all()
    
    receipt_list = []
    for receipt in receipts:
        items_data = json.loads(receipt.items) if receipt.items else {}
        # Extract metadata if stored in items JSON
        metadata = items_data.get("_metadata", {}) if isinstance(items_data, dict) else {}
        items = items_data if isinstance(items_data, list) else (items_data.get("items", []) if isinstance(items_data, dict) else [])
        
        receipt_list.append(ReceiptResponse(
            id=receipt.id,
            file_id=receipt.file_id,
            receipt_number=receipt.receipt_number,
            merchant_name=receipt.merchant_name,
            date=receipt.date,
            total_amount=receipt.total_amount,
            tax_amount=receipt.tax_amount,
            subtotal=receipt.subtotal,
            items=items if isinstance(items, list) else [],
            vat_breakdown=receipt.vat_breakdown if receipt.vat_breakdown else [],
            vat_percentage_effective=receipt.vat_percentage_effective,
            payment_method=receipt.payment_method,
            address=receipt.address,
            phone=receipt.phone,
            raw_text=receipt.raw_text,
            image_path=receipt.image_path,
            confidence_score=receipt.confidence_score,
            extraction_date=receipt.extraction_date,
            currency=metadata.get("currency"),
            vat_percentage=receipt.vat_percentage_effective or metadata.get("vat_percentage"),
            missing_fields=metadata.get("missing_fields")
        ))
    
    # Calculate stats (simplified - in production, store these in database)
    # For now, we'll estimate based on receipts found
    receipts_extracted = len(receipt_list)
    # Estimate detected as extracted + some margin (in production, track this)
    receipts_detected = max(receipts_extracted, receipts_extracted + 1)
    
    return EnhancedReceiptListResponse(
        file_id=file_id,
        pages_processed=1,  # Would need to track this
        receipts_detected=receipts_detected,
        receipts_extracted=receipts_extracted,
        missing_receipts_estimate=max(0, receipts_detected - receipts_extracted),
        page_stats=[PageStat(
            page_number=1,
            detected=receipts_detected,
            successful=receipts_extracted,
            rejected=max(0, receipts_detected - receipts_extracted),
            rejection_reasons=[]
        )],
        detection_warning=receipts_detected == 0,
        receipts=receipt_list
    )


@router.patch("/receipt/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(
    receipt_id: int,
    receipt_update: ReceiptUpdate,
    db: Session = Depends(get_db)
):
    """Update receipt fields. If items or vat_breakdown are updated, re-runs reconciliation."""
    # Get receipt
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Import functions
    from services.pipeline import normalize_extracted_fields
    from services.llm_extractor import reconcile_vat_and_items
    
    # Build update dict
    update_data = receipt_update.model_dump(exclude_unset=True)
    
    # Separate fields that need special handling
    currency_update = update_data.pop("currency", None)
    vat_percentage_update = update_data.pop("vat_percentage", None)
    items_update = update_data.pop("items", None)
    vat_breakdown_update = update_data.pop("vat_breakdown", None)
    
    # Check if we need to re-run reconciliation
    needs_reconciliation = items_update is not None or vat_breakdown_update is not None
    
    # Normalize basic fields
    if update_data:
        normalized = normalize_extracted_fields(update_data)
        for key, value in normalized.items():
            if value is not None:
                setattr(receipt, key, value)
    
    # Handle items update
    if items_update is not None:
        # Update items JSON
        items_data = json.loads(receipt.items) if receipt.items else {}
        if not isinstance(items_data, dict):
            items_data = {"items": items_data if isinstance(items_data, list) else []}
        
        items_data["items"] = items_update
        receipt.items = json.dumps(items_data)
    
    # Handle VAT breakdown update
    if vat_breakdown_update is not None:
        receipt.vat_breakdown = vat_breakdown_update
    
    # Re-run reconciliation if needed
    if needs_reconciliation:
        # Build extracted dict for reconciliation
        extracted_dict = {
            "merchant_name": receipt.merchant_name,
            "date": receipt.date,
            "total_amount": receipt.total_amount,
            "tax_amount": receipt.tax_amount,
            "subtotal": receipt.subtotal,
            "currency": currency_update or (json.loads(receipt.items) if receipt.items else {}).get("_metadata", {}).get("currency"),
            "items": items_update if items_update is not None else (json.loads(receipt.items) if receipt.items else {}).get("items", []),
            "vat_breakdown": vat_breakdown_update if vat_breakdown_update is not None else receipt.vat_breakdown,
            "payment_method": receipt.payment_method,
            "address": receipt.address,
            "phone": receipt.phone,
        }
        
        # Reconcile
        reconciled = reconcile_vat_and_items(extracted_dict, receipt.raw_text or "")
        
        # Update fields from reconciliation
        receipt.vat_breakdown = reconciled.get("vat_breakdown", [])
        receipt.vat_percentage_effective = reconciled.get("vat_percentage_effective")
        
        # Update totals if they changed
        if reconciled.get("total_amount") is not None:
            receipt.total_amount = reconciled["total_amount"]
        if reconciled.get("tax_amount") is not None:
            receipt.tax_amount = reconciled["tax_amount"]
        if reconciled.get("subtotal") is not None:
            receipt.subtotal = reconciled["subtotal"]
    
    # Update currency and vat_percentage in items metadata
    items_data = json.loads(receipt.items) if receipt.items else {}
    if not isinstance(items_data, dict):
        items_data = {"items": items_data if isinstance(items_data, list) else []}
    
    if "_metadata" not in items_data:
        items_data["_metadata"] = {}
    
    if currency_update is not None:
        items_data["_metadata"]["currency"] = currency_update
    if vat_percentage_update is not None:
        # Round VAT percentage to 1 decimal
        items_data["_metadata"]["vat_percentage"] = round(float(vat_percentage_update), 1)
    elif receipt.vat_percentage_effective is not None:
        # Use effective VAT if no explicit update
        items_data["_metadata"]["vat_percentage"] = receipt.vat_percentage_effective
    
    receipt.items = json.dumps(items_data)
    
    db.commit()
    db.refresh(receipt)

    # Re-index the user-corrected receipt so it becomes a high-quality
    # few-shot example for future RAG retrievals (feedback loop).
    try:
        from config import settings
        if settings.RAG_ENABLED:
            corrected_fields = {
                "merchant_name": receipt.merchant_name,
                "date": receipt.date,
                "total_amount": receipt.total_amount,
                "tax_amount": receipt.tax_amount,
                "subtotal": receipt.subtotal,
                "currency": items_data.get("_metadata", {}).get("currency"),
                "items": items_data.get("items", []) if isinstance(items_data, dict) else [],
                "vat_breakdown": receipt.vat_breakdown or [],
                "vat_percentage_effective": receipt.vat_percentage_effective,
                "payment_method": receipt.payment_method,
                "address": receipt.address,
                "phone": receipt.phone,
            }
            vs_index_receipt(
                receipt_id=receipt.id,
                ocr_text=receipt.raw_text or "",
                extracted_fields=corrected_fields,
                is_user_corrected=True,
            )
            logger.info(f"Re-indexed corrected receipt {receipt.id} in vector store")
    except Exception as e:
        logger.warning(f"Failed to re-index corrected receipt {receipt.id}: {e}")

    # Return updated receipt
    metadata = items_data.get("_metadata", {})
    items = items_data.get("items", []) if isinstance(items_data, dict) else (items_data if isinstance(items_data, list) else [])
    
    return ReceiptResponse(
        id=receipt.id,
        file_id=receipt.file_id,
        receipt_number=receipt.receipt_number,
        merchant_name=receipt.merchant_name,
        date=receipt.date,
        total_amount=receipt.total_amount,
        tax_amount=receipt.tax_amount,
        subtotal=receipt.subtotal,
        items=items if isinstance(items, list) else [],
        vat_breakdown=receipt.vat_breakdown if receipt.vat_breakdown else [],
        vat_percentage_effective=receipt.vat_percentage_effective,
        payment_method=receipt.payment_method,
        address=receipt.address,
        phone=receipt.phone,
        raw_text=receipt.raw_text,
        image_path=receipt.image_path,
        confidence_score=receipt.confidence_score,
        extraction_date=receipt.extraction_date,
        currency=metadata.get("currency"),
        vat_percentage=receipt.vat_percentage_effective,  # Use effective VAT
        missing_fields=metadata.get("missing_fields")
    )


@router.get("/rag/stats")
async def get_rag_stats():
    """Return RAG vector store statistics."""
    from config import settings
    stats = get_store_stats()
    stats["rag_enabled"] = settings.RAG_ENABLED
    stats["embedding_model"] = settings.EMBEDDING_MODEL
    stats["top_k"] = settings.RAG_TOP_K
    stats["min_similarity"] = settings.RAG_MIN_SIMILARITY
    return stats


@router.get("/file/{file_id}/stats")
async def get_file_stats(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Get processing statistics for a file."""
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get receipts
    receipts = db.query(Receipt).filter(Receipt.file_id == file_id).all()
    
    receipts_extracted = len(receipts)
    receipts_detected = max(receipts_extracted, receipts_extracted + 1)  # Estimate
    
    # Calculate average confidence
    avg_confidence = 0.0
    if receipts:
        confidences = [r.confidence_score for r in receipts if r.confidence_score is not None]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
    
    # Count fields with missing data
    missing_fields_count = 0
    for receipt in receipts:
        if receipt.merchant_name is None:
            missing_fields_count += 1
        if receipt.date is None:
            missing_fields_count += 1
        if receipt.total_amount is None:
            missing_fields_count += 1
        if receipt.tax_amount is None:
            missing_fields_count += 1
        if receipt.currency is None:
            missing_fields_count += 1
    
    return {
        "file_id": file_id,
        "receipts_detected": receipts_detected,
        "receipts_extracted": receipts_extracted,
        "missing_receipts_estimate": max(0, receipts_detected - receipts_extracted),
        "average_confidence": round(avg_confidence, 2),
        "total_missing_fields": missing_fields_count,
        "pages_processed": 1,  # Would need to track this
        "error_breakdown": {
            "no_merchant_name": sum(1 for r in receipts if r.merchant_name is None),
            "no_date": sum(1 for r in receipts if r.date is None),
            "no_total": sum(1 for r in receipts if r.total_amount is None),
            "no_tax": sum(1 for r in receipts if r.tax_amount is None),
            "no_currency": sum(1 for r in receipts if r.currency is None)
        }
    }

