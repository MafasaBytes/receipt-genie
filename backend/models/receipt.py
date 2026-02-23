"""
Pydantic schemas for receipt data validation and serialization.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ReceiptItem(BaseModel):
    """Schema for a single receipt item."""
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    vat_rate: Optional[float] = None
    # Legacy fields for backward compatibility
    price: Optional[float] = None
    total: Optional[float] = None


class VATBreakdownEntry(BaseModel):
    """Schema for a VAT breakdown entry."""
    vat_rate: float
    tax_amount: Optional[float] = None
    base_amount: Optional[float] = None


class ReceiptCreate(BaseModel):
    """Schema for creating a receipt record."""
    file_id: str
    receipt_number: int
    merchant_name: Optional[str] = None
    date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    items: Optional[List[ReceiptItem]] = None
    payment_method: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    raw_text: Optional[str] = None
    image_path: Optional[str] = None
    confidence_score: Optional[float] = None


class ReceiptResponse(BaseModel):
    """Schema for receipt API responses."""
    id: int
    file_id: str
    receipt_number: int
    merchant_name: Optional[str] = None
    date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    items: Optional[List[Dict[str, Any]]] = None
    vat_breakdown: Optional[List[Dict[str, Any]]] = None
    vat_percentage_effective: Optional[float] = None
    payment_method: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    raw_text: Optional[str] = None
    image_path: Optional[str] = None
    confidence_score: Optional[float] = None
    extraction_date: Optional[datetime] = None
    currency: Optional[str] = None
    vat_percentage: Optional[float] = None  # Legacy field, maps to vat_percentage_effective
    missing_fields: Optional[Dict[str, Any]] = None  # Metadata for missing fields
    
    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    """Schema for file upload response."""
    file_id: str
    filename: str
    file_size: int
    message: str


class ProcessResponse(BaseModel):
    """Schema for processing response."""
    job_id: str
    file_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Schema for job status response."""
    job_id: str
    file_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ReceiptListResponse(BaseModel):
    """Schema for list of receipts response."""
    file_id: str
    receipts: List[ReceiptResponse]
    total: int


class PageStat(BaseModel):
    """Schema for per-page statistics."""
    page_number: int
    detected: int
    successful: int
    rejected: int
    rejection_reasons: List[str] = []


class EnhancedReceiptListResponse(BaseModel):
    """Enhanced schema for receipt list with processing stats."""
    file_id: str
    pages_processed: int
    receipts_detected: int
    receipts_extracted: int
    missing_receipts_estimate: int
    page_stats: List[PageStat]
    detection_warning: bool
    receipts: List[ReceiptResponse]


class ReceiptUpdate(BaseModel):
    """Schema for updating receipt fields."""
    merchant_name: Optional[str] = None
    date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    items: Optional[List[Dict[str, Any]]] = None
    vat_breakdown: Optional[List[Dict[str, Any]]] = None
    vat_percentage: Optional[float] = None
    currency: Optional[str] = None

