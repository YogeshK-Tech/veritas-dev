from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any
import structlog
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.utils.security import create_access_token, verify_password, get_password_hash
from app.database.database import get_db
from app.models.document import User
from sqlalchemy.orm import Session

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mock users for development - replace with database integration
MOCK_USERS = {
    "demo": {
        "username": "demo",
        "email": "demo@veritas.com",
        "hashed_password": get_password_hash("demo123"),
        "role": "analyst"
    },
    "admin": {
        "username": "admin", 
        "email": "admin@veritas.com",
        "hashed_password": get_password_hash("admin123"),
        "role": "administrator"
    }
}

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return access token"""
    try:
        user = MOCK_USERS.get(request.username)
        
        if not user or not verify_password(request.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(
            data={"sub": user["username"], "email": user["email"], "role": user["role"]}
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        )
        
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(status_code=500, detail="Login failed")

@router.get("/validate")
async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return user info"""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user = MOCK_USERS.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
            
        return {
            "username": user["username"],
            "email": user["email"], 
            "role": user["role"]
        }
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/logout")
async def logout():
    """Logout endpoint (token invalidation handled client-side)"""
    return {"message": "Logged out successfully"}