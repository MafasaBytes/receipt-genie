"""
Export endpoints for CSV and Excel.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import pandas as pd
import json

from database import get_db
from models.db_models import Receipt, UploadedFile
from utils.file_manager import ensure_export_dir
from config import settings

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/csv")
async def export_csv(
    file_id: str,
    db: Session = Depends(get_db)
):
    """
    Export receipts to CSV format.
    
    Args:
        file_id: ID of the processed file
        
    Returns:
        CSV file download
    """
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get receipts
    receipts = db.query(Receipt).filter(Receipt.file_id == file_id).order_by(Receipt.receipt_number).all()
    
    if not receipts:
        raise HTTPException(status_code=404, detail="No receipts found for this file")
    
    # Prepare data for DataFrame
    data = []
    for receipt in receipts:
        # Items + metadata are stored as JSON in the items column
        items_raw = json.loads(receipt.items) if receipt.items else {}
        if isinstance(items_raw, dict):
            items_list = items_raw.get("items", [])
            metadata = items_raw.get("_metadata", {})
        else:
            items_list = items_raw if isinstance(items_raw, list) else []
            metadata = {}

        # Human‑readable items string
        def format_item(item: dict) -> str:
            name = item.get("name", "") or ""
            # Prefer line_total, fall back to total
            total = item.get("line_total", item.get("total", 0.0)) or 0.0
            return f"{name} ({total})" if name else str(total)

        items_str = "; ".join([format_item(item) for item in items_list])

        # VAT % – prefer effective percentage when available
        vat_percentage = receipt.vat_percentage_effective
        if vat_percentage is None:
            vat_percentage = metadata.get("vat_percentage")

        # Currency from metadata if present
        currency = metadata.get("currency")

        # Optional VAT breakdown string for richer exports
        vat_breakdown_str = ""
        if receipt.vat_breakdown:
            try:
                breakdown = receipt.vat_breakdown
                vat_parts = []
                for entry in breakdown:
                    rate = entry.get("vat_rate")
                    base = entry.get("base_amount")
                    tax = entry.get("tax_amount")
                    if rate is not None:
                        part = f"{rate}%"
                        details = []
                        if base is not None:
                            details.append(f"base={base}")
                        if tax is not None:
                            details.append(f"tax={tax}")
                        if details:
                            part += f" ({', '.join(details)})"
                        vat_parts.append(part)
                vat_breakdown_str = "; ".join(vat_parts)
            except Exception:
                # Fallback: raw JSON string if something goes wrong
                vat_breakdown_str = json.dumps(receipt.vat_breakdown)

        data.append({
            "Receipt Number": receipt.receipt_number,
            "Store Name": receipt.merchant_name or "",
            "Date": receipt.date or "",
            "Subtotal": receipt.subtotal or 0.0,
            "VAT Amount": receipt.tax_amount or 0.0,
            "VAT %": vat_percentage or 0.0,
            "VAT Breakdown": vat_breakdown_str,
            "Total Amount": receipt.total_amount or 0.0,
            "Currency": currency or "",
            "Payment Method": receipt.payment_method or "",
            "Items": items_str,
            "Address": receipt.address or "",
            "Phone": receipt.phone or "",
            "Confidence Score": receipt.confidence_score or 0.0,
            "Extraction Date": receipt.extraction_date.isoformat() if receipt.extraction_date else ""
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to CSV
    export_dir = ensure_export_dir()
    csv_path = export_dir / f"{file_id}_receipts.csv"
    df.to_csv(csv_path, index=False)
    
    return FileResponse(
        path=str(csv_path),
        filename=f"{uploaded_file.original_filename}_receipts.csv",
        media_type="text/csv"
    )


@router.get("/excel")
async def export_excel(
    file_id: str,
    db: Session = Depends(get_db)
):
    """
    Export receipts to Excel format.
    
    Args:
        file_id: ID of the processed file
        
    Returns:
        Excel file download
    """
    # Verify file exists
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.file_id == file_id).first()
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get receipts
    receipts = db.query(Receipt).filter(Receipt.file_id == file_id).order_by(Receipt.receipt_number).all()
    
    if not receipts:
        raise HTTPException(status_code=404, detail="No receipts found for this file")
    
    # Prepare data for DataFrame (same structure as CSV export)
    data = []
    for receipt in receipts:
        items_raw = json.loads(receipt.items) if receipt.items else {}
        if isinstance(items_raw, dict):
            items_list = items_raw.get("items", [])
            metadata = items_raw.get("_metadata", {})
        else:
            items_list = items_raw if isinstance(items_raw, list) else []
            metadata = {}

        def format_item(item: dict) -> str:
            name = item.get("name", "") or ""
            total = item.get("line_total", item.get("total", 0.0)) or 0.0
            return f"{name} ({total})" if name else str(total)

        items_str = "; ".join([format_item(item) for item in items_list])

        vat_percentage = receipt.vat_percentage_effective
        if vat_percentage is None:
            vat_percentage = metadata.get("vat_percentage")

        currency = metadata.get("currency")

        vat_breakdown_str = ""
        if receipt.vat_breakdown:
            try:
                breakdown = receipt.vat_breakdown
                vat_parts = []
                for entry in breakdown:
                    rate = entry.get("vat_rate")
                    base = entry.get("base_amount")
                    tax = entry.get("tax_amount")
                    if rate is not None:
                        part = f"{rate}%"
                        details = []
                        if base is not None:
                            details.append(f"base={base}")
                        if tax is not None:
                            details.append(f"tax={tax}")
                        if details:
                            part += f" ({', '.join(details)})"
                        vat_parts.append(part)
                vat_breakdown_str = "; ".join(vat_parts)
            except Exception:
                vat_breakdown_str = json.dumps(receipt.vat_breakdown)

        data.append({
            "Receipt Number": receipt.receipt_number,
            "Store Name": receipt.merchant_name or "",
            "Date": receipt.date or "",
            "Subtotal": receipt.subtotal or 0.0,
            "VAT Amount": receipt.tax_amount or 0.0,
            "VAT %": vat_percentage or 0.0,
            "VAT Breakdown": vat_breakdown_str,
            "Total Amount": receipt.total_amount or 0.0,
            "Currency": currency or "",
            "Payment Method": receipt.payment_method or "",
            "Items": items_str,
            "Address": receipt.address or "",
            "Phone": receipt.phone or "",
            "Confidence Score": receipt.confidence_score or 0.0,
            "Extraction Date": receipt.extraction_date.isoformat() if receipt.extraction_date else ""
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel
    export_dir = ensure_export_dir()
    excel_path = export_dir / f"{file_id}_receipts.xlsx"
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Receipts', index=False)
    
    return FileResponse(
        path=str(excel_path),
        filename=f"{uploaded_file.original_filename}_receipts.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

