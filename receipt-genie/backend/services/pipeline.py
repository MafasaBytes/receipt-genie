"""
End-to-end receipt processing pipeline.

PDF path (primary):
    PDF → langchain text extraction per page → LLM → DB
    Falls back to image + OCR for scanned pages with no selectable text.

Image path:
    Image → OCR → LLM → DB   (no contour detection)
"""
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import json
import logging
import time

from config import settings
from services.pdf_text_extractor import extract_text_from_pdf_safe
from services.pdf_utils import pdf_to_images
from services.ocr_engine import run_ocr
from services.llm_extractor import extract_fields_llm, check_ollama_connection
from services.rag_service import retrieve_examples, build_few_shot_block, cross_validate
from services.vector_store import index_receipt
from models.db_models import Receipt, UploadedFile

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
        all_receipts = []
        page_stats = []
        total_pages = 0

        # ---------------------------------------------------------------
        # PDF path: langchain text extraction (primary), OCR fallback
        # ---------------------------------------------------------------
        if is_pdf_file(file_path):
            if progress_callback:
                progress_callback(10, "Extracting text from PDF...")

            logger.info(f"Extracting text from PDF: {file_path}")
            step_start = time.time()

            pages = extract_text_from_pdf_safe(file_path)

            if pages:
                total_pages = len(pages)
                logger.info(f"Extracted text from {total_pages} page(s) in {time.time() - step_start:.2f}s")

                for page in pages:
                    page_num = page["page_number"]
                    page_stat = {"page_number": page_num, "detected": 1, "successful": 0, "rejected": 0, "rejection_reasons": []}

                    if progress_callback:
                        base = 10 + int(((page_num - 1) / max(total_pages, 1)) * 30)
                        progress_callback(base, f"Processing page {page_num}/{total_pages}...")

                    logger.info("=" * 60)
                    logger.info(f"PAGE {page_num}/{total_pages}")

                    if page["has_text"]:
                        ocr_text = page["text"]
                        source_path = str(file_path)
                        logger.info(f"  Text extracted via PDF loader ({len(ocr_text)} chars)")
                    else:
                        # Scanned page – fall back to image + OCR
                        logger.info("  Insufficient selectable text, falling back to OCR")
                        try:
                            images_dir = settings.TEMP_DIR / f"{file_id}_images"
                            images_dir.mkdir(exist_ok=True)
                            image_paths = pdf_to_images(file_path, images_dir)
                            if page_num - 1 < len(image_paths):
                                img_path = image_paths[page_num - 1]
                                ocr_text = run_ocr(img_path)
                                source_path = str(img_path)
                            else:
                                raise ValueError(f"Image for page {page_num} not available")
                        except Exception as ocr_err:
                            logger.error(f"  OCR fallback failed: {ocr_err}")
                            page_stat["rejected"] += 1
                            page_stat["rejection_reasons"].append(f"OCR fallback error: {ocr_err}")
                            page_stats.append(page_stat)
                            continue

                    if not ocr_text or len(ocr_text.strip()) < 10:
                        logger.warning(f"  Skipping page {page_num}: insufficient text ({len(ocr_text) if ocr_text else 0} chars)")
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append("Insufficient text")
                        page_stats.append(page_stat)
                        continue

                    receipt_result = _extract_single_receipt(
                        ocr_text=ocr_text,
                        source_path=source_path,
                        file_id=file_id,
                        receipt_number=len(all_receipts) + 1,
                        db=db,
                        progress_callback=progress_callback,
                        total_pages=total_pages,
                        current_page=page_num,
                    )

                    if receipt_result:
                        all_receipts.append(receipt_result)
                        page_stat["successful"] += 1
                    else:
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append("LLM extraction failed")

                    page_stats.append(page_stat)
            else:
                # langchain extraction failed entirely – fall back to OCR for all pages
                logger.warning("langchain PDF extraction failed, falling back to full OCR pipeline")
                images_dir = settings.TEMP_DIR / f"{file_id}_images"
                images_dir.mkdir(exist_ok=True)
                image_paths = pdf_to_images(file_path, images_dir)
                total_pages = len(image_paths)
                if not image_paths:
                    raise ValueError("No pages extracted from PDF")

                for page_idx, img_path in enumerate(image_paths):
                    page_num = page_idx + 1
                    page_stat = {"page_number": page_num, "detected": 1, "successful": 0, "rejected": 0, "rejection_reasons": []}

                    if progress_callback:
                        base = 10 + int((page_idx / max(total_pages, 1)) * 30)
                        progress_callback(base, f"OCR page {page_num}/{total_pages}...")

                    try:
                        ocr_text = run_ocr(img_path)
                    except Exception as ocr_err:
                        logger.error(f"  OCR failed on page {page_num}: {ocr_err}")
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append(f"OCR error: {ocr_err}")
                        page_stats.append(page_stat)
                        continue

                    if not ocr_text or len(ocr_text.strip()) < 10:
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append("Insufficient OCR text")
                        page_stats.append(page_stat)
                        continue

                    receipt_result = _extract_single_receipt(
                        ocr_text=ocr_text,
                        source_path=str(img_path),
                        file_id=file_id,
                        receipt_number=len(all_receipts) + 1,
                        db=db,
                        progress_callback=progress_callback,
                        total_pages=total_pages,
                        current_page=page_num,
                    )
                    if receipt_result:
                        all_receipts.append(receipt_result)
                        page_stat["successful"] += 1
                    else:
                        page_stat["rejected"] += 1
                        page_stat["rejection_reasons"].append("LLM extraction failed")

                    page_stats.append(page_stat)

        # ---------------------------------------------------------------
        # Image path: OCR the full image (no contour detection)
        # ---------------------------------------------------------------
        elif is_image_file(file_path):
            total_pages = 1
            if progress_callback:
                progress_callback(10, "Processing image file...")

            logger.info(f"Processing image file: {file_path}")
            page_stat = {"page_number": 1, "detected": 1, "successful": 0, "rejected": 0, "rejection_reasons": []}

            images_dir = settings.TEMP_DIR / f"{file_id}_images"
            images_dir.mkdir(exist_ok=True)
            import shutil
            temp_image_path = images_dir / f"{file_id}_page_1{file_path.suffix}"
            if not temp_image_path.exists():
                shutil.copy2(file_path, temp_image_path)

            try:
                ocr_text = run_ocr(temp_image_path)
            except Exception as ocr_err:
                logger.error(f"OCR failed: {ocr_err}")
                page_stat["rejected"] += 1
                page_stat["rejection_reasons"].append(f"OCR error: {ocr_err}")
                page_stats.append(page_stat)
                ocr_text = None

            if ocr_text and len(ocr_text.strip()) >= 10:
                receipt_result = _extract_single_receipt(
                    ocr_text=ocr_text,
                    source_path=str(temp_image_path),
                    file_id=file_id,
                    receipt_number=1,
                    db=db,
                    progress_callback=progress_callback,
                    total_pages=1,
                    current_page=1,
                )
                if receipt_result:
                    all_receipts.append(receipt_result)
                    page_stat["successful"] += 1
                else:
                    page_stat["rejected"] += 1
                    page_stat["rejection_reasons"].append("LLM extraction failed")
            elif ocr_text is not None:
                page_stat["rejected"] += 1
                page_stat["rejection_reasons"].append("Insufficient OCR text")

            page_stats.append(page_stat)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}. Supported: PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP")

        # ---------------------------------------------------------------
        # Wrap-up
        # ---------------------------------------------------------------
        uploaded_file.status = "completed"
        db.commit()

        pipeline_duration = time.time() - pipeline_start_time

        total_detected = sum(s["detected"] for s in page_stats)
        total_successful = sum(s["successful"] for s in page_stats)
        total_rejected = sum(s["rejected"] for s in page_stats)

        logger.info("=" * 60)
        logger.info("PIPELINE PROCESSING SUMMARY")
        logger.info(f"  Pages: {total_pages} | Detected: {total_detected} | OK: {total_successful} | Rejected: {total_rejected}")
        logger.info(f"  Duration: {pipeline_duration:.2f}s")
        for stat in page_stats:
            logger.info(f"  Page {stat['page_number']}: {stat['successful']} OK, {stat['rejected']} rejected")
            for r in stat.get("rejection_reasons", []):
                logger.warning(f"    - {r}")
        logger.info("=" * 60)

        if progress_callback:
            progress_callback(100, f"Completed! Extracted {len(all_receipts)} receipt(s)")

        return {
            "receipts": all_receipts,
            "file_id": file_id,
            "pages_processed": total_pages,
            "receipts_detected": total_detected,
            "receipts_extracted": total_successful,
            "missing_receipts_estimate": total_detected - total_successful,
            "page_stats": page_stats,
            "detection_warning": total_detected == 0,
        }

    except Exception as e:
        uploaded_file.status = "failed"
        db.commit()
        raise Exception(f"Pipeline error: {str(e)}")


def _extract_single_receipt(
    ocr_text: str,
    source_path: str,
    file_id: str,
    receipt_number: int,
    db: Session,
    progress_callback=None,
    total_pages: int = 1,
    current_page: int = 1,
) -> Dict[str, Any] | None:
    """
    Run RAG retrieval → LLM extraction → post-processing → DB save for a
    single receipt text.  Returns the receipt dict or None on failure.
    """
    # RAG retrieval
    rag_examples_block = ""
    rag_matches = []
    try:
        if settings.RAG_ENABLED:
            rag_matches = retrieve_examples(ocr_text)
            if rag_matches:
                rag_examples_block = build_few_shot_block(rag_matches)
                logger.info(
                    f"  RAG: {len(rag_matches)} similar receipt(s) "
                    f"(best sim={rag_matches[0]['similarity']:.2f})"
                )
            else:
                logger.info("  RAG: no similar receipts found")
    except Exception as rag_err:
        logger.warning(f"  RAG retrieval failed (non-fatal): {rag_err}")

    # LLM extraction
    if progress_callback:
        pct = 40 + int((current_page / max(total_pages, 1)) * 50)
        progress_callback(pct, f"Extracting receipt {receipt_number}...")

    llm_start = time.time()
    llm_success = False
    try:
        extracted_fields = extract_fields_llm(ocr_text, rag_examples_block=rag_examples_block)
        llm_success = True
        logger.info(f"  LLM extraction OK in {time.time() - llm_start:.2f}s")
    except Exception as llm_error:
        logger.error(f"  LLM extraction failed after {time.time() - llm_start:.2f}s: {llm_error}")
        extracted_fields = {
            "merchant_name": None, "date": None, "total_amount": None,
            "tax_amount": None, "subtotal": None, "items": [],
            "payment_method": None, "address": None, "phone": None,
            "currency": None, "vat_amount": None, "vat_percentage": None,
        }

    # RAG cross-validation
    if rag_matches and llm_success:
        try:
            extracted_fields = cross_validate(extracted_fields, rag_matches)
            for w in extracted_fields.pop("_rag_warnings", []):
                logger.info(f"  RAG validation: {w}")
        except Exception as cv_err:
            logger.warning(f"  RAG cross-validation failed (non-fatal): {cv_err}")

    # VAT/tax consistency
    if extracted_fields.get("vat_amount") is not None and extracted_fields.get("tax_amount") is None:
        extracted_fields["tax_amount"] = extracted_fields["vat_amount"]
    elif extracted_fields.get("tax_amount") is not None and extracted_fields.get("vat_amount") is None:
        extracted_fields["vat_amount"] = extracted_fields["tax_amount"]

    _compute_vat(extracted_fields)

    if extracted_fields.get("total_amount") and extracted_fields.get("tax_amount") and extracted_fields.get("subtotal") is None:
        total = float(extracted_fields["total_amount"])
        tax = float(extracted_fields["tax_amount"])
        extracted_fields["subtotal"] = round(total - tax, 2)

    confidence_score = calculate_confidence_score(extracted_fields, llm_success, ocr_text)
    extracted_fields = normalize_extracted_fields(extracted_fields)
    missing_metadata = add_missing_field_metadata(extracted_fields, confidence_score)

    # Build items JSON with metadata
    items_list = extracted_fields.get("items") or []
    if not isinstance(items_list, list):
        items_list = []
    items_json = json.dumps({
        "items": items_list,
        "_metadata": {
            "currency": extracted_fields.get("currency"),
            "vat_percentage": extracted_fields.get("vat_percentage_effective"),
            "missing_fields": missing_metadata,
        },
    })

    vat_breakdown_json = extracted_fields.get("vat_breakdown") or None

    db_receipt = Receipt(
        file_id=file_id,
        receipt_number=receipt_number,
        merchant_name=extracted_fields.get("merchant_name"),
        date=extracted_fields.get("date"),
        total_amount=extracted_fields.get("total_amount"),
        tax_amount=extracted_fields.get("tax_amount"),
        subtotal=extracted_fields.get("subtotal"),
        items=items_json,
        vat_breakdown=vat_breakdown_json,
        vat_percentage_effective=extracted_fields.get("vat_percentage_effective"),
        payment_method=extracted_fields.get("payment_method"),
        address=extracted_fields.get("address"),
        phone=extracted_fields.get("phone"),
        raw_text=ocr_text,
        image_path=source_path,
        confidence_score=confidence_score,
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    # Vector-store indexing
    if settings.RAG_ENABLED and llm_success:
        try:
            index_receipt(
                receipt_id=db_receipt.id,
                ocr_text=ocr_text,
                extracted_fields=extracted_fields,
                is_user_corrected=False,
            )
        except Exception as idx_err:
            logger.warning(f"  Vector store indexing failed (non-fatal): {idx_err}")

    logger.info(f"  Receipt {receipt_number} saved (ID: {db_receipt.id}, confidence: {confidence_score:.0%})")

    stored = json.loads(db_receipt.items) if db_receipt.items else {}
    meta = stored.get("_metadata", {}) if isinstance(stored, dict) else {}
    items_out = stored.get("items", []) if isinstance(stored, dict) else (stored if isinstance(stored, list) else [])

    return {
        "id": db_receipt.id,
        "file_id": db_receipt.file_id,
        "receipt_number": db_receipt.receipt_number,
        "merchant_name": db_receipt.merchant_name,
        "date": db_receipt.date,
        "total_amount": db_receipt.total_amount,
        "tax_amount": db_receipt.tax_amount,
        "subtotal": db_receipt.subtotal,
        "items": items_out,
        "vat_breakdown": db_receipt.vat_breakdown or [],
        "vat_percentage_effective": db_receipt.vat_percentage_effective,
        "payment_method": db_receipt.payment_method,
        "address": db_receipt.address,
        "phone": db_receipt.phone,
        "raw_text": db_receipt.raw_text,
        "image_path": db_receipt.image_path,
        "confidence_score": db_receipt.confidence_score,
        "extraction_date": db_receipt.extraction_date,
        "currency": meta.get("currency") or extracted_fields.get("currency"),
        "vat_percentage": db_receipt.vat_percentage_effective,
        "missing_fields": meta.get("missing_fields") or missing_metadata,
    }


def _compute_vat(extracted_fields: Dict[str, Any]) -> None:
    """Compute/validate VAT percentage from total and tax amounts in-place."""
    if not (extracted_fields.get("total_amount") and extracted_fields.get("tax_amount")):
        return
    total = float(extracted_fields["total_amount"])
    tax = float(extracted_fields["tax_amount"])
    if not (total > tax > 0):
        return

    inclusive = (tax / (total - tax)) * 100
    exclusive = (tax / total) * 100

    if 5.0 <= inclusive <= 30.0:
        calc = inclusive
        if extracted_fields.get("subtotal") is None:
            extracted_fields["subtotal"] = round(total - tax, 2)
    elif 0.0 <= exclusive <= 15.0:
        calc = exclusive
        if extracted_fields.get("subtotal") is None:
            extracted_fields["subtotal"] = round(total, 2)
    else:
        calc = inclusive
        if extracted_fields.get("subtotal") is None:
            extracted_fields["subtotal"] = round(total - tax, 2)

    if extracted_fields.get("vat_percentage") is None:
        extracted_fields["vat_percentage"] = round(calc, 1)
    else:
        llm_val = float(extracted_fields["vat_percentage"])
        if abs(llm_val - calc) > 5.0:
            extracted_fields["vat_percentage"] = round(calc, 1)
