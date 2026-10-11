"""Test FSP integration - mock OIDC, achievements, index calculation"""
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


def test_candidate_without_fsp_history(client, auth_candidate):
    """Test candidate without FSP history - TZ criterion #5
    
    CRITICAL: This must return neutral status, not an error.
    The path "candidate without FSP history" is explicitly evaluated in TZ.
    """
    response = client.get("/api/v1/fsp/status",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check neutral status (not error)
    assert data["has_fsp"] == False
    assert data["fsp_id"] is None
    assert data["achievements_count"] == 0
    assert data["fsp_index"] == 0.0
    assert "message" in data
    assert "link it anytime" in data["message"].lower()


def test_mock_oidc_provider(client):
    """Test mock FSP OIDC provider"""
    response = client.get("/api/v1/fsp/mock-provider/auth?fsp_id=FSP001")
    
    assert response.status_code == 200
    data = response.json()
    assert "fsp_data" in data
    assert data["fsp_data"]["fsp_id"] == "FSP001"
    assert data["fsp_data"]["verified"] == True
    assert len(data["fsp_data"]["achievements"]) > 0


def test_link_fsp_identity(client, auth_candidate):
    """Test linking FSP identity"""
    response = client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP001"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["fsp_id"] == "FSP001"
    assert data["achievements_synced"] > 0
    assert "fsp_index" in data
    assert data["fsp_index"] > 0.0
    
    # Clean up for other tests
    client.delete("/api/v1/fsp/unlink", headers={"Authorization": f"Bearer {auth_candidate}"})


def test_get_fsp_status_with_linked(client, auth_candidate):
    """Test getting FSP status after linking"""
    # Link FSP
    client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP002"}
    )
    
    # Get status
    response = client.get("/api/v1/fsp/status",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_fsp"] == True
    assert data["fsp_id"] == "FSP002"
    assert data["achievements_count"] > 0
    assert "verified_achievements" in data
    assert "fsp_index" in data


def test_get_fsp_achievements(client, auth_candidate):
    """Test getting achievement details"""
    # Link FSP
    client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP001"}
    )
    
    # Get achievements
    response = client.get("/api/v1/fsp/achievements",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_fsp"] == True
    assert len(data["achievements"]) > 0
    
    # Check achievement structure
    ach = data["achievements"][0]
    assert "event_name" in ach
    assert "event_level" in ach
    assert "discipline" in ach
    assert "verification_status" in ach
    assert "recency_weight" in ach
    assert "place_weight" in ach
    
    # Clean up
    client.delete("/api/v1/fsp/unlink", headers={"Authorization": f"Bearer {auth_candidate}"})


def test_unlink_fsp(client, auth_candidate):
    """Test unlinking FSP"""
    # Link
    client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP001"}
    )
    
    # Unlink
    response = client.delete("/api/v1/fsp/unlink",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    
    assert response.status_code == 200
    assert "unlinked successfully" in response.json()["message"].lower()
    
    # Verify unlinked
    status = client.get("/api/v1/fsp/status",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    )
    assert status.json()["has_fsp"] == False


def test_fsp_index_calculation(client, auth_candidate):
    """Test FSP index calculation per brief §5.3
    
    Formula: level_weight × place_weight × recency_weight × discipline_fit
    - Verified achievements get full weight
    - Self-declared get 0
    - Recency: 24-month half-life
    """
    # Link FSP with achievements
    link_response = client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP001"}
    )
    
    assert link_response.status_code == 200
    fsp_index = link_response.json()["fsp_index"]
    
    # Index should be > 0 for FSP001 (has 2 verified achievements)
    assert fsp_index > 0.0
    
    # Get detailed achievements to verify calculation
    achs = client.get("/api/v1/fsp/achievements",
        headers={"Authorization": f"Bearer {auth_candidate}"}
    ).json()["achievements"]
    
    # All should have weights calculated
    for ach in achs:
        assert ach["recency_weight"] >= 0.0
        assert ach["place_weight"] >= 0.0
    
    # Clean up
    client.delete("/api/v1/fsp/unlink", headers={"Authorization": f"Bearer {auth_candidate}"})


def test_duplicate_fsp_id_rejected(client, auth_candidate):
    """Test that FSP ID can only be linked to one account"""
    # Link to first candidate
    client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {auth_candidate}"},
        json={"fsp_id": "FSP001"}
    )
    
    # Create second candidate
    reg2 = client.post("/api/v1/auth/register", json={
        "email": "candidate2@test.com",
        "password": "testpass123",  # 11 chars
        "role": "candidate"
    })
    token2 = reg2.json()["confirmation_link"].split("token=")[1]
    client.post("/api/v1/auth/confirm-email", json={"token": token2})
    login2 = client.post("/api/v1/auth/login", json={
        "email": "candidate2@test.com",
        "password": "testpass123"
    })
    token2 = login2.json()["access_token"]
    
    # Try to link same FSP ID
    response = client.post("/api/v1/fsp/link",
        headers={"Authorization": f"Bearer {token2}"},
        json={"fsp_id": "FSP001"}
    )
    
    assert response.status_code == 409
    assert "already linked" in response.json()["detail"].lower()
