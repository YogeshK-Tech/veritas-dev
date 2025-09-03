from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database setup
DATABASE_URL = "sqlite:///./veritas.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True)  # UUID for file
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    document_type = Column(String, nullable=False)  # 'pdf' or 'excel'
    session_id = Column(String, index=True)  # Group related documents
    upload_date = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="uploaded")  # uploaded, processing, completed, failed

class UploadSession(Base):
    __tablename__ = "upload_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    pdf_count = Column(Integer, default=0)
    excel_count = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    total_size = Column(Integer, default=0)  # bytes
    created_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")  # active, completed, failed

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")

# Database utility functions
def get_document_stats():
    db = SessionLocal()
    try:
        total_docs = db.query(Document).count()
        pdf_count = db.query(Document).filter(Document.document_type == "pdf").count()
        excel_count = db.query(Document).filter(Document.document_type == "excel").count()
        total_sessions = db.query(UploadSession).count()
        
        return {
            "total_documents": total_docs,
            "pdf_documents": pdf_count,
            "excel_documents": excel_count,
            "total_sessions": total_sessions
        }
    finally:
        db.close()

def get_recent_uploads(limit=10):
    db = SessionLocal()
    try:
        documents = db.query(Document).order_by(Document.upload_date.desc()).limit(limit).all()
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "file_size": doc.file_size,
                "upload_date": doc.upload_date.isoformat(),
                "status": doc.processing_status
            }
            for doc in documents
        ]
    finally:
        db.close()