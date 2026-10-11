"""Authentication service - email confirmation, login, tokens

Owner: architect
"""
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.models import User, Session as UserSession, Consent, AuditLog


def generate_email_token() -> str:
    """Generate secure email confirmation token"""
    return secrets.token_urlsafe(32)


def create_user(
    db: Session,
    email: str,
    password: str,
    role: str,
    ip_address: Optional[str] = None
) -> Tuple[User, str]:
    """Create new user with email confirmation token
    
    Returns: (user, confirmation_token)
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Create user
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        email_confirmed=False
    )
    db.add(user)
    db.flush()
    
    # Generate confirmation token (stored in audit log for demo)
    token = generate_email_token()
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="user_registered",
        entity_type="user",
        entity_id=user.id,
        changes={"email": email, "role": role, "confirmation_token": token},
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()
    db.refresh(user)
    
    return user, token


def confirm_email(db: Session, token: str) -> User:
    """Confirm email with token"""
    # Find token in audit log (for demo - in production would use separate table)
    # SQLite doesn't support JSONB queries well, so we filter in Python
    audits = db.query(AuditLog).filter(
        AuditLog.action == "user_registered"
    ).all()
    
    audit = None
    for a in audits:
        if a.changes and isinstance(a.changes, dict) and a.changes.get("confirmation_token") == token:
            audit = a
            break
    
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired confirmation token"
        )
    
    # Check if token is still valid (24 hours)
    token_age = datetime.utcnow() - audit.created_at
    if token_age > timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation token expired"
        )
    
    user = db.query(User).filter(User.id == audit.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already confirmed"
        )
    
    user.email_confirmed = True
    user.email_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def create_user_session(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Tuple[str, str]:
    """Create access and refresh tokens, store refresh token session
    
    Returns: (access_token, refresh_token)
    """
    access_token = create_access_token(
        subject=user.email,
        user_id=user.id,
        role=user.role
    )
    
    refresh_token = create_refresh_token(
        subject=user.email,
        user_id=user.id
    )
    
    # Store refresh token session
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_password(refresh_token),  # Hash it for security
        expires_at=datetime.utcnow() + timedelta(seconds=settings.JWT_REFRESH_TTL),
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(session)
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return access_token, refresh_token


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    """Revoke refresh token session"""
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if session:
        session.revoked = True
        db.commit()


def create_consent(
    db: Session,
    user_id: uuid.UUID,
    consent_type: str,
    version: str,
    text_snapshot: str,
    granted: bool,
    ip_address: Optional[str] = None
) -> Consent:
    """Create versioned consent record"""
    consent = Consent(
        user_id=user_id,
        consent_type=consent_type,
        version=version,
        text_snapshot=text_snapshot,
        granted=granted,
        ip_address=ip_address
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent
