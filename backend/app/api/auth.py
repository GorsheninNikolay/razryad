"""Authentication API router - owner: architect

Handles: registration, email confirmation, login, token refresh, logout
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.core.security import get_current_user, decode_token
from app.services import auth as auth_service


router = APIRouter()


# Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    role: str = Field(pattern="^(candidate|employer)$")


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    role: str
    message: str
    confirmation_link: Optional[str] = None  # Only in DEV_MODE


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class ConfirmEmailRequest(BaseModel):
    token: str


class RefreshRequest(BaseModel):
    refresh_token: str


# Endpoints
@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register new user (candidate or employer)
    
    Email confirmation required. In DEV_MODE, confirmation link is returned in response.
    """
    ip_address = request.client.host if request.client else None
    
    user, token = auth_service.create_user(
        db=db,
        email=data.email,
        password=data.password,
        role=data.role,
        ip_address=ip_address
    )
    
    # Generate confirmation link
    confirmation_link = f"http://localhost:8000/api/v1/auth/confirm-email?token={token}"
    
    response = RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        message="Registration successful. Please check your email to confirm your account."
    )
    
    # In DEV_MODE, include link in response and print to console
    if settings.DEV_MODE:
        response.confirmation_link = confirmation_link
        print(f"\n{'='*60}")
        print(f"📧 EMAIL CONFIRMATION LINK (DEV MODE)")
        print(f"{'='*60}")
        print(f"Email: {user.email}")
        print(f"Link:  {confirmation_link}")
        print(f"{'='*60}\n")
    
    return response


@router.post("/confirm-email")
async def confirm_email(
    data: ConfirmEmailRequest,
    db: Session = Depends(get_db)
):
    """Confirm email address with token"""
    user = auth_service.confirm_email(db=db, token=data.token)
    
    return {
        "message": "Email confirmed successfully",
        "email": user.email,
        "user_id": str(user.id)
    }


@router.get("/confirm-email")
async def confirm_email_get(
    token: str,
    db: Session = Depends(get_db)
):
    """Confirm email via GET (for email links)"""
    user = auth_service.confirm_email(db=db, token=token)
    
    # In production, would redirect to frontend success page
    return {
        "message": "Email confirmed successfully! You can now log in.",
        "email": user.email
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login and get access/refresh tokens"""
    user = auth_service.authenticate_user(db=db, email=data.email, password=data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not confirmed. Please check your email."
        )
    
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    access_token, refresh_token = auth_service.create_user_session(
        db=db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "email_confirmed": user.email_confirmed
        }
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    data: RefreshRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        payload = decode_token(data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        from app.models.models import User
        import uuid
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        access_token, new_refresh_token = auth_service.create_user_session(
            db=db,
            user=user
        )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user={
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "email_confirmed": user.email_confirmed
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout (client should discard tokens)"""
    return {"message": "Logged out successfully"}
