from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, Boolean
from datetime import datetime
from enum import Enum

from app.database.database import Base

class DocumentType(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"

class AuditStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ValidationStatus(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    FORMATTING_ERROR = "formatting_error"
    UNVERIFIABLE = "unverifiable"

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, nullable=False)
    document_type = Column(String, nullable=False)
    extraction_data = Column(JSON, nullable=True)
    processing_status = Column(String, default="uploaded")
    
class AuditSession(Base):
    __tablename__ = "audit_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String, nullable=False)
    pdf_document_id = Column(Integer, nullable=False)
    excel_document_ids = Column(JSON, nullable=False)  # List of Excel doc IDs
    user_id = Column(String, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default=AuditStatus.PENDING)
    mapping_data = Column(JSON, nullable=True)
    audit_results = Column(JSON, nullable=True)
    completion_date = Column(DateTime, nullable=True)

class ValidationResult(Base):
    __tablename__ = "validation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_session_id = Column(Integer, nullable=False)
    slide_number = Column(Integer, nullable=False)
    extracted_value = Column(String, nullable=False)
    source_sheet = Column(String, nullable=True)
    source_cell = Column(String, nullable=True)
    source_value = Column(String, nullable=True)
    validation_status = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)

class UsageMetrics(Base):
    __tablename__ = "usage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)  # upload, extraction, audit, report
    ai_model_used = Column(String, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)