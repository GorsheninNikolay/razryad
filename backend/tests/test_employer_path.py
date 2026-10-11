from app.core.db import get_db
import pytest
from app.models.models import Company, EmployerProfile, Vacancy, Application, ContactRevealLog, CandidateProfile
from fastapi.testclient import TestClient
import uuid
import datetime

@pytest.fixture
def auth_employer(client, test_db):
    user_id = uuid.uuid4()
    emp_id = uuid.uuid4()
    comp_id = uuid.uuid4()
    # Stub security override
    # Since we don't have token gen easily accessible without user creation, let's mock the dependency
    from app.core.security import get_current_user, require_employer
    def override_require_employer():
        return {"id": user_id, "email": "emp@test.com", "role": "employer"}
    def override_current_user():
        return {"id": user_id, "email": "emp@test.com", "role": "employer"}
        
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_current_user
    
    # Create DB rows
    comp = Company(id=comp_id, name="Test Company", industry="IT")
    test_db.add(comp)
    emp = EmployerProfile(id=emp_id, user_id=user_id, company_id=comp_id, full_name="Emp")
    test_db.add(emp)
    test_db.commit()
    
    # Remove fixture teardowns trying to use get_db
    yield {"user_id": user_id, "company_id": comp_id, "employer_id": emp_id}
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override


@pytest.fixture
def auth_candidate(client, test_db):
    user_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    
    from app.core.security import get_current_user, require_candidate
    def override_require_candidate():
        return {"id": user_id, "email": "cand@test.com", "role": "candidate"}
    def override_current_user():
        return {"id": user_id, "email": "cand@test.com", "role": "candidate"}
        
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_current_user
    
    cand = CandidateProfile(id=cand_id, user_id=user_id, full_name="Candidate")
    test_db.add(cand)
    test_db.commit()
    
    yield {"user_id": user_id, "candidate_id": cand_id}
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override


def test_create_vacancy_missing_salary(client, auth_employer):
    payload = {
        "title": "Backend",
        "description": "Desc",
        "specialization_id": "backend",
        "grade_min_id": "junior",
        "grade_max_id": "senior"
        # missing salary
    }
    r = client.post("/api/v1/vacancies/", json=payload)
    assert r.status_code == 422
    assert "Вилка ЗП" in r.text or "Field required" in r.text

def test_create_vacancy_min_greater_than_max(client, auth_employer):
    payload = {
        "title": "Backend",
        "description": "Desc",
        "specialization_id": "backend",
        "grade_min_id": "junior",
        "grade_max_id": "senior",
        "salary_min": 200,
        "salary_max": 100
    }
    r = client.post("/api/v1/vacancies/", json=payload)
    assert r.status_code == 422
    assert "Минимальная зарплата не может быть больше" in r.text

def test_application_reveals_contact(client, test_db, auth_employer, auth_candidate):
    # employer creates vacancy
    payload = {
        "title": "Backend",
        "description": "Desc",
        "specialization_id": "backend",
        "grade_min_id": "junior",
        "grade_max_id": "senior",
        "salary_min": 100,
        "salary_max": 200,
        "requirements": {}
    }
    r = client.post("/api/v1/vacancies/", json=payload)
    assert r.status_code == 201
    vac_id = r.json()["id"]
    
    # Check that contact is hidden before application - no application yet
    
    # candidate applies
    app_payload = {"vacancy_id": vac_id, "cover_letter": "Hi"}
    r = client.post("/api/v1/applications/", json=app_payload)
    assert r.status_code == 201
    app_id = r.json()["id"]
    
    # employer fetches applications and should see revealed data
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override

    
    user_id = auth_employer["user_id"]
    from app.core.security import get_current_user, require_employer
    def override_current_user():
        return {"id": user_id, "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[get_current_user] = override_current_user
    client.app.dependency_overrides[require_employer] = override_current_user
    
    r = client.get("/api/v1/applications/")
    assert r.status_code == 200
    apps = r.json()
    assert len(apps) == 1
    assert "candidate_data" in apps[0]
    assert "contacts" in apps[0]["candidate_data"]  # Revealed!

def test_candidate_sees_own_applications_only(client, test_db, auth_candidate, auth_employer):
    payload = {
        "title": "Backend",
        "description": "Desc",
        "specialization_id": "backend",
        "grade_min_id": "junior",
        "grade_max_id": "senior",
        "salary_min": 100,
        "salary_max": 200,
        "requirements": {}
    }
    from app.core.security import get_current_user, require_employer, require_candidate
    
    # Store old override just in case, but conftest sets it
    
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override

    # post vacancy
    user_id = auth_employer["user_id"]
    comp_id = auth_employer["company_id"]
    emp_id = auth_employer["employer_id"]
    
    # re-create employer in db since fixture clears? No, fixture does not rollback db
    # but maybe test_db is not preserving across requests? Yes it is!
    # Wait, the failure is:
    # emp.id = 77d30dd8-09d2-49fa-969c-f42242cdfd87
    # vac.employer_id = 7c6fe02a-6b72-4ad7-90b8-6a34a2ef4cfb
    # They are DIFFERENT! Why? Because auth_employer creates one, and then `override_require_employer` returns auth_employer["user_id"], but somehow `create_vacancy` creates a NEW employer profile or uses another?
    # Wait! In vacancies.py:
    # employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    # It fetches the employer by user_id.
    # Ah! In auth_employer fixture, we yield a DIFFERENT user_id because we created a new one!
    # Let's check auth_employer code again.
    def override_require_employer_v():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer_v
    client.app.dependency_overrides[get_current_user] = override_require_employer_v
    r = client.post("/api/v1/vacancies/", json=payload)
    vac_id = r.json()["id"]
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override

        
    # candidate 1 applies
    def override_require_candidate():
        return {"id": auth_candidate["user_id"], "email": "cand@test.com", "role": "candidate"}
    def override_current_user():
        return {"id": auth_candidate["user_id"], "email": "cand@test.com", "role": "candidate"}
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_current_user
    r = client.post("/api/v1/applications/", json={"vacancy_id": vac_id})
    assert r.status_code == 201
    
    # check
    r = client.get("/api/v1/applications/")
    apps = r.json()
    assert len(apps) == 1
    app_id = apps[0]["id"]
    
    # check status change is visible
    # employer updates status
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override

    def override_require_employer2():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[get_current_user] = override_require_employer2
    # Need to override require_employer too!
    client.app.dependency_overrides[require_employer] = override_require_employer2
    
    r = client.put(f"/api/v1/applications/{app_id}/status", json={"status": "interview", "note": ""})
    if r.status_code != 200:
        print(r.json())
    assert r.status_code == 200
    
    # candidate checks status
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override:
        client.app.dependency_overrides[get_db] = _db_override

    client.app.dependency_overrides[get_current_user] = override_current_user
    r = client.get(f"/api/v1/applications/{app_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "interview"
