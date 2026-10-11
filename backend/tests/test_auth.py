"""Test authentication flow: registration, email confirmation, login"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, get_db, engine



# Локальные фикстуры test_db/client удалены: они брали `engine` из app.core.db,
# то есть общую демо-базу, и `Base.metadata.drop_all(bind=engine)` в finally сносил
# все её таблицы при каждом прогоне тестов. Используются безопасные фикстуры из
# conftest.py: отдельная SQLite в памяти через StaticPool.

def test_register_candidate(client):
    """Test candidate registration"""
    response = client.post("/api/v1/auth/register", json={
        "email": "candidate@test.com",
        "password": "securepass123",
        "role": "candidate"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "candidate@test.com"
    assert data["role"] == "candidate"
    assert "user_id" in data
    assert "confirmation_link" in data  # DEV_MODE


def test_register_duplicate_email(client):
    """Test registration with duplicate email fails"""
    # First registration
    client.post("/api/v1/auth/register", json={
        "email": "duplicate@test.com",
        "password": "password123",
        "role": "candidate"
    })
    
    # Second registration with same email
    response = client.post("/api/v1/auth/register", json={
        "email": "duplicate@test.com",
        "password": "password456",
        "role": "employer"
    })
    
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


def test_email_confirmation_flow(client):
    """Test complete email confirmation flow"""
    # Register
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "confirm@test.com",
        "password": "testpass123",
        "role": "candidate"
    })
    assert reg_response.status_code == 201
    
    # Extract token from DEV_MODE link
    confirmation_link = reg_response.json()["confirmation_link"]
    token = confirmation_link.split("token=")[1]
    
    # Confirm email
    confirm_response = client.post("/api/v1/auth/confirm-email", json={
        "token": token
    })
    assert confirm_response.status_code == 200
    assert "confirmed successfully" in confirm_response.json()["message"].lower()


def test_login_requires_email_confirmation(client):
    """Test that login fails for unconfirmed email"""
    # Register but don't confirm
    client.post("/api/v1/auth/register", json={
        "email": "unconfirmed@test.com",
        "password": "password123",
        "role": "candidate"
    })
    
    # Try to login
    response = client.post("/api/v1/auth/login", json={
        "email": "unconfirmed@test.com",
        "password": "password123"
    })
    
    assert response.status_code == 403
    assert "not confirmed" in response.json()["detail"].lower()


def test_complete_auth_flow(client):
    """Test complete flow: register → confirm → login → access protected endpoint"""
    # 1. Register
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "fullflow@test.com",
        "password": "secure123",
        "role": "employer"
    })
    assert reg_response.status_code == 201
    
    # 2. Confirm email
    token = reg_response.json()["confirmation_link"].split("token=")[1]
    client.post("/api/v1/auth/confirm-email", json={"token": token})
    
    # 3. Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "fullflow@test.com",
        "password": "secure123"
    })
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "fullflow@test.com"
    assert data["user"]["role"] == "employer"
    
    # 4. Access protected endpoint
    access_token = data["access_token"]
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "fullflow@test.com"


def test_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "wrongpass"
    })
    
    assert response.status_code == 401


def test_token_refresh(client):
    """Test token refresh flow"""
    # Register and confirm
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "refresh@test.com",
        "password": "password123",
        "role": "candidate"
    })
    token = reg_response.json()["confirmation_link"].split("token=")[1]
    client.post("/api/v1/auth/confirm-email", json={"token": token})
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "refresh@test.com",
        "password": "password123"
    })
    refresh_token = login_response.json()["refresh_token"]
    
    # Refresh access token
    refresh_response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data  # New refresh token
