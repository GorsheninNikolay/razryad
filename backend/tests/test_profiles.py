"""Test candidate profiles with privacy and consents"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, get_db, engine



# Локальные фикстуры test_db/client удалены: они брали `engine` из app.core.db,
# то есть общую демо-базу, и `Base.metadata.drop_all(bind=engine)` в finally сносил
# все её таблицы при каждом прогоне тестов. Используются безопасные фикстуры из
# conftest.py: отдельная SQLite в памяти через StaticPool.

# Local auth_candidate fixture removed - using the one from conftest.py to avoid
# duplicate email conflicts


def test_update_profile(client, auth_candidate):
    """Test profile update"""
    response = client.put("/api/v1/profiles/candidate/me", 
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "full_name": "Test Candidate",
            "years_of_experience": 5,
            "work_format": "remote",
            "bio": "Experienced backend developer"
        }
    )
    
    assert response.status_code == 200
    assert "Profile updated successfully" in response.json()["message"]


def test_consent_personal_data(client, auth_candidate):
    """Test granting personal data consent"""
    response = client.post("/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "consent_type": "personal_data",
            "granted": True,
            "version": "1.0"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["consent_type"] == "personal_data"
    assert data["granted"] == True


def test_consent_profile_publication(client, auth_candidate):
    """Test profile publication consent"""
    response = client.post("/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "consent_type": "profile_publication",
            "granted": True,
            "version": "1.0"
        }
    )
    
    assert response.status_code == 200
    assert response.json()["consent_type"] == "profile_publication"


def test_revoke_consent(client, auth_candidate):
    """Test revoking consent (separate versioned records)"""
    # Grant
    client.post("/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"consent_type": "profile_publication", "granted": True, "version": "1.0"}
    )
    
    # Revoke
    response = client.post("/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"consent_type": "profile_publication", "granted": False, "version": "1.0"}
    )
    
    assert response.status_code == 200
    assert response.json()["granted"] == False


def test_separate_consents(client, auth_candidate):
    """Test that consents are separate (personal_data vs profile_publication)"""
    # Grant personal data only
    client.post("/api/v1/profiles/candidate/me/consents",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"consent_type": "personal_data", "granted": True, "version": "1.0"}
    )
    
    # Get profile
    profile = client.get("/api/v1/profiles/candidate/me",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    consents = profile.json()["consents"]
    assert len(consents) >= 1
    
    # Check that personal_data and profile_publication are separate
    consent_types = [c["consent_type"] for c in consents]
    assert "personal_data" in consent_types


def test_privacy_settings(client, auth_candidate):
    """Test privacy settings"""
    response = client.post("/api/v1/profiles/candidate/me/privacy",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={
            "setting_key": "hide_from_search",
            "setting_value": "true"
        }
    )
    
    assert response.status_code == 200
    assert response.json()["setting_key"] == "hide_from_search"


def test_profile_requires_auth(client):
    """Test that profile endpoints require authentication"""
    response = client.get("/api/v1/profiles/candidate/me")
    assert response.status_code == 401
