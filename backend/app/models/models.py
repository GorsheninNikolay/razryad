"""Database models - complete schema from brief §7.3

All models with fields, types, indexes, relationships, and constraints.
Owner: architect
"""
import uuid
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, Enum,
    ForeignKey, CheckConstraint, Index, UniqueConstraint,
    Numeric, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.db import Base, TimestampMixin, UUIDMixin, settings, GUID


# Determine JSON type based on database
def get_json_type():
    """Return JSONB for PostgreSQL, JSON for SQLite"""
    if settings.DATABASE_URL.startswith("postgresql"):
        return JSONB
    return JSON


# ============================================================================
# IDENTITY & USER MANAGEMENT
# ============================================================================

class User(Base, UUIDMixin, TimestampMixin):
    """User account (both candidates and employers)"""
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("candidate", "employer", "moderator", "admin", name="user_role"),
        nullable=False,
        index=True
    )
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    candidate_profile: Mapped[Optional["CandidateProfile"]] = relationship(back_populates="user", uselist=False)
    employer_profile: Mapped[Optional["EmployerProfile"]] = relationship(back_populates="user", uselist=False)
    consents: Mapped[List["Consent"]] = relationship(back_populates="user")
    sessions: Mapped[List["Session"]] = relationship(back_populates="user")


class Consent(Base, UUIDMixin, TimestampMixin):
    """Versioned consent records (152-ФЗ compliance)"""
    __tablename__ = "consents"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consent_type: Mapped[str] = mapped_column(
        Enum("personal_data", "profile_publication", "fsp_data", name="consent_type"),
        nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="consents")
    
    __table_args__ = (
        Index("ix_consents_user_type", "user_id", "consent_type"),
    )


class Session(Base, UUIDMixin, TimestampMixin):
    """User sessions for refresh token tracking"""
    __tablename__ = "sessions"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")


# ============================================================================
# CANDIDATE PROFILE
# ============================================================================

class CandidateProfile(Base, UUIDMixin, TimestampMixin):
    """Candidate profile (1:1 with User where role=candidate)"""
    __tablename__ = "candidate_profiles"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Personal info (kept separate from search index per §6.2)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Profile
    years_of_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Work preferences
    work_format: Mapped[Optional[str]] = mapped_column(
        Enum("remote", "office", "hybrid", "any", name="work_format"),
        nullable=True
    )
    team_role: Mapped[Optional[str]] = mapped_column(
        Enum("individual", "team_member", "team_lead", "any", name="team_role"),
        nullable=True
    )
    availability: Mapped[Optional[str]] = mapped_column(
        Enum("immediate", "two_weeks", "one_month", "not_looking", name="availability"),
        nullable=True
    )
    
    # Salary expectations (optional, can be hidden per privacy settings)
    salary_expectation_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_expectation_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Resume file
    resume_file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resume_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Profile completion and freshness
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Freshness decay (updated by micro-challenges)
    freshness_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    # Onboarding fields (nullable to support existing profiles)
    specialization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("specializations.id"),
        nullable=True
    )
    subspecialization_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "backend-api"
    claimed_grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="candidate_profile")
    skills: Mapped[List["CandidateSkill"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    category_assignment: Mapped[Optional["CategoryAssignment"]] = relationship(back_populates="candidate", uselist=False)
    grade_history: Mapped[List["GradeHistory"]] = relationship(back_populates="candidate")
    privacy_settings: Mapped[List["PrivacySetting"]] = relationship(back_populates="candidate")
    assessment_sessions: Mapped[List["AssessmentSession"]] = relationship(back_populates="candidate")
    ability_estimates: Mapped[List["AbilityEstimate"]] = relationship(back_populates="candidate")
    fsp_identity: Mapped[Optional["FspIdentity"]] = relationship(back_populates="candidate", uselist=False)
    invitations: Mapped[List["Invitation"]] = relationship(back_populates="candidate", foreign_keys="Invitation.candidate_id")
    applications: Mapped[List["Application"]] = relationship(back_populates="candidate")
    micro_challenge_responses: Mapped[List["MicroChallengeResponse"]] = relationship(back_populates="candidate")


# ============================================================================
# TAXONOMY: SPECIALIZATIONS & GRADES
# ============================================================================

class Specialization(Base, UUIDMixin, TimestampMixin):
    """IT specializations (backend, frontend, etc.)"""
    __tablename__ = "specializations"
    
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competency_blueprint: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    category_assignments: Mapped[List["CategoryAssignment"]] = relationship(back_populates="specialization")
    needs: Mapped[List["Need"]] = relationship(back_populates="specialization")


class Grade(Base, UUIDMixin, TimestampMixin):
    """Grading levels (intern, junior, middle, senior, lead)"""
    __tablename__ = "grades"
    
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # 0-4 for ordering
    theta_threshold: Mapped[float] = mapped_column(Float, nullable=False)  # IRT ability threshold
    experience_range_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # years, for display only
    experience_range_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    category_assignments: Mapped[List["CategoryAssignment"]] = relationship(back_populates="grade")


class CategoryAssignment(Base, UUIDMixin, TimestampMixin):
    """Current category assignment (specialization × grade)"""
    __tablename__ = "category_assignments"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    grade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    
    # Confirmation status
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Rank in category (updated by background job)
    category_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rank_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="category_assignment")
    specialization: Mapped["Specialization"] = relationship(back_populates="category_assignments")
    grade: Mapped["Grade"] = relationship(back_populates="category_assignments")
    
    __table_args__ = (
        Index("ix_category_spec_grade", "specialization_id", "grade_id"),
        Index("ix_category_rank", "specialization_id", "grade_id", "category_rank"),
    )


class GradeHistory(Base, UUIDMixin, TimestampMixin):
    """History of grade changes for transparency (required by brief §2.3)"""
    __tablename__ = "grade_history"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    old_grade_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("grades.id"), nullable=True)
    new_grade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    
    change_type: Mapped[str] = mapped_column(
        Enum("initial", "upgrade", "downgrade", "reconfirm", name="grade_change_type"),
        nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(100), nullable=False)  # "assessment", "manual", "recalibration"
    assessment_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="grade_history")
    
    __table_args__ = (
        Index("ix_grade_history_candidate", "candidate_id", "created_at"),
    )


# ============================================================================
# SKILLS
# ============================================================================

class Skill(Base, UUIDMixin, TimestampMixin):
    """Normalized skill taxonomy"""
    __tablename__ = "skills"
    
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # "language", "framework", "database", "tool"
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Relationships
    candidate_skills: Mapped[List["CandidateSkill"]] = relationship(back_populates="skill")
    aliases: Mapped[List["SkillAlias"]] = relationship(back_populates="skill")


class SkillAlias(Base, UUIDMixin, TimestampMixin):
    """Skill aliases for normalization (e.g., "React.js" → "React")"""
    __tablename__ = "skill_aliases"
    
    alias: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), nullable=False)
    
    # Relationships
    skill: Mapped["Skill"] = relationship(back_populates="aliases")


class CandidateSkill(Base, UUIDMixin, TimestampMixin):
    """Candidate's skills with proficiency level"""
    __tablename__ = "candidate_skills"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), nullable=False)
    proficiency: Mapped[str] = mapped_column(
        Enum("beginner", "intermediate", "advanced", "expert", name="skill_proficiency"),
        nullable=False
    )
    years_of_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="candidate_skills")
    
    __table_args__ = (
        UniqueConstraint("candidate_id", "skill_id", name="uq_candidate_skill"),
        Index("ix_candidate_skills_candidate", "candidate_id"),
    )


# ============================================================================
# PRIVACY SETTINGS
# ============================================================================

class PrivacySetting(Base, UUIDMixin, TimestampMixin):
    """Candidate privacy settings (§6.2)"""
    __tablename__ = "privacy_settings"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    setting_value: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="privacy_settings")
    
    __table_args__ = (
        UniqueConstraint("candidate_id", "setting_key", name="uq_candidate_privacy_setting"),
    )


# Continue in next message due to length...
"""Database models - Part 2: FSP, Assessment, Employer, Matching, Contact"""

# This continues from models.py
# Add these classes to models.py after the Privacy Settings section


# ============================================================================
# FSP INTEGRATION
# ============================================================================

class FspIdentity(Base, UUIDMixin, TimestampMixin):
    """FSP identity linkage"""
    __tablename__ = "fsp_identities"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    fsp_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="fsp_identity")
    achievements: Mapped[List["FspAchievement"]] = relationship(back_populates="fsp_identity", cascade="all, delete-orphan")


class FspAchievement(Base, UUIDMixin, TimestampMixin):
    """FSP achievement record (§5.2)"""
    __tablename__ = "fsp_achievements"
    
    fsp_identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fsp_identities.id", ondelete="CASCADE"), nullable=False)
    
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    event_level: Mapped[str] = mapped_column(
        Enum("international", "national", "regional", "university", "corporate", name="event_level"),
        nullable=False
    )
    discipline: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # "algorithms", "ml", "security", etc.
    
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    place: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    participants_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    role: Mapped[str] = mapped_column(
        Enum("participant", "captain", "coach", name="achievement_role"),
        default="participant",
        nullable=False
    )
    team_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    verification_status: Mapped[str] = mapped_column(
        Enum("verified", "self_declared", "pending", name="verification_status"),
        default="pending",
        nullable=False
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    fsp_identity: Mapped["FspIdentity"] = relationship(back_populates="achievements")
    
    __table_args__ = (
        Index("ix_fsp_achievements_discipline_date", "discipline", "event_date"),
    )


class FspSyncLog(Base, UUIDMixin, TimestampMixin):
    """FSP synchronization log"""
    __tablename__ = "fsp_sync_logs"
    
    fsp_identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fsp_identities.id", ondelete="CASCADE"), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "full", "incremental", "manual"
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "success", "failed", "partial"
    records_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================================
# ASSESSMENT SYSTEM (IRT/CAT)
# ============================================================================

class Competency(Base, UUIDMixin, TimestampMixin):
    """Competency areas within specializations"""
    __tablename__ = "competencies"
    
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)


class Blueprint(Base, UUIDMixin, TimestampMixin):
    """Assessment blueprint (content coverage specification)"""
    __tablename__ = "blueprints"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    grade_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("grades.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    weights: Mapped[List["BlueprintWeight"]] = relationship(back_populates="blueprint", cascade="all, delete-orphan")


class BlueprintWeight(Base, UUIDMixin, TimestampMixin):
    """Competency weights in blueprint"""
    __tablename__ = "blueprint_weights"
    
    blueprint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blueprints.id", ondelete="CASCADE"), nullable=False)
    competency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competencies.id"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)  # proportion (0-1)
    min_items: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_items: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    blueprint: Mapped["Blueprint"] = relationship(back_populates="weights")


class Item(Base, UUIDMixin, TimestampMixin):
    """Assessment item (question/task)"""
    __tablename__ = "items"
    
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    competency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competencies.id"), nullable=False)
    
    item_type: Mapped[str] = mapped_column(
        Enum("mcq", "code_output", "short_answer", "sql", "essay", name="item_type"),
        nullable=False
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        Enum("draft", "calibrating", "active", "retired", "quarantine", name="item_status"),
        default="draft",
        nullable=False,
        index=True
    )
    
    # IRT parameters (2PL model)
    discrimination: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # a parameter
    difficulty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # b parameter
    parameter_se: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)  # standard errors
    
    # Metadata
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Relationships
    versions: Mapped[List["ItemVersion"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    calibrations: Mapped[List["ItemCalibration"]] = relationship(back_populates="item")
    exposures: Mapped[List["ItemExposure"]] = relationship(back_populates="item")


class ItemVersion(Base, UUIDMixin, TimestampMixin):
    """Item content versions (for parametric variants)"""
    __tablename__ = "item_versions"
    
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Content (stored as JSON for flexibility)
    content: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    # Structure: {stem, options?, correct_answer?, rubric?, test_cases?}
    
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    item: Mapped["Item"] = relationship(back_populates="versions")
    
    __table_args__ = (
        UniqueConstraint("item_id", "version", name="uq_item_version"),
    )


class ItemCalibration(Base, UUIDMixin, TimestampMixin):
    """Item calibration history"""
    __tablename__ = "item_calibrations"
    
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    calibration_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "synthetic", "real", "equating"
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    discrimination: Mapped[float] = mapped_column(Float, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False)
    fit_statistics: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)
    
    # Relationships
    item: Mapped["Item"] = relationship(back_populates="calibrations")


class ItemExposure(Base, UUIDMixin, TimestampMixin):
    """Item exposure tracking (Sympson-Hetter control)"""
    __tablename__ = "item_exposures"
    
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exposure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exposure_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Relationships
    item: Mapped["Item"] = relationship(back_populates="exposures")
    
    __table_args__ = (
        Index("ix_item_exposure_window", "item_id", "window_end"),
    )


class AssessmentSession(Base, UUIDMixin, TimestampMixin):
    """CAT assessment session"""
    __tablename__ = "assessment_sessions"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    target_grade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blueprints.id"), nullable=False)
    
    status: Mapped[str] = mapped_column(
        Enum("active", "completed", "abandoned", "expired", name="session_status"),
        default="active",
        nullable=False,
        index=True
    )
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Current state
    current_item_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_theta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_se: Mapped[float] = mapped_column(Float, default=999.0, nullable=False)
    
    # Final results
    final_theta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_se: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assigned_grade_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("grades.id"), nullable=True)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="assessment_sessions")
    items: Mapped[List["SessionItem"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    responses: Mapped[List["SessionResponse"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_assessment_session_candidate", "candidate_id", "created_at"),
    )


class SessionItem(Base, UUIDMixin, TimestampMixin):
    """Items selected for a session"""
    __tablename__ = "session_items"
    
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False)
    item_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("item_versions.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    theta_when_selected: Mapped[float] = mapped_column(Float, nullable=False)
    information_value: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Relationships
    session: Mapped["AssessmentSession"] = relationship(back_populates="items")
    
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_session_item_sequence"),
    )


class SessionResponse(Base, UUIDMixin, TimestampMixin):
    """Candidate responses in session"""
    __tablename__ = "session_responses"
    
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False)
    session_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("session_items.id"), nullable=False)
    
    response_data: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-1 or rubric score
    
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    theta_after: Mapped[float] = mapped_column(Float, nullable=False)
    se_after: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Relationships
    session: Mapped["AssessmentSession"] = relationship(back_populates="responses")


class AbilityEstimate(Base, UUIDMixin, TimestampMixin):
    """Candidate ability estimates (θ̂) by specialization"""
    __tablename__ = "ability_estimates"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    
    theta: Mapped[float] = mapped_column(Float, nullable=False)
    se: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Grade probabilities P(θ > cut_g | data)
    grade_probabilities: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    
    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="ability_estimates")
    
    __table_args__ = (
        Index("ix_ability_estimate_candidate_spec", "candidate_id", "specialization_id", "created_at"),
    )


class LeakSignal(Base, UUIDMixin, TimestampMixin):
    """Leak detection signals"""
    __tablename__ = "leak_signals"
    
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "cusum", "p_value_anomaly"
    theta_band: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    observed_p_correct: Mapped[float] = mapped_column(Float, nullable=False)
    expected_p_correct: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    action_taken: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


# Continue in next part...
"""Database models - Part 3: Employer, Matching, Contact, Micro-challenges"""

# Add these to models.py after Assessment section


# ============================================================================
# MICRO-CHALLENGES
# ============================================================================

class MicroChallenge(Base, UUIDMixin, TimestampMixin):
    """Short challenges for freshness (§3.6)"""
    __tablename__ = "micro_challenges"
    
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    competency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competencies.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    
    employer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("employer_profiles.id"), nullable=True)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    estimated_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rubric: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    responses: Mapped[List["MicroChallengeResponse"]] = relationship(back_populates="challenge")


class MicroChallengeResponse(Base, UUIDMixin, TimestampMixin):
    """Candidate responses to micro-challenges"""
    __tablename__ = "micro_challenge_responses"
    
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("micro_challenges.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    
    response_data: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Scoring
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-4 per rubric
    rubric_scores: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "llm", "manual"
    
    # Relationships
    challenge: Mapped["MicroChallenge"] = relationship(back_populates="responses")
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="micro_challenge_responses")
    
    __table_args__ = (
        UniqueConstraint("challenge_id", "candidate_id", name="uq_challenge_response"),
    )


# ============================================================================
# EMPLOYER
# ============================================================================

class Company(Base, UUIDMixin, TimestampMixin):
    """Company/organization"""
    __tablename__ = "companies"
    
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    inn: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    industry: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(
        Enum("startup", "small", "medium", "large", "enterprise", name="company_size"),
        nullable=True
    )
    
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    employer_profiles: Mapped[List["EmployerProfile"]] = relationship(back_populates="company")
    trust_score: Mapped[Optional["TrustScore"]] = relationship(back_populates="company", uselist=False)
    vacancies: Mapped[List["Vacancy"]] = relationship(back_populates="company")


class EmployerProfile(Base, UUIDMixin, TimestampMixin):
    """Employer profile (1:1 with User where role=employer)"""
    __tablename__ = "employer_profiles"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="employer_profile")
    company: Mapped["Company"] = relationship(back_populates="employer_profiles")
    needs: Mapped[List["Need"]] = relationship(back_populates="employer")
    shortlists: Mapped[List["Shortlist"]] = relationship(back_populates="employer")
    invitations: Mapped[List["Invitation"]] = relationship(back_populates="employer", foreign_keys="Invitation.employer_id")
    vacancies: Mapped[List["Vacancy"]] = relationship(back_populates="employer")


class TrustScore(Base, UUIDMixin, TimestampMixin):
    """Company trust score (§4.4)"""
    __tablename__ = "trust_scores"
    
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    verification_level: Mapped[str] = mapped_column(
        Enum("email", "domain", "inn", "contract", name="verification_level"),
        default="email",
        nullable=False
    )
    
    # Metrics
    invitations_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invitations_accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invitations_declined: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ghosting_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    response_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ghosting_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Rate limits
    daily_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    weekly_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    
    # Relationships
    company: Mapped["Company"] = relationship(back_populates="trust_score")


# ============================================================================
# MATCHING & NEEDS
# ============================================================================

class Need(Base, UUIDMixin, TimestampMixin):
    """Employer's need (structured requirement, §4.2)"""
    __tablename__ = "needs"
    
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Grade range
    grade_min_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    grade_max_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    
    # Skills
    must_have_skills: Mapped[List[str]] = mapped_column(get_json_type(), nullable=False)
    nice_to_have_skills: Mapped[List[str]] = mapped_column(get_json_type(), nullable=False)
    
    # Context
    work_format: Mapped[Optional[str]] = mapped_column(
        Enum("remote", "office", "hybrid", "any", name="work_format"),
        nullable=True
    )
    team_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    team_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Salary (REQUIRED per brief §7.3)
    salary_min: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_max: Mapped[int] = mapped_column(Integer, nullable=False)
    
    urgency: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "urgent", name="urgency"),
        default="medium",
        nullable=False
    )
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Parsed/enriched data
    parsed_data: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    employer: Mapped["EmployerProfile"] = relationship(back_populates="needs")
    specialization: Mapped["Specialization"] = relationship(back_populates="needs")
    shortlists: Mapped[List["Shortlist"]] = relationship(back_populates="need")
    
    __table_args__ = (
        CheckConstraint("salary_min > 0", name="ck_need_salary_min_positive"),
        CheckConstraint("salary_max >= salary_min", name="ck_need_salary_max_gte_min"),
        Index("ix_needs_employer_active", "employer_id", "is_active"),
    )


class Shortlist(Base, UUIDMixin, TimestampMixin):
    """Shortlist (saved candidate selection, §4.2)"""
    __tablename__ = "shortlists"
    
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    employer: Mapped["EmployerProfile"] = relationship(back_populates="shortlists")
    need: Mapped["Need"] = relationship(back_populates="shortlists")
    revisions: Mapped[List["ShortlistRevision"]] = relationship(back_populates="shortlist", cascade="all, delete-orphan")
    entries: Mapped[List["ShortlistEntry"]] = relationship(back_populates="shortlist", cascade="all, delete-orphan")


class ShortlistRevision(Base, UUIDMixin, TimestampMixin):
    """Shortlist revision (for filter history, §4.2)"""
    __tablename__ = "shortlist_revisions"
    
    shortlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shortlists.id", ondelete="CASCADE"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    
    filters: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    ranking_params: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_ids: Mapped[list] = mapped_column(get_json_type(), nullable=True)
    
    # Relationships
    shortlist: Mapped["Shortlist"] = relationship(back_populates="revisions")
    
    __table_args__ = (
        UniqueConstraint("shortlist_id", "revision", name="uq_shortlist_revision"),
    )


class ShortlistEntry(Base, UUIDMixin, TimestampMixin):
    """Candidate in shortlist"""
    __tablename__ = "shortlist_entries"
    
    shortlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shortlists.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[dict] = mapped_column(get_json_type(), nullable=False)  # "Why in shortlist"
    
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    shortlist: Mapped["Shortlist"] = relationship(back_populates="entries")
    
    __table_args__ = (
        UniqueConstraint("shortlist_id", "candidate_id", name="uq_shortlist_candidate"),
        Index("ix_shortlist_entries_rank", "shortlist_id", "rank"),
    )


# ============================================================================
# VACANCIES & APPLICATIONS
# ============================================================================

class Vacancy(Base, UUIDMixin, TimestampMixin):
    """Published vacancy (traditional flow)"""
    __tablename__ = "vacancies"
    
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_profiles.id"), nullable=False)
    need_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("needs.id"), nullable=True)
    
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    grade_min_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    grade_max_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    
    # Salary (REQUIRED per brief §7.3)
    salary_min: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_max: Mapped[int] = mapped_column(Integer, nullable=False)
    
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    work_format: Mapped[Optional[str]] = mapped_column(
        Enum("remote", "office", "hybrid", "any", name="work_format"),
        nullable=True
    )
    
    requirements: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    status: Mapped[str] = mapped_column(
        Enum("draft", "published", "closed", "archived", name="vacancy_status"),
        default="draft",
        nullable=False,
        index=True
    )
    
    # Relationships
    company: Mapped["Company"] = relationship(back_populates="vacancies")
    employer: Mapped["EmployerProfile"] = relationship(back_populates="vacancies")
    applications: Mapped[List["Application"]] = relationship(back_populates="vacancy")
    
    __table_args__ = (
        CheckConstraint("salary_min > 0", name="ck_vacancy_salary_min_positive"),
        CheckConstraint("salary_max >= salary_min", name="ck_vacancy_salary_max_gte_min"),
        Index("ix_vacancies_published", "published", "published_at"),
    )


class Application(Base, UUIDMixin, TimestampMixin):
    """Candidate application to vacancy"""
    __tablename__ = "applications"
    
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(
        Enum("pending", "viewed", "shortlisted", "rejected", "interview", "offer", "hired", "withdrawn", name="application_status"),
        default="pending",
        nullable=False,
        index=True
    )
    
    # Relationships
    vacancy: Mapped["Vacancy"] = relationship(back_populates="applications")
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="applications")
    status_events: Mapped[List["ApplicationStatusEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("vacancy_id", "candidate_id", name="uq_application"),
        Index("ix_applications_candidate_status", "candidate_id", "status"),
    )


class ApplicationStatusEvent(Base, UUIDMixin, TimestampMixin):
    """Application status change history"""
    __tablename__ = "application_status_events"
    
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="status_events")


# Continue in next part...
"""Database models - Part 4: Invitations, Contact, Misc"""

# Add these to models.py after Applications section


# ============================================================================
# INVITATIONS & CONTACT
# ============================================================================

class Invitation(Base, UUIDMixin, TimestampMixin):
    """Employer invitation to candidate (§4.2)"""
    __tablename__ = "invitations"
    
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    
    vacancy_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("vacancies.id"), nullable=True)  # Optional link
    need_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("needs.id"), nullable=True)
    
    # Invitation content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Salary offer (REQUIRED per brief §7.3)
    salary_min: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_max: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Contact info (revealed after acceptance)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_method: Mapped[str] = mapped_column(String(500), nullable=False)  # email, phone, telegram, etc.
    
    # Lifecycle
    status: Mapped[str] = mapped_column(
        Enum("sent", "viewed", "accepted", "declined", "withdrawn", "expired", "hired", name="invitation_status"),
        default="sent",
        nullable=False,
        index=True
    )
    
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    slots_available: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Relationships
    employer: Mapped["EmployerProfile"] = relationship(back_populates="invitations", foreign_keys=[employer_id])
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="invitations", foreign_keys=[candidate_id])
    status_events: Mapped[List["InvitationStatusEvent"]] = relationship(back_populates="invitation", cascade="all, delete-orphan")
    contact_reveal: Mapped[Optional["ContactRevealLog"]] = relationship(back_populates="invitation", uselist=False)
    
    __table_args__ = (
        CheckConstraint("salary_min > 0", name="ck_invitation_salary_min_positive"),
        CheckConstraint("salary_max >= salary_min", name="ck_invitation_salary_max_gte_min"),
        Index("ix_invitations_candidate_status", "candidate_id", "status"),
        Index("ix_invitations_employer_status", "employer_id", "status"),
    )


class InvitationStatusEvent(Base, UUIDMixin, TimestampMixin):
    """Invitation status change history (required by brief §2.2)"""
    __tablename__ = "invitation_status_events"
    
    invitation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invitations.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)  # "candidate", "employer", "system"
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    invitation: Mapped["Invitation"] = relationship(back_populates="status_events")


class ContactRevealLog(Base, UUIDMixin, TimestampMixin):
    """Contact reveal audit log (§6.2 compliance)"""
    __tablename__ = "contact_reveal_logs"
    
    invitation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invitations.id", ondelete="CASCADE"), unique=True, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    
    revealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    trigger: Mapped[str] = mapped_column(String(100), nullable=False)  # "invitation_accepted", "application_created"
    
    # What was revealed
    candidate_data_revealed: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    employer_data_revealed: Mapped[dict] = mapped_column(get_json_type(), nullable=False)
    
    # Relationships
    invitation: Mapped["Invitation"] = relationship(back_populates="contact_reveal")


class Complaint(Base, UUIDMixin, TimestampMixin):
    """Candidate complaints about invitations/vacancies (§4.4)"""
    __tablename__ = "complaints"
    
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # Target
    invitation_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("invitations.id"), nullable=True)
    vacancy_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    
    complaint_type: Mapped[str] = mapped_column(
        Enum("spam", "fake_vacancy", "inappropriate", "discrimination", "other", name="complaint_type"),
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(
        Enum("pending", "reviewing", "resolved", "dismissed", name="complaint_status"),
        default="pending",
        nullable=False
    )
    
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ============================================================================
# NOTIFICATIONS & AUDIT
# ============================================================================

class Notification(Base, UUIDMixin, TimestampMixin):
    """User notifications"""
    __tablename__ = "notifications"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notification_metadata: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)
    
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read", "created_at"),
    )


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit log for significant actions (§6.3)"""
    __tablename__ = "audit_logs"
    
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Без index=True: имя ix_audit_logs_action уже занято составным индексом ниже.
    # Дублирование ломало Base.metadata.create_all (CREATE INDEX дважды).
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    
    changes: Mapped[Optional[dict]] = mapped_column(get_json_type(), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_action", "action", "created_at"),
    )


# ============================================================================
# MISCELLANEOUS
# ============================================================================

class SalaryBenchmark(Base, UUIDMixin, TimestampMixin):
    """Salary benchmarks by category"""
    __tablename__ = "salary_benchmarks"
    
    specialization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    grade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grades.id"), nullable=False)
    
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    percentile_25: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile_50: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile_75: Mapped[int] = mapped_column(Integer, nullable=False)
    
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (
        Index("ix_salary_benchmarks_category", "specialization_id", "grade_id", "region"),
    )


# Import all models for Alembic
__all__ = [
    "User", "Consent", "Session",
    "CandidateProfile", "Specialization", "Grade", "CategoryAssignment", "GradeHistory",
    "Skill", "SkillAlias", "CandidateSkill", "PrivacySetting",
    "FspIdentity", "FspAchievement", "FspSyncLog",
    "Competency", "Blueprint", "BlueprintWeight",
    "Item", "ItemVersion", "ItemCalibration", "ItemExposure",
    "AssessmentSession", "SessionItem", "SessionResponse", "AbilityEstimate", "LeakSignal",
    "MicroChallenge", "MicroChallengeResponse",
    "Company", "EmployerProfile", "TrustScore",
    "Need", "Shortlist", "ShortlistRevision", "ShortlistEntry",
    "Vacancy", "Application", "ApplicationStatusEvent",
    "Invitation", "InvitationStatusEvent", "ContactRevealLog", "Complaint",
    "Notification", "AuditLog", "SalaryBenchmark"
]
