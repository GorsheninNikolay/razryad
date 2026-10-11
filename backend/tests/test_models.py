"""Tests for database models and schema"""
from app.models.models import User, CandidateProfile, Specialization, Grade


def test_user_model(test_db):
    """Test User model creation"""
    user = User(
        email="test@example.com",
        password_hash="hash",
        role="candidate"
    )
    test_db.add(user)
    test_db.commit()
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.role == "candidate"
    assert user.email_confirmed is False


def test_candidate_profile_relationship(test_db):
    """Test User to CandidateProfile relationship"""
    user = User(
        email="candidate@example.com",
        password_hash="hash",
        role="candidate"
    )
    test_db.add(user)
    test_db.commit()
    
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Test Candidate"
    )
    test_db.add(profile)
    test_db.commit()
    
    assert profile.user_id == user.id
    assert profile.user.email == "candidate@example.com"
