"""Test health check endpoint"""


def test_health_check(client):
    """Test /health endpoint returns 200"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


def test_health_check_structure(client):
    """Test health check response structure"""
    response = client.get("/health")
    data = response.json()
    
    assert isinstance(data, dict)
    assert data["service"] == "РАЗРЯД API"
    assert data["version"] == "0.1.0"
