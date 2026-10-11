from app.core.security import get_current_user, require_employer, require_candidate
"""Tests for profile privacy and onboarding fields

Tests TZ 2.2(2) requirements:
- PATCH support for onboarding
- Contact redaction from bio
- Field visibility per brief §6.1
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_patch_onboarding_fields_saved(auth_candidate, test_db):
    """Test that PATCH saves specialization_id and claimed_grade"""
    # Get specialization UUID from database
    from sqlalchemy import text
    spec = test_db.execute(
        text("SELECT id FROM specializations WHERE code = 'backend' LIMIT 1")
    ).fetchone()
    
    if not spec:
        pytest.skip("No specializations in test database")
    
    spec_id = str(spec[0])
    
    # PATCH profile with onboarding fields
    response = client.patch(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"},  # auth_candidate is the token string
        json={
            "specialization_id": spec_id,
            "claimed_grade": "middle",
            "full_name": "Test Candidate"
        }
    )
    
    assert response.status_code == 200, f"PATCH failed: {response.json()}"
    
    # GET profile to verify fields were saved
    get_response = client.get(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"}  # auth_candidate is the token string
    )
    
    assert get_response.status_code == 200
    data = get_response.json()
    
    # Verify onboarding fields are returned and saved
    assert data["specialization_id"] == spec_id, "specialization_id not saved"
    assert data["claimed_grade"] == "middle", "claimed_grade not saved"
    assert data["full_name"] == "Test Candidate"


def test_bio_contact_redaction_employer_view(client, auth_candidate, auth_employer, test_db):
    
    """Test that emails and phones in bio are redacted for employer before invitation.
    
    Per contract §5: bio is hidden before invitation acceptance (bio = None or redacted).
    This test verifies the stricter requirement: bio is None (not partially redacted).
    """
    # Candidate creates profile with contacts in bio
    bio_with_contacts = "Опытный разработчик. Пишите на vasya@example.com или звоните +7-999-123-4567"
    
    response = client.patch(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "bio": bio_with_contacts,
            "full_name": "Vasya Pupkin"
        }
    )
    assert response.status_code == 200
    
    # Grant publication consent
    consent_response = client.post(
        "/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "consent_type": "profile_publication",
            "granted": True,
            "version": "1.0"
        }
    )
    assert consent_response.status_code == 200
    
    # Get profile ID
    profile = client.get(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    ).json()
    
    candidate_id = profile["id"]
    
    # Employer views profile (before invitation acceptance)
    employer_view = client.get(
        f"/api/v1/profiles/candidate/{candidate_id}",
        headers={"Authorization": f"Bearer {auth_employer}"},
    )
    
    assert employer_view.status_code == 200
    employer_data = employer_view.json()
    
    # Verify bio is hidden (None) before invitation acceptance per §5
    # This is stricter than partial redaction: bio is completely unavailable to employer
    assert employer_data["bio"] is None, "bio should be None before invitation acceptance per §5"
    
    # Verify no contact leaks through bio
    if employer_data["bio"]:  # If bio were present, check no contacts are in it
        assert "vasya@example.com" not in employer_data["bio"], "Email leaked in bio!"
        assert "+7-999-123-4567" not in employer_data["bio"], "Phone leaked in bio!"
    
    # Verify structured contact fields are None
    assert employer_data["full_name"] is None, "full_name should be hidden"
    assert employer_data["email"] is None, "email should be hidden"
    assert employer_data["phone"] is None, "phone should be hidden"


def test_workplace_hidden_from_employer_view(client, auth_candidate, auth_employer, test_db):
    
    """Test that current_company and current_position are hidden per brief §6.1"""
    # Candidate sets workplace info
    response = client.patch(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "current_company": "Secret Corp",
            "current_position": "Senior Developer"
        }
    )
    assert response.status_code == 200
    
    # Grant publication consent
    client.post(
        "/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "consent_type": "profile_publication",
            "granted": True,
            "version": "1.0"
        }
    )
    
    # Get candidate ID
    profile = client.get(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    ).json()
    
    candidate_id = profile["id"]
    
    # Employer views profile
    employer_view = client.get(
        f"/api/v1/profiles/candidate/{candidate_id}",
        headers={"Authorization": f"Bearer {auth_employer}"},
    )
    
    employer_data = employer_view.json()
    
    # Per brief §6.1, workplace is hidden before invitation acceptance
    assert employer_data["current_company"] is None, "current_company should be hidden"
    assert employer_data["current_position"] is None, "current_position should be hidden"


def test_put_still_works(auth_candidate):
    """Verify PUT method still works alongside PATCH"""
    response = client.put(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "full_name": "Test via PUT",
            "years_of_experience": 5
        }
    )
    
    assert response.status_code == 200
    
    # Verify saved
    get_response = client.get(
        "/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    data = get_response.json()
    assert data["full_name"] == "Test via PUT"
    assert data["years_of_experience"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
