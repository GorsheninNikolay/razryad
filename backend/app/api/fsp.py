"""FSP integration API - mock OIDC provider and achievements management

Owner: architect
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.security import require_candidate
from app.services import fsp as fsp_service
from app.services.notifications import log_audit
from app.models.models import User


router = APIRouter()


class FspLinkRequest(BaseModel):
    fsp_id: str


class FspMockAuthResponse(BaseModel):
    """Mock OIDC authorization response"""
    fsp_id: str
    verified: bool
    achievements: list


@router.get("/mock-provider/auth")
async def mock_fsp_auth(fsp_id: str):
    """Mock FSP OIDC provider - simulates authorization redirect
    
    In real implementation:
    1. User clicks "Link FSP" 
    2. Redirect to FSP Keycloak with OIDC params
    3. User authenticates at FSP
    4. FSP redirects back with authorization code
    5. Exchange code for tokens + claims
    
    For demo: direct call with fsp_id returns mock claims
    """
    response = fsp_service.mock_oidc_provider(fsp_id)
    
    return {
        "message": "Mock FSP authentication successful",
        "fsp_data": response,
        "note": "In production, this would be OIDC authorization code flow via Keycloak"
    }


@router.post("/link")
async def link_fsp(
    data: FspLinkRequest,
    request: Request,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Link FSP identity to candidate profile
    
    Scenario:
    1. Candidate initiates FSP link
    2. Mock OIDC flow returns fsp_id + achievements
    3. We create FspIdentity and sync achievements
    4. Calculate FSP index per brief §5.3
    """
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        from app.models.models import CandidateProfile
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    # Get mock FSP data
    fsp_data = fsp_service.mock_oidc_provider(data.fsp_id)
    
    if not fsp_data["verified"]:
        raise HTTPException(
            status_code=404,
            detail=f"FSP ID {data.fsp_id} not found in mock registry"
        )
    
    try:
        # Link identity
        fsp_identity = fsp_service.link_fsp_identity(
            db=db,
            candidate_id=user.candidate_profile.id,
            fsp_id=data.fsp_id,
            verified=True
        )
        
        # Sync achievements
        achievements = fsp_service.sync_fsp_achievements(
            db=db,
            fsp_identity_id=fsp_identity.id,
            achievements_data=fsp_data["achievements"]
        )
        
        # Update last sync
        fsp_identity.last_sync_at = fsp_service.datetime.utcnow()
        db.commit()
        
        # Calculate FSP index
        status_data = fsp_service.get_fsp_status(db, user.candidate_profile.id)
        
        # Audit log
        log_audit(
            db=db,
            action="fsp_linked",
            entity_type="fsp_identity",
            entity_id=fsp_identity.id,
            user_id=user.id,
            changes={
                "fsp_id": data.fsp_id,
                "achievements_count": len(achievements),
                "fsp_index": status_data["fsp_index"]
            },
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "message": "FSP identity linked successfully",
            "fsp_id": fsp_identity.fsp_id,
            "achievements_synced": len(achievements),
            "fsp_index": status_data["fsp_index"],
            "status": status_data
        }
        
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/unlink")
async def unlink_fsp(
    request: Request,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Unlink FSP identity from profile"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        from app.models.models import CandidateProfile
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    success = fsp_service.unlink_fsp_identity(db, user.candidate_profile.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="No FSP identity linked")
    
    # Audit log
    log_audit(
        db=db,
        action="fsp_unlinked",
        entity_type="fsp_identity",
        entity_id=user.candidate_profile.id,
        user_id=user.id,
        ip_address=request.client.host if request.client else None
    )
    
    return {"message": "FSP identity unlinked successfully"}


@router.get("/status")
async def get_fsp_status(
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Get FSP status for current candidate
    
    CRITICAL: This endpoint handles the "candidate without FSP history" path
    which TZ evaluates separately (criterion #5).
    
    Returns neutral status if no FSP linked - not an error.
    """
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist (new users without profile)
    if not user.candidate_profile:
        from app.models.models import CandidateProfile
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)  # Refresh to get the newly created profile
    
    status_data = fsp_service.get_fsp_status(db, user.candidate_profile.id)
    
    return status_data


@router.get("/achievements")
async def get_fsp_achievements(
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Get candidate's FSP achievements with details"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        from app.models.models import CandidateProfile
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    from app.models.models import FspIdentity, FspAchievement
    
    fsp_identity = db.query(FspIdentity).filter(
        FspIdentity.candidate_id == user.candidate_profile.id
    ).first()
    
    if not fsp_identity:
        # Candidate without FSP - return empty list, not error
        return {
            "has_fsp": False,
            "achievements": [],
            "message": "No FSP profile linked"
        }
    
    achievements = db.query(FspAchievement).filter(
        FspAchievement.fsp_identity_id == fsp_identity.id
    ).order_by(FspAchievement.event_date.desc()).all()
    
    return {
        "has_fsp": True,
        "fsp_id": fsp_identity.fsp_id,
        "achievements": [
            {
                "id": str(a.id),
                "event_name": a.event_name,
                "event_level": a.event_level,
                "discipline": a.discipline,
                "event_date": a.event_date.isoformat(),
                "place": a.place,
                "participants_count": a.participants_count,
                "role": a.role,
                "team_size": a.team_size,
                "verification_status": a.verification_status,
                "recency_weight": fsp_service.calculate_recency_weight(a.event_date),
                "place_weight": fsp_service.calculate_place_weight(a.place, a.participants_count)
            }
            for a in achievements
        ]
    }


@router.post("/sync")
async def sync_fsp_achievements(
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Manually trigger FSP achievements sync"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        from app.models.models import CandidateProfile
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    from app.models.models import FspIdentity
    
    fsp_identity = db.query(FspIdentity).filter(
        FspIdentity.candidate_id == user.candidate_profile.id
    ).first()
    
    if not fsp_identity:
        raise HTTPException(
            status_code=404,
            detail="No FSP identity linked. Link FSP first."
        )
    
    # Get fresh data from mock provider
    fsp_data = fsp_service.mock_oidc_provider(fsp_identity.fsp_id)
    
    # Sync achievements
    achievements = fsp_service.sync_fsp_achievements(
        db=db,
        fsp_identity_id=fsp_identity.id,
        achievements_data=fsp_data["achievements"]
    )
    
    # Update last sync
    fsp_identity.last_sync_at = fsp_service.datetime.utcnow()
    db.commit()
    
    # Recalculate index
    status_data = fsp_service.get_fsp_status(db, user.candidate_profile.id)
    
    return {
        "message": "Achievements synced successfully",
        "achievements_count": len(achievements),
        "fsp_index": status_data["fsp_index"]
    }
