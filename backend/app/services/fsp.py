"""FSP integration service - mock OIDC provider and achievements

Owner: architect
Per brief §5.3: level, place, recency (24mo half-life), discipline-specialization match
"""
import uuid
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.models import (
    FspIdentity, FspAchievement, CandidateProfile, Specialization
)


# Mock FSP achievement data for demo
MOCK_FSP_ACHIEVEMENTS = {
    "FSP001": [
        {
            "event_name": "Всероссийская олимпиада по программированию",
            "event_level": "national",
            "discipline": "algorithms",
            "event_date": "2024-03-15",
            "place": 2,
            "participants_count": 150,
            "role": "participant",
            "verification_status": "verified"
        },
        {
            "event_name": "Хакатон «Цифровой прорыв»",
            "event_level": "national",
            "discipline": "product",
            "event_date": "2023-11-20",
            "place": 1,
            "team_size": 4,
            "role": "captain",
            "verification_status": "verified"
        }
    ],
    "FSP002": [
        {
            "event_name": "ML Cup 2024",
            "event_level": "international",
            "discipline": "ml",
            "event_date": "2024-05-10",
            "place": 5,
            "participants_count": 300,
            "role": "participant",
            "verification_status": "verified"
        }
    ]
}


# Discipline to specialization mapping (per brief §5.3)
DISCIPLINE_SPECIALIZATION_WEIGHTS = {
    "algorithms": {
        "backend": 0.9,
        "frontend": 0.5,
        "mobile": 0.6,
        "data-eng": 0.7,
        "ml": 0.8,
        "devops": 0.3,
        "qa": 0.4,
        "embedded": 0.7
    },
    "ml": {
        "ml": 1.0,
        "data-eng": 0.7,
        "backend": 0.5,
        "analytics": 0.6
    },
    "security": {
        "infosec": 1.0,
        "backend": 0.5,
        "devops": 0.6
    },
    "product": {
        "frontend": 0.6,
        "mobile": 0.6,
        "backend": 0.4,
        "analytics": 0.7
    }
}


def calculate_recency_weight(event_date: datetime, halflife_months: int = 24) -> float:
    """Calculate recency weight with exponential decay (half-life 24 months per brief)"""
    months_ago = (datetime.utcnow() - event_date).days / 30.44
    decay_rate = math.log(2) / halflife_months
    return math.exp(-decay_rate * months_ago)


def calculate_place_weight(place: Optional[int], participants_count: Optional[int]) -> float:
    """Calculate weight based on place and participants"""
    if place is None:
        return 0.5  # Participation
    
    if place == 1:
        return 1.0
    elif place == 2:
        return 0.85
    elif place == 3:
        return 0.75
    elif place <= 10:
        return 0.6
    else:
        if participants_count:
            percentile = 1 - (place / participants_count)
            return max(0.3, percentile)
        return 0.3


def calculate_level_weight(level: str) -> float:
    """Calculate weight based on event level"""
    weights = {
        "international": 1.0,
        "national": 0.85,
        "regional": 0.6,
        "university": 0.4,
        "corporate": 0.5
    }
    return weights.get(level, 0.5)


def calculate_fsp_index(
    achievements: List[FspAchievement],
    specialization_code: Optional[str] = None
) -> float:
    """Calculate FSP index per brief §5.3
    
    Formula: Σ (level_weight × place_weight × recency_weight × discipline_fit)
    Only verified achievements get full weight, self_declared get 0
    """
    if not achievements:
        return 0.0
    
    total = 0.0
    
    for ach in achievements:
        # Only verified achievements count (per brief)
        if ach.verification_status != "verified":
            continue
        
        # Level weight
        level_w = calculate_level_weight(ach.event_level)
        
        # Place weight
        place_w = calculate_place_weight(ach.place, ach.participants_count)
        
        # Recency weight (24 month half-life per brief §5.3)
        recency_w = calculate_recency_weight(ach.event_date, halflife_months=24)
        
        # Discipline-specialization fit
        discipline_fit = 1.0  # Default if no specialization specified
        if specialization_code and ach.discipline:
            weights = DISCIPLINE_SPECIALIZATION_WEIGHTS.get(ach.discipline, {})
            discipline_fit = weights.get(specialization_code, 0.3)
        
        # Calculate contribution
        contribution = level_w * place_w * recency_w * discipline_fit
        total += contribution
    
    return round(total, 3)


def mock_oidc_provider(fsp_id: str) -> Dict[str, Any]:
    """Mock FSP OIDC provider response
    
    In real implementation, this would redirect to FSP Keycloak,
    handle OIDC flow, and return verified claims.
    For demo, we simulate the return from authorization code flow.
    """
    achievements = MOCK_FSP_ACHIEVEMENTS.get(fsp_id, [])
    
    return {
        "fsp_id": fsp_id,
        "verified": bool(achievements),
        "achievements": achievements,
        "fsp_rating": sum(a.get("place", 0) for a in achievements) if achievements else None
    }


def link_fsp_identity(
    db: Session,
    candidate_id: uuid.UUID,
    fsp_id: str,
    verified: bool = True
) -> FspIdentity:
    """Link FSP identity to candidate profile"""
    # Check if already linked
    existing = db.query(FspIdentity).filter(
        FspIdentity.fsp_id == fsp_id
    ).first()
    
    if existing:
        raise ValueError("FSP ID already linked to another account")
    
    # Create FSP identity
    fsp_identity = FspIdentity(
        candidate_id=candidate_id,
        fsp_id=fsp_id,
        verified=verified,
        verified_at=datetime.utcnow() if verified else None
    )
    db.add(fsp_identity)
    db.commit()
    db.refresh(fsp_identity)
    
    return fsp_identity


def sync_fsp_achievements(
    db: Session,
    fsp_identity_id: uuid.UUID,
    achievements_data: List[Dict[str, Any]]
) -> List[FspAchievement]:
    """Sync FSP achievements from mock provider"""
    # Clear existing achievements
    db.query(FspAchievement).filter(
        FspAchievement.fsp_identity_id == fsp_identity_id
    ).delete()
    
    achievements = []
    for data in achievements_data:
        achievement = FspAchievement(
            fsp_identity_id=fsp_identity_id,
            event_name=data["event_name"],
            event_level=data["event_level"],
            discipline=data["discipline"],
            event_date=datetime.fromisoformat(data["event_date"]),
            place=data.get("place"),
            participants_count=data.get("participants_count"),
            role=data.get("role", "participant"),
            team_size=data.get("team_size"),
            verification_status=data.get("verification_status", "verified")
        )
        db.add(achievement)
        achievements.append(achievement)
    
    db.commit()
    return achievements


def unlink_fsp_identity(db: Session, candidate_id: uuid.UUID) -> bool:
    """Unlink FSP identity from candidate"""
    fsp_identity = db.query(FspIdentity).filter(
        FspIdentity.candidate_id == candidate_id
    ).first()
    
    if not fsp_identity:
        return False
    
    # Delete achievements
    db.query(FspAchievement).filter(
        FspAchievement.fsp_identity_id == fsp_identity.id
    ).delete()
    
    # Delete identity
    db.delete(fsp_identity)
    db.commit()
    
    return True


def get_fsp_status(db: Session, candidate_id: uuid.UUID) -> Dict[str, Any]:
    """Get FSP status for candidate
    
    Returns neutral status if no FSP - this is the "candidate without FSP history" path
    that TZ evaluates separately (criterion #5)
    """
    fsp_identity = db.query(FspIdentity).filter(
        FspIdentity.candidate_id == candidate_id
    ).first()
    
    if not fsp_identity:
        # Candidate without FSP history - neutral status, not an error
        return {
            "has_fsp": False,
            "fsp_id": None,
            "verified": None,
            "achievements_count": 0,
            "fsp_index": 0.0,
            "message": "FSP profile not linked. You can link it anytime to showcase your achievements."
        }
    
    # Get achievements
    achievements = db.query(FspAchievement).filter(
        FspAchievement.fsp_identity_id == fsp_identity.id
    ).all()
    
    # Get candidate's specialization for discipline matching
    profile = db.query(CandidateProfile).filter(
        CandidateProfile.id == candidate_id
    ).first()
    
    specialization_code = None
    if profile and profile.category_assignment:
        spec = db.query(Specialization).filter(
            Specialization.id == profile.category_assignment.specialization_id
        ).first()
        if spec:
            specialization_code = spec.code
    
    # Calculate FSP index
    fsp_index = calculate_fsp_index(achievements, specialization_code)
    
    return {
        "has_fsp": True,
        "fsp_id": fsp_identity.fsp_id,
        "verified": fsp_identity.verified,
        "achievements_count": len(achievements),
        "verified_achievements": len([a for a in achievements if a.verification_status == "verified"]),
        "self_declared_achievements": len([a for a in achievements if a.verification_status == "self_declared"]),
        "fsp_index": fsp_index,
        "last_sync": fsp_identity.last_sync_at.isoformat() if fsp_identity.last_sync_at else None
    }
