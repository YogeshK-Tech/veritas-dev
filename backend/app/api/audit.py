from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from typing import Dict, Any
import structlog
import uuid
import time

from app.services.audit_service import audit_service
from app.models.document import AuditSession, ValidationResult
from app.database.database import get_db
from app.utils.security import verify_token
from app.utils.metrics import track_operation

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()

@router.post("/sessions")
async def create_audit_session(
    request: Dict[str, Any],
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Create a new audit session"""
    try:
        user_data = verify_token(token.credentials)
        
        session = AuditSession(
            session_name=request.get("session_name", f"Audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"),
            pdf_document_id=request["pdf_document_id"],
            excel_document_ids=request["excel_document_ids"],
            user_id=user_data["sub"],
            mapping_data=request.get("mapping_data", {})
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {
            "session_id": session.id,
            "session_name": session.session_name,
            "status": session.status
        }
        
    except Exception as e:
        logger.error("Failed to create audit session", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/run")
async def run_audit(
    session_id: int,
    request: Dict[str, Any],
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Run audit for a session"""
    start_time = time.time()
    operation_session_id = str(uuid.uuid4())
    
    try:
        user_data = verify_token(token.credentials)
        
        # Get session
        session = db.query(AuditSession).filter(
            AuditSession.id == session_id,
            AuditSession.user_id == user_data["sub"]
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Audit session not found")
        
        # Update session status
        session.status = "in_progress"
        db.commit()
        
        # Get PDF and Excel data from the documents
        pdf_data = request.get("pdf_data", {})
        excel_data = request.get("excel_data", {})
        user_mappings = request.get("user_mappings", {})
        
        # Run the audit
        audit_results = await audit_service.run_comprehensive_audit(
            pdf_data=pdf_data,
            excel_data=excel_data,
            user_mappings=user_mappings
        )
        
        # Save results
        session.audit_results = audit_results
        session.status = "completed"
        session.completion_date = datetime.utcnow()
        
        # Save individual validation results
        for result in audit_results["detailed_results"]:
            validation_record = ValidationResult(
                audit_session_id=session.id,
                slide_number=result.get("pdf_slide", 0),
                extracted_value=str(result.get("pdf_value", "")),
                source_sheet=result.get("excel_sheet"),
                source_cell=result.get("excel_cell"),
                source_value=str(result.get("excel_value", "")),
                validation_status=result.get("validation_status"),
                confidence_score=result.get("confidence_score"),
                ai_reasoning=result.get("ai_reasoning")
            )
            db.add(validation_record)
        
        db.commit()
        
        latency = (time.time() - start_time) * 1000
        await track_operation("audit", latency, True, operation_session_id)
        
        return {
            "session_id": session.id,
            "audit_results": audit_results,
            "status": "completed"
        }
        
    except Exception as e:
        # Update session status to failed
        if 'session' in locals():
            session.status = "failed"
            db.commit()
        
        latency = (time.time() - start_time) * 1000
        await track_operation("audit", latency, False, operation_session_id, str(e))
        logger.error("Audit failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_audit_session(
    session_id: int,
    token: str = Depends(security),
    db = Depends(get_db)
):
    """Get audit session details"""
    user_data = verify_token(token.credentials)
    
    session = db.query(AuditSession).filter(
        AuditSession.id == session_id,
        AuditSession.user_id == user_data["sub"]
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Audit session not found")
    
    return {
        "id": session.id,
        "session_name": session.session_name,
        "status": session.status,
        "created_date": session.created_date.isoformat(),
        "completion_date": session.completion_date.isoformat() if session.completion_date else None,
        "audit_results": session.audit_results
    }

@router.get("/sessions")
async def list_audit_sessions(
    token: str = Depends(security),
    db = Depends(get_db)
):
    """List all audit sessions for the user"""
    user_data = verify_token(token.credentials)
    
    sessions = db.query(AuditSession).filter(
        AuditSession.user_id == user_data["sub"]
    ).order_by(AuditSession.created_date.desc()).all()
    
    return {
        "sessions": [
            {
                "id": session.id,
                "session_name": session.session_name,
                "status": session.status,
                "created_date": session.created_date.isoformat(),
                "completion_date": session.completion_date.isoformat() if session.completion_date else None
            }
            for session in sessions
        ]
    }