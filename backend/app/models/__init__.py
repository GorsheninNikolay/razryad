"""Import all models for easy access"""
from app.models.models import (
    User, Consent, Session,
    CandidateProfile, Specialization, Grade, CategoryAssignment, GradeHistory,
    Skill, SkillAlias, CandidateSkill, PrivacySetting,
    FspIdentity, FspAchievement, FspSyncLog,
    Competency, Blueprint, BlueprintWeight,
    Item, ItemVersion, ItemCalibration, ItemExposure,
    AssessmentSession, SessionItem, SessionResponse, AbilityEstimate, LeakSignal,
    MicroChallenge, MicroChallengeResponse,
    Company, EmployerProfile, TrustScore,
    Need, Shortlist, ShortlistRevision, ShortlistEntry,
    Vacancy, Application, ApplicationStatusEvent,
    Invitation, InvitationStatusEvent, ContactRevealLog, Complaint,
    Notification, AuditLog, SalaryBenchmark
)

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
