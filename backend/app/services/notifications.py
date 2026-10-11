"""Notifications service - audit logging and in-app notifications

Owner: architect
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.models import Notification, AuditLog


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Notification:
    """Create in-app notification"""
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        action_url=action_url,
        notification_metadata=metadata or {}
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def log_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    changes: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log significant action to audit trail"""
    audit = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def mark_notification_read(db: Session, notification_id: uuid.UUID) -> Notification:
    """Mark notification as read"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification:
        notification.read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def get_user_notifications(
    db: Session,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20
):
    """Get user notifications"""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    
    if unread_only:
        query = query.filter(Notification.read == False)
    
    return query.order_by(Notification.created_at.desc()).limit(limit).all()
