from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import uuid
import shutil
import jwt
import hashlib
import json
import asyncio
import structlog
import base64
from PIL import Image
import io

# Enhanced imports
from app.services.enhanced_ai_service import enhanced_gemini_service
from decouple import config

# Logging setup
logger = structlog.get_logger()

# Configuration
UPLOAD_DIR = config('UPLOAD_DIR', default='./uploads')
DATABASE_URL = config('DATABASE_URL', default='sqlite:///./veritas_enhanced.db')
SECRET_KEY = config('SECRET_KEY', default='your-secret-key-change-in-production')
ALGORITHM = config('ALGORITHM', default='HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = config('ACCESS_TOKEN_EXPIRE_MINUTES', default=30, cast=int)

# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Authentication utilities
def hash_password(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enhanced Database Models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    document_type = Column(String, nullable=False)
    session_id = Column(String, index=True)
    user_id = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="uploaded")
    extracted_data = Column(JSON, nullable=True, default=None)
    comprehensive_analysis = Column(JSON, nullable=True, default=None)
    extraction_metadata = Column(JSON, nullable=True, default=None)
    processed_date = Column(DateTime, nullable=True, default=None)

class EnhancedUploadSession(Base):
    __tablename__ = "enhanced_upload_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    pdf_document_id = Column(String, nullable=True)
    excel_document_ids = Column(JSON, nullable=True)
    extraction_results = Column(JSON, nullable=True)
    validation_data = Column(JSON, nullable=True)
    validated_pdf_values = Column(JSON, nullable=True, default=None)
    validated_excel_values = Column(JSON, nullable=True, default=None)
    total_files = Column(Integer, default=0)
    total_size = Column(Integer, default=0)
    created_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="analyst")
    created_date = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class DirectAuditSession(Base):
    __tablename__ = "direct_audit_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_session_id = Column(String, unique=True, index=True)
    upload_session_id = Column(String, index=True)
    user_id = Column(String, index=True)
    validated_pdf_values = Column(JSON, nullable=True)
    validated_excel_values = Column(JSON, nullable=True)
    audit_results = Column(JSON, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")
    completion_date = Column(DateTime, nullable=True)

# Initialize database
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Enhanced database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")

# Create default users
def create_default_users():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            demo_user = User(
                user_id=str(uuid.uuid4()),
                username="demo",
                email="demo@veritas.com",
                hashed_password=hash_password("demo123"),
                role="analyst"
            )
            admin_user = User(
                user_id=str(uuid.uuid4()),
                username="admin",
                email="admin@veritas.com", 
                hashed_password=hash_password("admin123"),
                role="admin"
            )
            db.add(demo_user)
            db.add(admin_user)
            db.commit()
            logger.info("Default users created successfully")
    except Exception as e:
        logger.error(f"Error creating users: {e}")
    finally:
        db.close()

create_default_users()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth dependency
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    payload = verify_token(credentials)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

# FastAPI app
app = FastAPI(
    title="Veritas AI Auditor - Direct Validation Edition",
    description="Advanced enterprise presentation validation with direct value validation",
    version="12.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Routes
@app.get("/")
async def root():
    return {
        "message": "Veritas AI Auditor - Direct Validation Edition",
        "version": "12.0.0", 
        "status": "operational",
        "ai_model": "gemini-2.5-pro-direct-validation",
        "features": [
            "comprehensive_gemini_pdf_extraction",
            "comprehensive_excel_extraction", 
            "direct_value_validation",
            "complete_coverage_auditing",
            "no_mapping_bottlenecks",
            "real_time_validation_ui"
        ],
        "demo_credentials": {"username": "demo", "password": "demo123"}
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "veritas-direct-validation",
        "ai_model": "gemini-2.5-pro",
        "ai_enabled": enhanced_gemini_service.ai_enabled,
        "timestamp": datetime.utcnow().isoformat()
    }

# Authentication
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Enhanced authentication with detailed logging"""
    logger.info(f"Login attempt for user: {request.username}")
    
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Failed login attempt for user: {request.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    user.last_login = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(
        data={"sub": user.user_id, "username": user.username, "role": user.role}
    )
    
    logger.info(f"Successful login for user: {request.username}")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    )

@app.get("/api/auth/validate")
async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Validate JWT token and return user info"""
    payload = verify_token(credentials)
    username = payload.get("username")
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"username": user.username, "email": user.email, "role": user.role}

# Enhanced File Upload
@app.post("/api/upload/documents")
async def upload_documents_enhanced(
    files: List[UploadFile] = File(...), 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enhanced document upload with comprehensive validation"""
    logger.info(f"Enhanced upload started by user: {current_user.username}")
    
    # Validate files
    pdf_files = [f for f in files if f.content_type == "application/pdf"]
    excel_files = [f for f in files if f.content_type in [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        "application/vnd.ms-excel"
    ]]
    
    if len(pdf_files) != 1:
        raise HTTPException(status_code=400, detail="Exactly one PDF required")
    
    if len(excel_files) == 0:
        raise HTTPException(status_code=400, detail="At least one Excel file required")
    
    # Create enhanced session
    session_id = str(uuid.uuid4())
    upload_session = EnhancedUploadSession(
        session_id=session_id,
        user_id=current_user.user_id,
        total_files=len(files)
    )
    db.add(upload_session)
    
    # Save files with enhanced metadata
    uploaded_documents = []
    total_size = 0
    
    for file in files:
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{file_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_path)
        total_size += file_size
        
        document = Document(
            file_id=file_id,
            filename=file.filename,
            file_path=file_path,
            content_type=file.content_type,
            file_size=file_size,
            document_type="pdf" if file.content_type == "application/pdf" else "excel",
            session_id=session_id,
            user_id=current_user.user_id,
            processing_status="uploaded"
        )
        db.add(document)
        
        uploaded_documents.append({
            "id": document.file_id,
            "filename": document.filename,
            "file_size": file_size,
            "content_type": document.content_type,
            "document_type": document.document_type,
            "processing_status": document.processing_status
        })
        
        # Update session with document IDs
        if document.document_type == "pdf":
            upload_session.pdf_document_id = file_id
        else:
            excel_ids = upload_session.excel_document_ids or []
            excel_ids.append(file_id)
            upload_session.excel_document_ids = excel_ids
    
    upload_session.total_size = total_size
    upload_session.status = "completed"
    db.commit()
    
    logger.info(f"Enhanced upload completed: {len(uploaded_documents)} files, session: {session_id}")
    
    return {
        "session_id": session_id,
        "documents": uploaded_documents,
        "total_files": len(uploaded_documents),
        "total_size": total_size,
        "uploaded_by": current_user.username,
        "approach": "direct_value_validation",
        "message": f"Successfully uploaded {len(uploaded_documents)} files for direct validation analysis"
    }

# Enhanced Document Processing
@app.post("/api/process/comprehensive/{session_id}")
async def process_documents_comprehensive(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Comprehensive document processing for direct validation"""
    logger.info(f"Starting comprehensive processing for session: {session_id}")
    
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get documents
    pdf_doc = db.query(Document).filter(
        Document.file_id == session.pdf_document_id
    ).first()
    
    excel_docs = db.query(Document).filter(
        Document.file_id.in_(session.excel_document_ids or [])
    ).all()
    
    if not pdf_doc:
        raise HTTPException(status_code=400, detail="PDF document not found")
    
    if not excel_docs:
        raise HTTPException(status_code=400, detail="Excel documents not found")
    
    try:
        # Process PDF with comprehensive extraction
        logger.info(f"Processing PDF: {pdf_doc.filename}")
        pdf_doc.processing_status = "processing"
        db.commit()
        
        pdf_analysis = await enhanced_gemini_service.extract_comprehensive_pdf_data(pdf_doc.file_path)
        
        pdf_doc.comprehensive_analysis = pdf_analysis
        pdf_doc.processing_status = "processed"
        pdf_doc.processed_date = datetime.utcnow()
        
        # Process ALL Excel files comprehensively  
        all_excel_values = []
        excel_analyses = {}
        
        for excel_doc in excel_docs:
            logger.info(f"Processing Excel: {excel_doc.filename}")
            excel_doc.processing_status = "processing"
            db.commit()
            
            excel_analysis = await enhanced_gemini_service.analyze_excel_comprehensive(excel_doc.file_path)
            
            excel_doc.comprehensive_analysis = excel_analysis
            excel_doc.processing_status = "processed"
            excel_doc.processed_date = datetime.utcnow()
            
            excel_analyses[excel_doc.file_id] = excel_analysis
            
            # Collect ALL Excel values for validation
            potential_sources = excel_analysis.get("potential_sources", [])
            for source in potential_sources:
                source["source_file"] = excel_doc.filename
                source["file_id"] = excel_doc.file_id
                all_excel_values.append(source)
        
        # Store comprehensive extraction results
        session.extraction_results = {
            "pdf_analysis": pdf_analysis,
            "excel_analyses": excel_analyses,
            "all_pdf_values": pdf_analysis.get('all_extracted_values', []),
            "all_excel_values": all_excel_values,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "approach": "direct_validation"
        }
        
        # Initialize validated values with extracted values
        session.validated_pdf_values = pdf_analysis.get('all_extracted_values', [])
        session.validated_excel_values = all_excel_values
        
        db.commit()
        
        pdf_count = len(pdf_analysis.get('all_extracted_values', []))
        excel_count = len(all_excel_values)
        
        logger.info(f"Comprehensive processing completed for session: {session_id}")
        logger.info(f"Extracted {pdf_count} PDF values and {excel_count} Excel values for direct validation")
        
        return {
            "session_id": session_id,
            "processing_type": "direct_validation_approach",
            "pdf_results": {
                "filename": pdf_doc.filename,
                "status": "processed",
                "values_extracted": pdf_count,
                "pages_processed": pdf_analysis.get('document_summary', {}).get('total_pages', 0),
                "extraction_quality": pdf_analysis.get('extraction_quality_metrics', {}).get('overall_confidence', 0)
            },
            "excel_results": [
                {
                    "filename": doc.filename,
                    "status": "processed",
                    "values_extracted": len(excel_analyses[doc.file_id].get("potential_sources", [])),
                    "sheets_analyzed": len(excel_analyses[doc.file_id].get("sheet_analyses", []))
                }
                for doc in excel_docs
            ],
            "total_values_for_validation": {
                "pdf_values": pdf_count,
                "excel_values": excel_count,
                "total": pdf_count + excel_count
            },
            "overall_success": True,
            "ready_for_validation": True,
            "approach": "All values will be validated directly - no mapping bottlenecks"
        }
        
    except Exception as e:
        logger.error(f"Comprehensive processing failed for session {session_id}: {e}")
        
        # Update status for failed documents
        pdf_doc.processing_status = "failed"
        for excel_doc in excel_docs:
            excel_doc.processing_status = "failed"
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# Direct Validation Endpoints
@app.get("/api/validation/data/{session_id}")
async def get_validation_data(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive validation data for direct value validation"""
    logger.info(f"Loading validation data for session: {session_id}")
    
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.extraction_results:
        raise HTTPException(status_code=404, detail="No extraction results available. Please process documents first.")
    
    try:
        # Get PDF document for preview generation
        pdf_doc = db.query(Document).filter(
            Document.file_id == session.pdf_document_id
        ).first()
        
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF document not found")
        
        # Generate document preview with page images
        document_preview = await generate_document_preview(pdf_doc.file_path)
        
        # Get extraction results
        extraction_results = session.extraction_results
        
        # Get all PDF and Excel values for validation
        pdf_values = session.validated_pdf_values or extraction_results.get("all_pdf_values", [])
        excel_values = session.validated_excel_values or extraction_results.get("all_excel_values", [])
        
        # Prepare validation data
        validation_data = {
            "session_id": session_id,
            "approach": "direct_value_validation",
            "document_preview": document_preview,
            "pdf_values": pdf_values,
            "excel_values": excel_values,
            "validation_statistics": {
                "total_pdf_values": len(pdf_values),
                "total_excel_values": len(excel_values),
                "total_pages": document_preview.get("total_pages", 0),
                "coverage": "100% - All extracted values available for validation"
            },
            "validation_features": {
                "edit_pdf_values": True,
                "edit_excel_values": True,
                "coordinate_based_highlighting": True,
                "comprehensive_audit": True,
                "ai_model": "gemini-2.5-pro-direct-validation"
            }
        }
        
        # Store validation data in session
        session.validation_data = validation_data
        db.commit()
        
        logger.info(f"Validation data prepared: {len(pdf_values)} PDF values, {len(excel_values)} Excel values, {validation_data['validation_statistics']['total_pages']} pages")
        
        return validation_data
        
    except Exception as e:
        logger.error(f"Failed to prepare validation data for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare validation data: {str(e)}")

async def generate_document_preview(pdf_path: str) -> Dict[str, Any]:
    """Generate document preview with page images for validation UI"""
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Generate high-quality image for preview
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for good quality
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Convert to base64 for frontend
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            pages.append({
                "page_number": page_num + 1,
                "image_data": img_base64,
                "width": pix.width,
                "height": pix.height,
                "format": "png"
            })
        
        doc.close()
        
        return {
            "total_pages": len(pages),
            "pages": pages,
            "preview_quality": "high",
            "coordinate_system": "normalized"
        }
        
    except Exception as e:
        logger.error(f"Document preview generation failed: {e}")
        return {
            "total_pages": 0,
            "pages": [],
            "error": str(e)
        }

@app.post("/api/validation/update-pdf-value/{session_id}")
async def update_pdf_value(
    session_id: str,
    value_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a PDF extracted value"""
    logger.info(f"Updating PDF value for session: {session_id}")
    
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        value_id = value_data.get("value_id")
        updates = value_data.get("updates", {})
        
        if not value_id:
            raise HTTPException(status_code=400, detail="Value ID is required")
        
        # Update PDF value
        pdf_values = session.validated_pdf_values or []
        
        for i, value in enumerate(pdf_values):
            if value.get("id") == value_id:
                # Apply updates
                for key, new_value in updates.items():
                    if key in ["value", "business_context", "data_type"]:
                        if key == "business_context":
                            if "business_context" not in value:
                                value["business_context"] = {}
                            if isinstance(new_value, str):
                                value["business_context"]["semantic_meaning"] = new_value
                            else:
                                value["business_context"].update(new_value)
                        else:
                            value[key] = new_value
                
                # Mark as user modified
                value["user_modified"] = True
                value["modified_by"] = current_user.username
                value["modification_timestamp"] = datetime.utcnow().isoformat()
                
                pdf_values[i] = value
                break
        else:
            raise HTTPException(status_code=404, detail="PDF value not found")
        
        # Update session
        session.validated_pdf_values = pdf_values
        db.commit()
        
        logger.info(f"PDF value {value_id} updated successfully")
        
        return {
            "status": "success",
            "value_id": value_id,
            "updated_fields": list(updates.keys()),
            "message": "PDF value updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update PDF value: {e}")
        raise HTTPException(status_code=500, detail=f"PDF value update failed: {str(e)}")

@app.post("/api/validation/update-excel-value/{session_id}")
async def update_excel_value(
    session_id: str,
    value_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an Excel extracted value"""
    logger.info(f"Updating Excel value for session: {session_id}")
    
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        value_id = value_data.get("value_id")
        updates = value_data.get("updates", {})
        
        if not value_id:
            raise HTTPException(status_code=400, detail="Value ID is required")
        
        # Update Excel value
        excel_values = session.validated_excel_values or []
        
        for i, value in enumerate(excel_values):
            # Use cell_reference + source_file as unique identifier for Excel values
            value_identifier = f"{value.get('source_file', '')}_{value.get('cell_reference', '')}"
            if value_identifier == value_id or value.get("id") == value_id:
                # Apply updates
                for key, new_value in updates.items():
                    if key in ["value", "business_context", "data_type"]:
                        value[key] = new_value
                
                # Mark as user modified
                value["user_modified"] = True
                value["modified_by"] = current_user.username
                value["modification_timestamp"] = datetime.utcnow().isoformat()
                
                excel_values[i] = value
                break
        else:
            raise HTTPException(status_code=404, detail="Excel value not found")
        
        # Update session
        session.validated_excel_values = excel_values
        db.commit()
        
        logger.info(f"Excel value {value_id} updated successfully")
        
        return {
            "status": "success",
            "value_id": value_id,
            "updated_fields": list(updates.keys()),
            "message": "Excel value updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update Excel value: {e}")
        raise HTTPException(status_code=500, detail=f"Excel value update failed: {str(e)}")

@app.post("/api/validation/start-direct-audit/{session_id}")
async def start_direct_audit(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start direct comprehensive audit of all PDF vs all Excel values"""
    logger.info(f"Starting direct comprehensive audit for session: {session_id}")
    
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get validated values
    pdf_values = session.validated_pdf_values or []
    excel_values = session.validated_excel_values or []
    
    if len(pdf_values) == 0:
        raise HTTPException(status_code=400, detail="No PDF values available for audit")
    
    if len(excel_values) == 0:
        raise HTTPException(status_code=400, detail="No Excel values available for audit")
    
    try:
        # Create direct audit session
        audit_session_id = str(uuid.uuid4())
        audit_session = DirectAuditSession(
            audit_session_id=audit_session_id,
            upload_session_id=session_id,
            user_id=current_user.user_id,
            validated_pdf_values=pdf_values,
            validated_excel_values=excel_values,
            status="created"
        )
        
        db.add(audit_session)
        db.commit()
        
        logger.info(f"Direct audit session created: {audit_session_id}")
        logger.info(f"Auditing {len(pdf_values)} PDF values against {len(excel_values)} Excel values")
        
        # Run direct comprehensive audit
        audit_session.status = "running"
        db.commit()
        
        # Use enhanced Gemini service for direct audit
        audit_results = await enhanced_gemini_service.run_direct_comprehensive_audit(
            pdf_values=pdf_values,
            excel_values=excel_values
        )
        
        # Enhanced audit results
        enhanced_audit_results = {
            **audit_results,
            "audit_metadata": {
                "ai_model": "gemini-2.5-pro-direct-validation",
                "audit_type": "direct_comprehensive",
                "audit_timestamp": datetime.utcnow().isoformat(),
                "total_pdf_values_audited": len(pdf_values),
                "total_excel_values_searched": len(excel_values),
                "coverage": "100% - All extracted values audited",
                "user": current_user.username
            }
        }
        
        # Save results
        audit_session.audit_results = enhanced_audit_results
        audit_session.status = "completed"
        audit_session.completion_date = datetime.utcnow()
        db.commit()
        
        summary = audit_results.get("summary", {})
        matched = summary.get("matched", 0)
        total_audited = summary.get("total_values_checked", 0)
        accuracy = summary.get("overall_accuracy", 0)
        
        logger.info(f"Direct comprehensive audit completed: {audit_session_id}")
        logger.info(f"Results: {matched}/{total_audited} values matched, {accuracy:.1f}% accuracy")
        
        return {
            "status": "audit_completed",
            "session_id": session_id,
            "audit_session_id": audit_session_id,
            "audit_results": enhanced_audit_results,
            "redirect_url": f"/audit/{audit_session_id}",
            "message": f"Direct comprehensive audit completed: {matched}/{total_audited} values validated"
        }
        
    except Exception as e:
        # Update audit session status if it exists
        try:
            if 'audit_session' in locals():
                audit_session.status = "failed"
                db.commit()
        except:
            pass
        
        logger.error(f"Failed to start direct audit: {e}")
        raise HTTPException(status_code=500, detail=f"Direct audit failed: {str(e)}")

@app.get("/api/validation/status/{session_id}")
async def get_validation_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get validation status for direct approach"""
    session = db.query(EnhancedUploadSession).filter(
        EnhancedUploadSession.session_id == session_id,
        EnhancedUploadSession.user_id == current_user.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check validation readiness
    has_extraction = bool(session.extraction_results)
    has_validation_data = bool(session.validation_data)
    
    pdf_values = session.validated_pdf_values or []
    excel_values = session.validated_excel_values or []
    
    ready_for_audit = (
        has_extraction and 
        len(pdf_values) > 0 and 
        len(excel_values) > 0
    )
    
    return {
        "session_id": session_id,
        "approach": "direct_value_validation",
        "validation_status": {
            "has_extraction_results": has_extraction,
            "has_validation_data": has_validation_data,
            "total_pdf_values": len(pdf_values),
            "total_excel_values": len(excel_values),
            "ready_for_audit": ready_for_audit,
            "coverage": "100% of extracted values"
        },
        "next_steps": [
            "Review and validate extracted PDF values",
            "Review and validate extracted Excel values", 
            "Start comprehensive direct audit"
        ] if ready_for_audit else [
            "Complete document processing" if not has_extraction else None,
            "Review extracted values" if len(pdf_values) == 0 else None
        ]
    }

# Audit Results
@app.get("/api/audit/results/{audit_session_id}")
async def get_direct_audit_results(
    audit_session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get direct audit results"""
    audit_session = db.query(DirectAuditSession).filter(
        DirectAuditSession.audit_session_id == audit_session_id,
        DirectAuditSession.user_id == current_user.user_id
    ).first()
    
    if not audit_session:
        raise HTTPException(status_code=404, detail="Audit session not found")
    
    return {
        "audit_session_id": audit_session.audit_session_id,
        "upload_session_id": audit_session.upload_session_id,
        "status": audit_session.status,
        "approach": "direct_comprehensive_validation",
        "ai_model": "gemini-2.5-pro-direct-validation",
        "created_date": audit_session.created_date.isoformat(),
        "completion_date": audit_session.completion_date.isoformat() if audit_session.completion_date else None,
        "validated_pdf_values": audit_session.validated_pdf_values,
        "validated_excel_values": audit_session.validated_excel_values,
        "audit_results": audit_session.audit_results
    }

# Statistics and Health
@app.get("/api/documents/stats")
async def get_enhanced_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_docs = db.query(Document).filter(Document.user_id == current_user.user_id).count()
    pdf_count = db.query(Document).filter(
        Document.user_id == current_user.user_id,
        Document.document_type == "pdf"
    ).count()
    excel_count = db.query(Document).filter(
        Document.user_id == current_user.user_id,
        Document.document_type == "excel"
    ).count()
    
    return {
        "user": current_user.username,
        "approach": "direct_value_validation",
        "user_stats": {
            "total_documents": total_docs,
            "pdf_documents": pdf_count,
            "excel_documents": excel_count
        },
        "ai_model": "gemini-2.5-pro-direct-validation",
        "ai_status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)