from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer
from typing import List, Dict, Any
import aiofiles
import os
import uuid
import structlog
from datetime import datetime

from app.config import settings
from app.services.pdf_service import pdf_service
from app.services.excel_service import excel_service
from app.services.ai_service import ai_service
from app.database.database import get_db
from app.utils.security import verify_token
from app.utils.metrics import track_operation
import time

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()

@router.post("/documents")
async def upload_documents(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Upload PDF and Excel documents"""
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    try:
        # Verify authentication
        user_data = verify_token(token.credentials)
        user_id = user_data["sub"]
        
        # Validate files
        pdf_files = []
        excel_files = []
        
        from app.models.document import DocumentType
        
        for file in files:
            if file.content_type == "application/pdf":
                pdf_files.append(file)
            elif file.content_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
                excel_files.append(file)
            else:
                # Fixed syntax error: use detail parameter correctly
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
        
        if len(pdf_files) != 1:
            raise HTTPException(status_code=400, detail="Exactly one PDF file is required")
        
        if len(excel_files) == 0:
            raise HTTPException(status_code=400, detail="At least one Excel file is required")
        
        # Process files
        uploaded_documents = []
        
        # Process PDF
        pdf_file = pdf_files[0]
        pdf_doc = await _process_uploaded_file(pdf_file, user_id, DocumentType.PDF, db)
        uploaded_documents.append(pdf_doc)
        
        # Process Excel files
        for excel_file in excel_files:
            excel_doc = await _process_uploaded_file(excel_file, user_id, DocumentType.EXCEL, db)
            uploaded_documents.append(excel_doc)
        
        # Start background processing
        if background_tasks:
            background_tasks.add_task(
                _process_documents_background,
                pdf_doc["id"],
                [doc["id"] for doc in uploaded_documents if doc["document_type"] == DocumentType.EXCEL],
                session_id
            )
        
        latency = (time.time() - start_time) * 1000
        await track_operation("upload", latency, True, session_id)
        
        return {
            "session_id": session_id,
            "documents": uploaded_documents,
            "message": "Files uploaded successfully. Processing started in background."
        }
        
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        await track_operation("upload", latency, False, session_id, str(e))
        logger.error("Upload failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))

async def _process_uploaded_file(file: UploadFile, user_id: str, doc_type, db) -> Dict[str, Any]:
    """Process and save an uploaded file"""
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{file_id}{file_extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Create database record
    from app.models.document import Document
    document = Document(
        filename=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        file_size=len(content),
        user_id=user_id,
        document_type=doc_type,
        processing_status="uploaded"
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "file_size": document.file_size,
        "upload_date": document.upload_date.isoformat(),
        "processing_status": document.processing_status
    }

async def _process_documents_background(pdf_doc_id: int, excel_doc_ids: List[int], session_id: str):
    """Background task to process documents and extract data"""
    try:
        logger.info("Starting background document processing", 
                   pdf_doc_id=pdf_doc_id, 
                   excel_doc_ids=excel_doc_ids,
                   session_id=session_id)
        
        # This would integrate with your database and services
        # Implementation details would depend on your specific database setup
        
    except Exception as e:
        logger.error("Background processing failed", error=str(e), session_id=session_id)

@router.get("/documents/{document_id}/status")
async def get_document_status(
    document_id: int,
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Get processing status of a document"""
    user_data = verify_token(token.credentials)
    
    from app.models.document import Document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_data["sub"]
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "filename": document.filename,
        "processing_status": document.processing_status,
        "extraction_data": document.extraction_data
    }

@router.post("/extract")
async def extract_document_data(
    request: Dict[str, Any],
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Extract data from uploaded documents"""
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    try:
        user_data = verify_token(token.credentials)
        pdf_doc_id = request.get("pdf_document_id")
        excel_doc_ids = request.get("excel_document_ids", [])
        
        # Get documents
        from app.models.document import Document
        pdf_doc = db.query(Document).filter(
            Document.id == pdf_doc_id,
            Document.user_id == user_data["sub"]
        ).first()
        
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF document not found")
        
        # Extract PDF data
        with open(pdf_doc.file_path, 'rb') as f:
            pdf_content = f.read()
        
        pdf_text, pdf_images = await pdf_service.extract_text_and_images(pdf_content)
        pdf_extracted_data = await ai_service.extract_pdf_content(pdf_text, pdf_images)
        
        # Extract Excel data
        excel_extracted_data = {}
        for excel_id in excel_doc_ids:
            excel_doc = db.query(Document).filter(
                Document.id == excel_id,
                Document.user_id == user_data["sub"]
            ).first()
            
            if excel_doc:
                with open(excel_doc.file_path, 'rb') as f:
                    excel_content = f.read()
                
                excel_data = await excel_service.extract_data(excel_content)
                ai_excel_data = await ai_service.extract_excel_content(excel_data)
                excel_extracted_data[excel_doc.filename] = {
                    "document_id": excel_id,
                    "raw_data": excel_data,
                    "ai_analysis": ai_excel_data
                }
        
        # Generate mapping suggestions
        mapping_suggestions = await ai_service.suggest_mappings(pdf_extracted_data, excel_extracted_data)
        
        # Update document records with extraction data
        pdf_doc.extraction_data = pdf_extracted_data
        pdf_doc.processing_status = "extracted"
        
        for excel_id in excel_doc_ids:
            excel_doc = db.query(Document).filter(Document.id == excel_id).first()
            if excel_doc and excel_doc.filename in excel_extracted_data:
                excel_doc.extraction_data = excel_extracted_data[excel_doc.filename]
                excel_doc.processing_status = "extracted"
        
        db.commit()
        
        latency = (time.time() - start_time) * 1000
        await track_operation("extraction", latency, True, session_id)
        
        return {
            "session_id": session_id,
            "pdf_data": pdf_extracted_data,
            "excel_data": excel_extracted_data,
            "mapping_suggestions": mapping_suggestions
        }
        
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        await track_operation("extraction", latency, False, session_id, str(e))
        logger.error("Extraction failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))