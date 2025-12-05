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
    price: Optional[float] = None
    total: Optional[float] = None


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
    payment_method: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    raw_text: Optional[str] = None
    image_path: Optional[str] = None
    confidence_score: Optional[float] = None
    extraction_date: Optional[datetime] = None
    
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

