"""
End-to-end receipt processing pipeline.
"""
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import uuid
import json
import logging
import time

from config import settings
from services.pdf_utils import pdf_to_images
from services.receipt_detector import detect_receipts, crop_receipt
from services.ocr_engine import run_ocr
from services.llm_extractor import extract_fields_llm, check_ollama_connection
from models.db_models import Receipt, UploadedFile
from models.receipt import ReceiptCreate

logger = logging.getLogger(__name__)


def normalize_extracted_fields(extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and clean extracted fields:
    - Round VAT percentage to 1 decimal place
    - Round amounts to 2 decimal places
    - Normalize currency strings
    - Strip whitespace from text fields
    - Infer VAT percentage if missing
    """
    normalized = extracted_fields.copy()
    
    # Round amounts to 2 decimal places
    if normalized.get("total_amount") is not None:
        normalized["total_amount"] = round(float(normalized["total_amount"]), 2)
    if normalized.get("tax_amount") is not None:
        normalized["tax_amount"] = round(float(normalized["tax_amount"]), 2)
    if normalized.get("vat_amount") is not None:
        normalized["vat_amount"] = round(float(normalized["vat_amount"]), 2)
    if normalized.get("subtotal") is not None:
        normalized["subtotal"] = round(float(normalized["subtotal"]), 2)
    
    # Normalize VAT percentage: round to 1 decimal place, infer if missing
    if normalized.get("vat_percentage") is not None:
        normalized["vat_percentage"] = round(float(normalized["vat_percentage"]), 1)
    elif normalized.get("total_amount") and normalized.get("tax_amount"):
        # Infer VAT percentage if missing
        total = float(normalized["total_amount"])
        tax = float(normalized["tax_amount"])
        if total > tax > 0:
            subtotal = total - tax
            if subtotal > 0:
                inferred_vat_pct = (tax / subtotal) * 100
                normalized["vat_percentage"] = round(inferred_vat_pct, 1)
    
    # Normalize currency: only allow valid 3-letter codes
    valid_currencies = {"EUR", "USD", "GBP", "CAD", "AUD", "JPY", "CNY", "INR", "CHF"}
    if normalized.get("currency"):
        currency = str(normalized["currency"]).strip().upper()
        if currency in valid_currencies:
            normalized["currency"] = currency
        else:
            # Try to map common symbols
            currency_map = {"€": "EUR", "$": "USD", "£": "GBP", "¥": "JPY", "₹": "INR"}
            if currency in currency_map:
                normalized["currency"] = currency_map[currency]
            else:
                normalized["currency"] = None
    
    # Safety fallback: Default to EUR if currency is not detected
    # This is a reasonable default for Dutch receipts and many European receipts
    if normalized.get("currency") is None:
        logger.debug("Currency not detected, defaulting to EUR as safety fallback")
        normalized["currency"] = "EUR"
    
    # Strip whitespace from text fields
    if normalized.get("merchant_name"):
        normalized["merchant_name"] = str(normalized["merchant_name"]).strip() or None
    if normalized.get("date"):
        normalized["date"] = str(normalized["date"]).strip() or None
    if normalized.get("payment_method"):
        normalized["payment_method"] = str(normalized["payment_method"]).strip() or None
    if normalized.get("address"):
        normalized["address"] = str(normalized["address"]).strip() or None
    if normalized.get("phone"):
        normalized["phone"] = str(normalized["phone"]).strip() or None
    
    return normalized


def add_missing_field_metadata(extracted_fields: Dict[str, Any], confidence_score: float) -> Dict[str, Any]:
    """
    Add metadata for missing fields when confidence is high (>0.90).
    Returns fields with 'missing' and 'reason' metadata.
    """
    metadata = {}
    key_fields = ["merchant_name", "date", "total_amount", "tax_amount", "vat_percentage", "currency"]
    
    if confidence_score > 0.90:
        for field in key_fields:
            if extracted_fields.get(field) is None:
                metadata[field] = {
                    "missing": True,
                    "reason": "high confidence but field missing"
                }
    
    return metadata


def calculate_confidence_score(extracted_fields: Dict[str, Any], llm_success: bool, ocr_text: str) -> float:
    """
    Calculate confidence score based on extraction quality.
    
    Factors:
    - LLM extraction success (40%)
    - Number of fields extracted (40%)
    - OCR text quality (20%)
    
    Returns: float between 0.0 and 1.0
    """
    score = 0.0
    
    # Factor 1: LLM extraction success (40%)
    if llm_success:
        score += 0.4
    # If LLM failed, we get 0 for this factor
    
    # Factor 2: Number of fields extracted (40%)
    # Key fields: merchant_name, date, total_amount, tax_amount, currency
    key_fields = ["merchant_name", "date", "total_amount", "tax_amount", "currency"]
    extracted_count = sum(1 for field in key_fields if extracted_fields.get(field) is not None)
    field_score = (extracted_count / len(key_fields)) * 0.4
    score += field_score
    
    # Factor 3: OCR text quality (20%)
    # Based on text length and character diversity
    if ocr_text and len(ocr_text.strip()) > 0:
        text_length = len(ocr_text.strip())
        # Good OCR should have at least 50 characters
        if text_length >= 50:
            # Check for character diversity (not just repeated characters)
            unique_chars = len(set(ocr_text.strip().lower()))
            if unique_chars >= 10:  # At least 10 different characters
                score += 0.2
            elif unique_chars >= 5:
                score += 0.1
        elif text_length >= 20:
            score += 0.1
    
    # Ensure score is between 0.0 and 1.0
    return max(0.0, min(1.0, score))


def is_image_file(file_path: Path) -> bool:
    """Check if file is an image based on extension."""
    image_extensions = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"]
    return any(str(file_path).lower().endswith(ext) for ext in image_extensions)


def is_pdf_file(file_path: Path) -> bool:
    """Check if file is a PDF based on extension."""
    return str(file_path).lower().endswith(".pdf")


def process_pdf_pipeline(
    file_id: str,
    db: Session,
    progress_callback=None
) -> List[Dict[str, Any]]:
    """
    Complete pipeline: PDF/Image → Images → Detection → OCR → LLM → Database.
    
    Supports both PDF files and image files (PNG, JPG, JPEG, BMP, TIFF, WEBP).
    If image is uploaded, skips PDF conversion step.
    
    Args:
        file_id: ID of the uploaded file (PDF or image)
        db: Database session
        progress_callback: Optional callback function(progress: int, message: str)
        
    Returns:
        List of extracted receipt data
    """
    # Get uploaded file record
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise ValueError(f"File not found: {file_id}")
    
    file_path = Path(uploaded_file.file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check Ollama connection
    if not check_ollama_connection():
        logger.warning("Ollama is not available. LLM extraction will fail.")
        logger.warning("Start Ollama with: ollama serve")
    
    # Update status
    uploaded_file.status = "processing"
    db.commit()
    
    pipeline_start_time = time.time()
    
    try:
        # Step 1: Convert PDF to images OR use image directly
        if is_image_file(file_path):
            # Image file: use directly, skip PDF conversion
            if progress_callback:
                progress_callback(10, "Processing image file...")
            
            logger.info(f"Processing image file directly: {file_path}")
            image_paths = [file_path]
            
            # If needed, copy to temp directory for consistency
            images_dir = settings.TEMP_DIR / f"{file_id}_images"
            images_dir.mkdir(exist_ok=True)
            temp_image_path = images_dir / f"{file_id}_page_1{file_path.suffix}"
            if not temp_image_path.exists():
                import shutil
                shutil.copy2(file_path, temp_image_path)
                image_paths = [temp_image_path]
                logger.debug(f"Copied image to temp directory: {temp_image_path}")
            
        elif is_pdf_file(file_path):
            # PDF file: convert to images
            if progress_callback:
                progress_callback(10, "Converting PDF to images...")
            
            logger.info(f"Converting PDF to images: {file_path}")
            step_start = time.time()
            
            images_dir = settings.TEMP_DIR / f"{file_id}_images"
            images_dir.mkdir(exist_ok=True)
            image_paths = pdf_to_images(file_path, images_dir)
            
            logger.info(f"Extracted {len(image_paths)} images in {time.time() - step_start:.2f}s")
            
            if not image_paths:
                raise ValueError("No images extracted from PDF")
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}. Supported: PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP")
        
        all_receipts = []
        total_steps = len(image_paths)
        total_receipts_processed = 0
        estimated_total_receipts = total_steps * 2  # Estimate 2 receipts per page (will adjust dynamically)
        
        # Statistics tracking
        page_stats = []  # List of dicts with page statistics
        
        # Process each page
        for page_idx, image_path in enumerate(image_paths):
            page_stat = {
                "page_number": page_idx + 1,
                "detected": 0,
                "successful": 0,
                "rejected": 0,
                "rejection_reasons": []
            }
            if progress_callback:
                # Base progress: 10% for PDF conversion, 70% for processing
                # Distribute across pages
                base_progress = 10 + int((page_idx / max(total_steps, 1)) * 30)
                progress_callback(base_progress, f"Processing page {page_idx + 1}/{total_steps}...")
            
            # Step 2: Detect and extract receipts in image
            logger.info(f"=" * 60)
            logger.info(f"PAGE {page_idx + 1}/{total_steps}: Detecting receipts")
            logger.info(f"  Source image: {image_path}")
            detection_start = time.time()
            try:
                cropped_receipt_paths = detect_receipts(image_path)
                detection_duration = time.time() - detection_start
                page_stat["detected"] = len(cropped_receipt_paths)
                logger.info(f"[OK] Detection completed in {detection_duration:.2f}s")
                logger.info(f"  → Detected {len(cropped_receipt_paths)} receipt(s) on page {page_idx + 1}")
                for i, path in enumerate(cropped_receipt_paths, 1):
                    logger.info(f"    Receipt {i}: {path}")
            except Exception as det_error:
                logger.error(f"[FAILED] Receipt detection failed on page {page_idx + 1}: {str(det_error)}")
                logger.exception("Detection error details:")
                page_stat["rejected"] = 1
                page_stat["rejection_reasons"].append(f"Detection error: {str(det_error)}")
                page_stats.append(page_stat)
                continue
            
            if not cropped_receipt_paths:
                logger.warning(f"[WARNING] No receipts detected in page {page_idx + 1}, skipping")
                page_stats.append(page_stat)
                continue
            
            # Update estimated total if we found more receipts than expected
            if len(cropped_receipt_paths) > 2:
                estimated_total_receipts = max(estimated_total_receipts, total_receipts_processed + len(cropped_receipt_paths) + (total_steps - page_idx - 1) * 2)
            
            # Process each detected receipt
            for receipt_idx, cropped_path_str in enumerate(cropped_receipt_paths):
                receipt_success = False
                receipt_rejection_reason = None
                
                try:
                    # cropped_path is already a path to the cropped receipt image
                    cropped_path = Path(cropped_path_str)
                    
                    # Verify cropped image exists
                    if not cropped_path.exists():
                        logger.warning(f"[WARNING] Cropped receipt image not found: {cropped_path}")
                        logger.info(f"  Using original image path as fallback: {image_path}")
                        if image_path.exists():
                            cropped_path = image_path
                        else:
                            logger.error(f"[FAILED] Original image also not found: {image_path}, skipping receipt")
                            receipt_rejection_reason = "Image file not found"
                            page_stat["rejected"] += 1
                            page_stat["rejection_reasons"].append(f"Receipt {receipt_idx + 1}: {receipt_rejection_reason}")
                            continue
                    
                    logger.info(f"  Processing receipt {receipt_idx + 1}/{len(cropped_receipt_paths)} from page {page_idx + 1}")
                    logger.info(f"    Image: {cropped_path.name}")
                    
                    # Step 3: Run OCR on cropped receipt
                    ocr_start = time.time()
                    try:
                        ocr_text = run_ocr(cropped_path)
                        ocr_duration = time.time() - ocr_start
                        logger.info(f"[OK] OCR completed in {ocr_duration:.2f}s ({len(ocr_text) if ocr_text else 0} chars)")
                    except Exception as ocr_error:
                        logger.error(f"[FAILED] OCR failed: {str(ocr_error)}")
                        logger.exception("OCR error details:")
                        receipt_rejection_reason = f"OCR error: {str(ocr_error)}"
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append(f"Receipt {receipt_idx + 1}: {receipt_rejection_reason}")
                        continue
                    
                    if not ocr_text or len(ocr_text.strip()) < 10:
                        logger.warning(f"[WARNING] Insufficient OCR text ({len(ocr_text) if ocr_text else 0} chars < 10), skipping receipt")
                        logger.debug(f"    OCR text preview: {ocr_text[:100] if ocr_text else 'None'}")
                        receipt_rejection_reason = f"Insufficient OCR text ({len(ocr_text) if ocr_text else 0} chars)"
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append(f"Receipt {receipt_idx + 1}: {receipt_rejection_reason}")
                        continue
                    
                    # Step 4: Extract fields with LLM
                    receipt_number = len(all_receipts) + 1
                    total_receipts_processed += 1
                    logger.info(f"    Extracting fields with LLM for receipt {receipt_number}...")
                    
                    # Update progress before LLM call (can be slow)
                    if progress_callback:
                        # Progress: 10% PDF conversion + 30% pages + 60% receipts
                        # Distribute receipt processing across remaining progress
                        receipt_progress = 40 + int((total_receipts_processed / max(estimated_total_receipts, 1)) * 60)
                        progress_callback(receipt_progress, f"Extracting data from receipt {receipt_number} ({total_receipts_processed}/{estimated_total_receipts})...")
                    
                    llm_start = time.time()
                    llm_success = False
                    try:
                        extracted_fields = extract_fields_llm(ocr_text)
                        llm_duration = time.time() - llm_start
                        llm_success = True
                        logger.info(f"[OK] LLM extraction completed in {llm_duration:.2f}s")
                        if llm_duration > 60:
                            logger.warning(f"[WARNING] LLM extraction took {llm_duration:.2f}s (slow)")
                    except Exception as llm_error:
                        llm_duration = time.time() - llm_start
                        logger.error(f"[FAILED] LLM extraction failed after {llm_duration:.2f}s: {str(llm_error)}")
                        logger.exception("LLM error details:")
                        # Continue with empty fields rather than failing completely
                        extracted_fields = {
                            "merchant_name": None,
                            "date": None,
                            "total_amount": None,
                            "tax_amount": None,
                            "subtotal": None,
                            "items": [],
                            "payment_method": None,
                            "address": None,
                            "phone": None,
                            "currency": None,
                            "vat_amount": None,
                            "vat_percentage": None,
                        }
                        logger.warning("[WARNING] Continuing with empty extracted fields due to LLM failure")
                        # Note: We still count this as successful (receipt was processed, just with empty fields)
                    
                    # Post-process tax/VAT extraction (works for any country)
                    # Ensure tax_amount and vat_amount are consistent (they're synonyms)
                    if extracted_fields.get("vat_amount") is not None and extracted_fields.get("tax_amount") is None:
                        extracted_fields["tax_amount"] = extracted_fields["vat_amount"]
                    elif extracted_fields.get("tax_amount") is not None and extracted_fields.get("vat_amount") is None:
                        extracted_fields["vat_amount"] = extracted_fields["tax_amount"]
                    
                    # Calculate/validate VAT percentage and amounts
                    # Try both methods: total includes tax (EU style) and total excludes tax (US style)
                    if extracted_fields.get("total_amount") and extracted_fields.get("tax_amount"):
                        total = float(extracted_fields["total_amount"])
                        tax = float(extracted_fields["tax_amount"])
                        
                        if total > tax > 0:
                            # Method 1: Assume total INCLUDES tax (common in EU)
                            # VAT% = (tax / (total - tax)) * 100
                            calculated_vat_pct_inclusive = (tax / (total - tax)) * 100
                            
                            # Method 2: Assume total EXCLUDES tax (common in US)
                            # VAT% = (tax / total) * 100
                            calculated_vat_pct_exclusive = (tax / total) * 100
                            
                            # Use the method that gives a more reasonable VAT rate (typically 0-30%)
                            # EU rates are usually 9-27%, US rates 0-10%
                            if 5.0 <= calculated_vat_pct_inclusive <= 30.0:
                                calculated_vat_pct = calculated_vat_pct_inclusive
                                # Calculate subtotal if missing
                                if extracted_fields.get("subtotal") is None:
                                    extracted_fields["subtotal"] = round(total - tax, 2)
                            elif 0.0 <= calculated_vat_pct_exclusive <= 15.0:
                                calculated_vat_pct = calculated_vat_pct_exclusive
                                # Calculate total if missing (shouldn't happen, but just in case)
                                if extracted_fields.get("subtotal") is None:
                                    extracted_fields["subtotal"] = round(total, 2)
                            else:
                                # Use inclusive method as default (more common globally)
                                calculated_vat_pct = calculated_vat_pct_inclusive
                                if extracted_fields.get("subtotal") is None:
                                    extracted_fields["subtotal"] = round(total - tax, 2)
                            
                            # If LLM didn't provide vat_percentage, or it's way off, use calculated
                            if extracted_fields.get("vat_percentage") is None:
                                extracted_fields["vat_percentage"] = round(calculated_vat_pct, 1)  # Round to 1 decimal
                            else:
                                llm_vat_pct = float(extracted_fields["vat_percentage"])
                                # If LLM value is more than 5% off, use calculated (more reliable)
                                if abs(llm_vat_pct - calculated_vat_pct) > 5.0:
                                    logger.debug(f"    Correcting VAT percentage: LLM={llm_vat_pct:.1f}%, calculated={calculated_vat_pct:.1f}% (using calculated)")
                                    extracted_fields["vat_percentage"] = round(calculated_vat_pct, 1)  # Round to 1 decimal
                    
                    # Calculate/validate subtotal if still missing
                    if extracted_fields.get("total_amount") and extracted_fields.get("tax_amount") and extracted_fields.get("subtotal") is None:
                        total = float(extracted_fields["total_amount"])
                        tax = float(extracted_fields["tax_amount"])
                        # Default to EU style (total includes tax)
                        extracted_fields["subtotal"] = round(total - tax, 2)
                    
                    # Calculate confidence score based on extraction quality
                    confidence_score = calculate_confidence_score(extracted_fields, llm_success, ocr_text)
                    logger.debug(f"    Calculated confidence score: {confidence_score:.2%} (LLM success: {llm_success}, fields extracted: {sum(1 for k in ['merchant_name', 'date', 'total_amount', 'tax_amount', 'currency'] if extracted_fields.get(k) is not None)}/5)")
                    
                    # Normalize and clean extracted fields
                    extracted_fields = normalize_extracted_fields(extracted_fields)
                    
                    # Add missing field metadata if confidence is high
                    missing_metadata = add_missing_field_metadata(extracted_fields, confidence_score)
                    
                    # Step 5: Save to database
                    
                    # Convert items to JSON string for storage
                    # Also store currency and vat_percentage in metadata
                    items_json = None
                    if extracted_fields.get("items"):
                        items_data = extracted_fields["items"]
                        if isinstance(items_data, list):
                            items_json = json.dumps(items_data)
                        else:
                            items_json = json.dumps(items_data)
                    else:
                        # Create empty items structure with metadata
                        items_json = json.dumps([])
                    
                    # Add metadata to items JSON (currency, vat_percentage_effective, missing_fields)
                    items_data = json.loads(items_json) if items_json else []
                    if isinstance(items_data, list):
                        metadata_obj = {
                            "_metadata": {
                                "currency": extracted_fields.get("currency"),
                                "vat_percentage": extracted_fields.get("vat_percentage_effective"),  # Use effective VAT
                                "missing_fields": missing_metadata
                            }
                        }
                        # Store metadata separately - we'll extract it in response
                        items_json = json.dumps({"items": items_data, "_metadata": metadata_obj["_metadata"]})
                    
                    # Extract VAT breakdown for database storage
                    vat_breakdown_json = None
                    if extracted_fields.get("vat_breakdown"):
                        vat_breakdown_json = extracted_fields["vat_breakdown"]
                    
                    receipt_data = ReceiptCreate(
                        file_id=file_id,
                        receipt_number=receipt_number,
                        merchant_name=extracted_fields.get("merchant_name"),
                        date=extracted_fields.get("date"),
                        total_amount=extracted_fields.get("total_amount"),
                        tax_amount=extracted_fields.get("tax_amount"),
                        subtotal=extracted_fields.get("subtotal"),
                        items=None,  # Will be stored as JSON string
                        payment_method=extracted_fields.get("payment_method"),
                        address=extracted_fields.get("address"),
                        phone=extracted_fields.get("phone"),
                        raw_text=ocr_text,
                        image_path=str(cropped_path),
                        confidence_score=confidence_score
                    )
                    
                    # Create database record
                    db_receipt = Receipt(
                        file_id=receipt_data.file_id,
                        receipt_number=receipt_data.receipt_number,
                        merchant_name=receipt_data.merchant_name,
                        date=receipt_data.date,
                        total_amount=receipt_data.total_amount,
                        tax_amount=receipt_data.tax_amount,
                        subtotal=receipt_data.subtotal,
                        items=items_json,
                        vat_breakdown=vat_breakdown_json,
                        vat_percentage_effective=extracted_fields.get("vat_percentage_effective"),
                        payment_method=receipt_data.payment_method,
                        address=receipt_data.address,
                        phone=receipt_data.phone,
                        raw_text=receipt_data.raw_text,
                        image_path=receipt_data.image_path,
                        confidence_score=receipt_data.confidence_score
                    )
                    
                    db.add(db_receipt)
                    db.commit()
                    db.refresh(db_receipt)
                    
                    # Extract metadata from items JSON
                    items_data = json.loads(db_receipt.items) if db_receipt.items else {}
                    if isinstance(items_data, dict):
                        items_list = items_data.get("items", [])
                        metadata = items_data.get("_metadata", {})
                    else:
                        items_list = items_data if isinstance(items_data, list) else []
                        metadata = {}
                    
                    # Convert to response format
                    receipt_dict = {
                        "id": db_receipt.id,
                        "file_id": db_receipt.file_id,
                        "receipt_number": db_receipt.receipt_number,
                        "merchant_name": db_receipt.merchant_name,
                        "date": db_receipt.date,
                        "total_amount": db_receipt.total_amount,
                        "tax_amount": db_receipt.tax_amount,
                        "subtotal": db_receipt.subtotal,
                        "items": items_list,
                        "vat_breakdown": db_receipt.vat_breakdown if db_receipt.vat_breakdown else [],
                        "vat_percentage_effective": db_receipt.vat_percentage_effective,
                        "payment_method": db_receipt.payment_method,
                        "address": db_receipt.address,
                        "phone": db_receipt.phone,
                        "raw_text": db_receipt.raw_text,
                        "image_path": db_receipt.image_path,
                        "confidence_score": db_receipt.confidence_score,
                        "extraction_date": db_receipt.extraction_date,
                        "currency": metadata.get("currency") or extracted_fields.get("currency"),
                        "vat_percentage": db_receipt.vat_percentage_effective,  # Use effective VAT
                        "missing_fields": metadata.get("missing_fields") or missing_metadata
                    }
                    
                    all_receipts.append(receipt_dict)
                    
                    # Mark as successful
                    receipt_success = True
                    page_stat["successful"] += 1
                    logger.info(f" [OK] Receipt {receipt_idx + 1} successfully processed and saved (ID: {db_receipt.id})")
                    
                except Exception as e:
                    logger.error(f" [ERROR] Error processing receipt {receipt_idx + 1} from page {page_idx + 1}: {str(e)}")
                    logger.exception("Full error traceback:")
                    receipt_rejection_reason = f"Processing error: {str(e)}"
                    page_stat["rejected"] += 1
                    page_stat["rejection_reasons"].append(f"Receipt {receipt_idx + 1}: {receipt_rejection_reason}")
                    continue
            
            # Log page summary
            logger.info(f"  PAGE {page_idx + 1} SUMMARY: {page_stat['detected']} detected, {page_stat['successful']} successful, {page_stat['rejected']} rejected")
            if page_stat["rejection_reasons"]:
                for reason in page_stat["rejection_reasons"]:
                    logger.warning(f"    - {reason}")
            page_stats.append(page_stat)
        
        # Update file status
        uploaded_file.status = "completed"
        db.commit()
        
        pipeline_duration = time.time() - pipeline_start_time
        
        # Final summary
        logger.info("=" * 60)
        logger.info("PIPELINE PROCESSING SUMMARY")
        logger.info("=" * 60)
        total_detected = sum(stat["detected"] for stat in page_stats)
        total_successful = sum(stat["successful"] for stat in page_stats)
        total_rejected = sum(stat["rejected"] for stat in page_stats)
        
        logger.info(f"Total pages processed: {len(image_paths)}")
        logger.info(f"Total receipts detected: {total_detected}")
        logger.info(f"Total receipts successful: {total_successful}")
        logger.info(f"Total receipts rejected: {total_rejected}")
        logger.info(f"Pipeline duration: {pipeline_duration:.2f}s")
        logger.info("")
        
        # Per-page breakdown
        logger.info("Per-page breakdown:")
        for stat in page_stats:
            logger.info(f"  Page {stat['page_number']}: {stat['detected']} detected, {stat['successful']} successful, {stat['rejected']} rejected")
            if stat["rejection_reasons"]:
                for reason in stat["rejection_reasons"]:
                    logger.warning(f"    - {reason}")
        
        logger.info("=" * 60)
        logger.info(f"[OK] Pipeline completed. Extracted {len(all_receipts)} receipt(s) saved to database")
        logger.info("=" * 60)
        
        if progress_callback:
            progress_callback(100, f"Processing completed! Extracted {len(all_receipts)} receipt(s)")
        
        # Calculate detection warning
        detection_warning = False
        if total_detected == 0:
            detection_warning = True
        elif len(image_paths) > 1:
            # Check if more than 1 page has 0 detections
            pages_with_zero = sum(1 for stat in page_stats if stat["detected"] == 0)
            if pages_with_zero > 1:
                detection_warning = True
        
        # Return enhanced response with stats
        return {
            "receipts": all_receipts,
            "file_id": file_id,
            "pages_processed": len(image_paths),
            "receipts_detected": total_detected,
            "receipts_extracted": total_successful,
            "missing_receipts_estimate": total_detected - total_successful,
            "page_stats": page_stats,
            "detection_warning": detection_warning
        }
        
    except Exception as e:
        # Update file status to failed
        uploaded_file.status = "failed"
        db.commit()
        raise Exception(f"Pipeline error: {str(e)}")
