"""
SQLAlchemy database models.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class UploadedFile(Base):
    """Model for uploaded PDF files."""
    __tablename__ = "uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(255), unique=True, index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="uploaded")  # uploaded, processing, completed, failed
    
    # Relationships
    receipts = relationship("Receipt", back_populates="uploaded_file", cascade="all, delete-orphan")


class Receipt(Base):
    """Model for extracted receipt data."""
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(255), ForeignKey("uploaded_files.file_id"), nullable=False)
    receipt_number = Column(Integer, nullable=False)  # Receipt number in the PDF (1st, 2nd, etc.)
    
    # Extracted fields
    merchant_name = Column(String(255), nullable=True)
    date = Column(String(50), nullable=True)
    total_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    subtotal = Column(Float, nullable=True)
    items = Column(Text, nullable=True)  # JSON string of items
    payment_method = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    raw_text = Column(Text, nullable=True)  # Full OCR text
    
    # Processing metadata
    image_path = Column(String(500), nullable=True)  # Path to cropped receipt image
    confidence_score = Column(Float, nullable=True)  # Detection confidence
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    uploaded_file = relationship("UploadedFile", back_populates="receipts")


class ProcessingJob(Base):
    """Model for tracking background processing jobs."""
    __tablename__ = "processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(255), unique=True, index=True, nullable=False)
    file_id = Column(String(255), ForeignKey("uploaded_files.file_id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

