"""Candidate profiles API - full implementation with privacy and consents

Owner: architect
"""
from typing import Optional, List
import re
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.core.db import get_db
from app.core.security import get_current_user, require_candidate
from app.models.models import (
    CandidateProfile, User, Consent, PrivacySetting, 
    Skill, CandidateSkill, Specialization, Grade
)
from app.services.notifications import log_audit, create_notification
from app.services.auth import create_consent


router = APIRouter()


# Utility functions
EMAIL_PLACEHOLDER = '[email скрыт до принятия приглашения]'
PHONE_PLACEHOLDER = '[телефон скрыт до принятия приглашения]'

# Any e-mail-looking token. Checked FIRST, because an address may contain the
# '+' and digits the phone patterns look for (city44@example.com).
_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

# Optional extension tail, so "8-999-123-45-67 доб. 123" leaves no digits behind.
_EXT = r'(?:\s*(?:доб\.?|добавочный|ext\.?|x)\s*\d{1,6})?'

# International form: '+' <country code> <digits with arbitrary separators>.
# Covers +7, +44, +1, +49 ... The character class is greedy on purpose: a
# partially consumed number would leave a readable tail (the '-67' defect).
_INTL_PHONE_RE = re.compile(r'\+\d[\d\s\-.()]{6,}\d' + _EXT)

# Russian domestic form starting with 8, with or without separators/brackets.
_LOCAL_PHONE_RE = re.compile(
    r'\b8[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{2}[\s\-.]?\d{2}' + _EXT
)


def redact_contacts_from_text(text: str) -> str:
    """Redact e-mails and phone numbers from ANY free-form candidate text.

    Per TZ 2.2(2) / brief §6.1 contacts must not reach the employer before the
    invitation is accepted. The leak is not specific to `bio`: every field the
    candidate fills in by hand can carry an address or a number, so this helper
    is applied to each free-text field of the employer view (see
    `redact_free_text_fields`), not to `bio` alone.

    Phone coverage is intentionally generic (`+<country code><number>` plus the
    Russian `8...` form) rather than a list of observed examples, because
    earlier versions matched only `+7`/`8` and let `+44 20 7946 0958` through.
    """
    if not text:
        return text

    text = _EMAIL_RE.sub(EMAIL_PLACEHOLDER, text)
    text = _INTL_PHONE_RE.sub(PHONE_PLACEHOLDER, text)
    text = _LOCAL_PHONE_RE.sub(PHONE_PLACEHOLDER, text)

    return text


# Free-text fields of the candidate profile that the employer may see before
# the invitation is accepted. Each one is redacted; fields that are hidden
# outright (full_name, phone, email, current_company, current_position) are
# handled by returning None and are not listed here.
EMPLOYER_VISIBLE_FREE_TEXT_FIELDS = ("bio", "city")


def redact_free_text_fields(profile) -> dict:
    """Return redacted values for every employer-visible free-text field."""
    return {
        field: redact_contacts_from_text(getattr(profile, field, None))
        for field in EMPLOYER_VISIBLE_FREE_TEXT_FIELDS
    }


def resolve_specialization(db: Session, value: str) -> uuid.UUID:
    """Resolve specialization code OR UUID into a Specialization UUID.

    The frontend onboarding survey sends a stable code ("backend"); the column
    is a UUID. Accepting only UUIDs made the first onboarding step return 500
    (badly formed hexadecimal UUID string) because the type processor raised
    before any validation ran. The public contract therefore accepts both, and
    an unknown value is a 422 with the allowed codes, never an exception.
    """
    spec = db.query(Specialization).filter(Specialization.code == value).first()
    if spec:
        return spec.id

    # Not a code: it may still be a UUID of an existing specialization.
    try:
        candidate_uuid = uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        candidate_uuid = None

    if candidate_uuid is not None:
        spec = db.get(Specialization, candidate_uuid)
        if spec:
            return spec.id

    valid = ', '.join(
        s.code for s in db.query(Specialization).order_by(Specialization.code).all()
    )
    raise HTTPException(
        status_code=422,
        detail=f'Неизвестная специализация; допустимые значения: {valid}'
    )


def resolve_grade_code(db: Session, value: str) -> str:
    """Validate claimed_grade against the grades reference table.

    claimed_grade is stored as a code string, so the only failure mode is an
    unknown code. That must be a 422 with the allowed values rather than a
    silently stored garbage grade.
    """
    grade = db.query(Grade).filter(Grade.code == value).first()
    if grade:
        return grade.code

    valid = ', '.join(g.code for g in db.query(Grade).order_by(Grade.level).all())
    raise HTTPException(
        status_code=422,
        detail=f'Неизвестный грейд; допустимые значения: {valid}'
    )


def parse_uuid_or_422(value: str, field_name: str) -> uuid.UUID:
    """Parse a path/body UUID, answering 422 instead of letting SQLAlchemy 500."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f'Поле {field_name} должно быть корректным UUID'
        )


def resolve_skill_code_or_name(db: Session, value: str) -> uuid.UUID:
    """Resolve skill name or UUID to skill UUID.
    
    Skills are identified by name ('Python'), normalized_name ('python'),
    or UUID. Also check skill_aliases for alternate names.
    """
    from app.models.models import SkillAlias
    
    # Try exact name match first
    skill = db.query(Skill).filter(Skill.name == value).first()
    if skill:
        return skill.id
    
    # Try normalized name (case-insensitive)
    skill = db.query(Skill).filter(
        func.lower(Skill.normalized_name) == value.lower()
    ).first()
    if skill:
        return skill.id
    
    # Try skill aliases
    alias = db.query(SkillAlias).filter(
        func.lower(SkillAlias.alias) == value.lower()
    ).first()
    if alias:
        return alias.skill_id
    
    # Try as UUID
    try:
        skill_uuid = uuid.UUID(str(value))
        skill = db.get(Skill, skill_uuid)
        if skill:
            return skill.id
    except (ValueError, AttributeError, TypeError):
        pass
    
    # Not found
    raise HTTPException(
        status_code=422,
        detail=f'Навык "{value}" не найден; используй название навыка (Python, React, Docker, etc.)'
    )


# Schemas
class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    years_of_experience: Optional[int] = Field(None, ge=0)
    experience_years: Optional[int] = Field(None, ge=0)  # Alias for backwards compatibility
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    industry: Optional[str] = None
    bio: Optional[str] = None
    work_format: Optional[str] = Field(None, pattern="^(remote|office|hybrid|any)$")
    team_role: Optional[str] = Field(None, pattern="^(individual|team_member|team_lead|any)$")
    availability: Optional[str] = Field(None, pattern="^(immediate|two_weeks|one_month|not_looking)$")
    salary_expectation_min: Optional[int] = Field(None, ge=0)
    salary_expectation_max: Optional[int] = Field(None, ge=0)
    # Onboarding fields
    specialization_id: Optional[str] = None  # code ("backend") or UUID
    subspecialization_id: Optional[str] = None  # code ("backend-api") or UUID
    claimed_grade: Optional[str] = None  # grade code: intern/junior/middle/senior/lead
    # Skills: list of skill codes/names to be resolved and stored
    skills: Optional[List[str]] = None
    
    model_config = ConfigDict(extra='forbid')


class SkillAdd(BaseModel):
    skill_id: str  # Code or UUID; API resolves
    proficiency: str = Field(pattern="^(beginner|intermediate|advanced|expert)$")
    years_of_experience: Optional[int] = Field(None, ge=0)
    is_primary: bool = False
    
    model_config = ConfigDict(extra='forbid')


class ConsentRequest(BaseModel):
    consent_type: str = Field(pattern="^(personal_data|profile_publication|fsp_data)$")
    granted: bool
    version: str = "1.0"


class PrivacySettingRequest(BaseModel):
    setting_key: str
    setting_value: str


# Endpoints
@router.get("/candidate/me")
async def get_my_profile(
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Get current candidate's profile"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        profile = user.candidate_profile
    
    # Get consents
    consents = db.query(Consent).filter(
        Consent.user_id == user.id
    ).order_by(Consent.created_at.desc()).all()
    
    # Get skills
    skills = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == profile.id
    ).all()
    
    # Get privacy settings
    privacy_settings = db.query(PrivacySetting).filter(
        PrivacySetting.candidate_id == profile.id
    ).all()
    
    return {
        "id": str(profile.id),
        "user_id": str(user.id),
        "email": user.email,
        "full_name": profile.full_name,
        "phone": profile.phone,
        "city": profile.city,
        "years_of_experience": profile.years_of_experience,
        "current_company": profile.current_company,
        "current_position": profile.current_position,
        "industry": profile.industry,
        "bio": profile.bio,
        "work_format": profile.work_format,
        "team_role": profile.team_role,
        "availability": profile.availability,
        "salary_expectation_min": profile.salary_expectation_min,
        "salary_expectation_max": profile.salary_expectation_max,
        "onboarding_completed": profile.onboarding_completed,
        "profile_visible": profile.profile_visible,
        # Onboarding fields
        "specialization_id": str(profile.specialization_id) if profile.specialization_id else None,
        "subspecialization_id": profile.subspecialization_id,
        "claimed_grade": profile.claimed_grade,
        "skills": [
            {
                "skill_id": str(s.skill_id),
                "name": s.skill.name if s.skill else None,
                "proficiency": s.proficiency,
                "years_of_experience": s.years_of_experience,
                "is_primary": s.is_primary
            } for s in skills
        ],
        "consents": [
            {
                "consent_type": c.consent_type,
                "granted": c.granted,
                "version": c.version,
                "created_at": c.created_at.isoformat()
            } for c in consents
        ],
        "privacy_settings": [
            {
                "setting_key": p.setting_key,
                "setting_value": p.setting_value
            } for p in privacy_settings
        ]
    }


@router.put("/candidate/me")
@router.patch("/candidate/me")  # Support PATCH for frontend compatibility
async def update_my_profile(
    data: ProfileUpdate,
    request: Request,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Update current candidate's profile (PUT or PATCH)"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create profile if doesn't exist
    if not user.candidate_profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        profile = user.candidate_profile
    
    # Update fields
    #
    # Reference fields are resolved BEFORE assignment. The onboarding survey
    # sends a stable code ("backend"), and assigning that straight onto a UUID
    # column made SQLAlchemy raise at flush time -> 500. Resolving here keeps
    # the failure a validated 422 and stores the canonical UUID.
    changes = {}
    skills_to_update = None
    
    for field, value in data.dict(exclude_unset=True).items():
        if value is None:
            continue

        # Handle skills separately (it's a list to resolve)
        if field == "skills":
            skills_to_update = value
            continue
        
        # Alias: experience_years → years_of_experience
        if field == "experience_years":
            field = "years_of_experience"

        if field == "specialization_id":
            value = resolve_specialization(db, value)
        elif field == "subspecialization_id":
            # subspecialization_id is stored as a string code (e.g., "backend-api")
            # No resolution needed, just store it as-is
            pass
        elif field == "claimed_grade":
            value = resolve_grade_code(db, value)

        old_value = getattr(profile, field, None)
        if old_value != value:
            changes[field] = {"old": str(old_value) if old_value is not None else None,
                              "new": str(value)}
            setattr(profile, field, value)
    
    # Handle skills: resolve codes/names to UUIDs and replace candidate's skill list
    if skills_to_update is not None:
        # Remove existing skills for this candidate
        db.query(CandidateSkill).filter(CandidateSkill.candidate_id == profile.id).delete()
        
        # Add new skills
        for skill_identifier in skills_to_update:
            skill_id = resolve_skill_code_or_name(db, skill_identifier)
            candidate_skill = CandidateSkill(
                candidate_id=profile.id,
                skill_id=skill_id,
                proficiency="intermediate",  # Default proficiency
                is_primary=False
            )
            db.add(candidate_skill)
        
        changes["skills"] = {"old": [], "new": skills_to_update}
    
    db.commit()
    db.refresh(profile)
    
    # Audit log
    if changes:
        log_audit(
            db=db,
            action="profile_updated",
            entity_type="candidate_profile",
            entity_id=profile.id,
            user_id=user.id,
            changes=changes,
            ip_address=request.client.host if request.client else None
        )
    
    return {"message": "Profile updated successfully", "profile_id": str(profile.id)}


@router.post("/candidate/me/consents")
async def update_consent(
    data: ConsentRequest,
    request: Request,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Grant or revoke consent (versioned, with IP tracking)
    
    Required for TZ compliance - separate consents for:
    - personal_data: Processing of personal data
    - profile_publication: Publishing profile to employers
    - fsp_data: Sharing FSP achievements
    """
    # Get consent text (in production, from database/config)
    consent_texts = {
        "personal_data": "Я даю согласие на обработку моих персональных данных в соответствии с 152-ФЗ",
        "profile_publication": "Я даю согласие на публикацию моего профиля работодателям на платформе РАЗРЯД",
        "fsp_data": "Я даю согласие на передачу данных о моих достижениях ФСП"
    }
    
    consent = create_consent(
        db=db,
        user_id=current_user["id"],
        consent_type=data.consent_type,
        version=data.version,
        text_snapshot=consent_texts.get(data.consent_type, ""),
        granted=data.granted,
        ip_address=request.client.host if request.client else None
    )
    
    # Update profile visibility if publication consent changed
    if data.consent_type == "profile_publication":
        user = db.query(User).filter(User.id == current_user["id"]).first()
        if user and user.candidate_profile:
            user.candidate_profile.profile_visible = data.granted
            db.commit()
    
    # Audit log
    log_audit(
        db=db,
        action=f"consent_{'granted' if data.granted else 'revoked'}",
        entity_type="consent",
        entity_id=consent.id,
        user_id=current_user["id"],
        changes={
            "consent_type": data.consent_type,
            "granted": data.granted,
            "version": data.version
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "message": f"Consent {'granted' if data.granted else 'revoked'} successfully",
        "consent_id": str(consent.id),
        "consent_type": data.consent_type,
        "granted": data.granted
    }


@router.post("/candidate/me/skills")
async def add_skill(
    data: SkillAdd,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Add skill to profile (validated against skills.json)"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    # Resolve skill code/name/UUID to skill UUID
    skill_id = resolve_skill_code_or_name(db, data.skill_id)
    
    # Check if already added
    existing = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == user.candidate_profile.id,
        CandidateSkill.skill_id == skill_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="Skill already added")
    
    # Add skill
    candidate_skill = CandidateSkill(
        candidate_id=user.candidate_profile.id,
        skill_id=skill_id,
        proficiency=data.proficiency,
        years_of_experience=data.years_of_experience,
        is_primary=data.is_primary
    )
    db.add(candidate_skill)
    db.commit()
    
    # Get skill details for response
    skill = db.get(Skill, skill_id)
    
    return {
        "message": "Skill added successfully",
        "skill_id": str(skill_id),
        "skill_name": skill.name if skill else None
    }


@router.post("/candidate/me/privacy")
async def set_privacy_setting(
    data: PrivacySettingRequest,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    """Set privacy setting
    
    Supported settings:
    - hide_from_search: "true"/"false"
    - block_company: company_id
    - do_not_disturb_until: ISO date
    """
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-create profile if doesn't exist
    if not user.candidate_profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    
    # Upsert privacy setting
    setting = db.query(PrivacySetting).filter(
        PrivacySetting.candidate_id == user.candidate_profile.id,
        PrivacySetting.setting_key == data.setting_key
    ).first()
    
    if setting:
        setting.setting_value = data.setting_value
    else:
        setting = PrivacySetting(
            candidate_id=user.candidate_profile.id,
            setting_key=data.setting_key,
            setting_value=data.setting_value
        )
        db.add(setting)
    
    db.commit()
    
    return {
        "message": "Privacy setting updated",
        "setting_key": data.setting_key,
        "setting_value": data.setting_value
    }


@router.get("/candidate/{candidate_id}")
async def get_candidate_profile(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get candidate profile.
    
    - Owner (same candidate) sees full profile
    - Employer sees pseudonymized public view (no bio/city/workplace/contacts)
    - Other candidate sees pseudonymized public view (same as employer)
    """
    profile_id = parse_uuid_or_422(candidate_id, "candidate_id")
    profile = db.query(CandidateProfile).filter(
        CandidateProfile.id == profile_id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Check if this is the owner
    is_owner = current_user["id"] == profile.user_id
    
    if is_owner:
        # Owner sees full profile
        pub_consent = db.query(Consent).filter(
            Consent.user_id == profile.user_id,
            Consent.consent_type == "profile_publication",
            Consent.granted == True
        ).order_by(Consent.created_at.desc()).first()
        
        if not pub_consent:
            raise HTTPException(
                status_code=403,
                detail="Profile not published - consent not granted"
            )
        
        skills = db.query(CandidateSkill).filter(
            CandidateSkill.candidate_id == profile.id
        ).all()
        
        return {
            "id": str(profile.id),
            "full_name": profile.full_name,
            "phone": profile.phone,
            "email": profile.user.email if profile.user else None,
            "city": profile.city,
            "years_of_experience": profile.years_of_experience,
            "current_company": profile.current_company,
            "current_position": profile.current_position,
            "industry": profile.industry,
            "bio": profile.bio,
            "work_format": profile.work_format,
            "team_role": profile.team_role,
            "availability": profile.availability,
            "salary_expectation_min": profile.salary_expectation_min,
            "salary_expectation_max": profile.salary_expectation_max,
            "specialization": profile.specialization_id,
            "claimed_grade": profile.claimed_grade,
            "skills": [{"id": str(s.skill_id), "skill_name": s.skill.name} for s in skills]
        }
    else:
        # Non-owner sees pseudonymized view
        pub_consent = db.query(Consent).filter(
            Consent.user_id == profile.user_id,
            Consent.consent_type == "profile_publication",
            Consent.granted == True
        ).order_by(Consent.created_at.desc()).first()
        
        if not pub_consent:
            raise HTTPException(
                status_code=403,
                detail="Profile not published - consent not granted"
            )
        
        skills = db.query(CandidateSkill).filter(
            CandidateSkill.candidate_id == profile.id
        ).all()
        
        return {
            "id": str(profile.id),
            "pseudonym": f"#{str(profile.id)[:4].upper()}",
            # Visible before invitation
            "years_of_experience": profile.years_of_experience,
            "work_format": profile.work_format,
            "team_role": profile.team_role,
            "availability": profile.availability,
            "salary_expectation_max": profile.salary_expectation_max,
            "specialization": profile.specialization_id,
            "claimed_grade": profile.claimed_grade,
            "skills": [{"id": str(s.skill_id), "skill_name": s.skill.name} for s in skills],
            # Hidden from non-owners
            "full_name": None,
            "phone": None,
            "email": None,
            "city": None,
            "current_company": None,
            "current_position": None,
            "industry": None,
            "bio": None,
            "salary_expectation_min": None
        }
