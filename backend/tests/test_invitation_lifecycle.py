from .test_employer_path import auth_employer, auth_candidate
import pytest
import uuid

def test_invitation_salary_validation(client, test_db, auth_employer, auth_candidate):
    from app.core.security import get_current_user, require_employer
    from app.core.db import get_db
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    payload = {
        "candidate_id": str(auth_candidate["candidate_id"]),
        "subject": "Hi",
        "message": "We invite you",
        "salary_min": 200,
        "salary_max": 100, # ERROR
        "company_name": "Test Co",
        "contact_person": "HR",
        "contact_method": "hr@test.com"
    }
    r = client.post("/api/v1/invitations/", json=payload)
    assert r.status_code == 422
    assert "Минимальная зарплата не может быть больше максимальной" in r.text
    
    payload["salary_min"] = 0
    payload["salary_max"] = 100
    r = client.post("/api/v1/invitations/", json=payload)
    assert r.status_code == 422
    assert "Минимальная зарплата должна быть больше нуля" in r.text
    
    payload["salary_min"] = 100
    r = client.post("/api/v1/invitations/", json=payload)
    assert r.status_code == 201

def test_invitation_lifecycle(client, test_db, auth_employer, auth_candidate):
    from app.core.security import get_current_user, require_employer, require_candidate
    from app.core.db import get_db
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    def override_require_candidate():
        return {"id": auth_candidate["user_id"], "email": "cand@test.com", "role": "candidate"}

    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # Create
    payload = {
        "candidate_id": str(auth_candidate["candidate_id"]),
        "subject": "Hi", "message": "msg",
        "salary_min": 100, "salary_max": 200,
        "company_name": "Test Co", "contact_person": "HR", "contact_method": "x"
    }
    r = client.post("/api/v1/invitations/", json=payload)
    inv_id = r.json()["id"]
    
    # Candidate lists incoming
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_require_candidate
    
    r = client.get("/api/v1/invitations/incoming")
    assert r.status_code == 200
    
    # Should transition to viewed automatically
    r = client.get(f"/api/v1/invitations/{inv_id}/history")
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 2
    assert history[0]["to_status"] == "sent"
    assert history[1]["to_status"] == "viewed"
    
    # Employer withdraws
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    r = client.post(f"/api/v1/invitations/{inv_id}/withdraw")
    assert r.status_code == 200
    assert r.json()["status"] == "withdrawn"
    
    # Cannot accept withdrawn
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_require_candidate
    
    r = client.post(f"/api/v1/invitations/{inv_id}/accept")
    assert r.status_code == 400



def test_invitation_contact_reveal(client, test_db, auth_employer, auth_candidate):
    from app.core.security import get_current_user, require_employer, require_candidate
    from app.core.db import get_db
    from app.models.models import ContactRevealLog
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    def override_require_candidate():
        return {"id": auth_candidate["user_id"], "email": "cand@test.com", "role": "candidate"}

    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    payload = {
        "candidate_id": str(auth_candidate["candidate_id"]),
        "subject": "Hi", "message": "msg",
        "salary_min": 100, "salary_max": 200,
        "company_name": "Test Co", "contact_person": "HR", "contact_method": "x"
    }
    r = client.post("/api/v1/invitations/", json=payload)
    inv_id = r.json()["id"]
    
    # Check before accept (employer view)
    r = client.get("/api/v1/invitations/sent")
    inv = next(i for i in r.json() if i["id"] == inv_id)
    assert inv["candidate_fio"] is None, "Contacts should be hidden before accept"
    assert inv["candidate_contacts"] is None
    assert inv["candidate_pseudonym"] is not None
    
    # Candidate accepts
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_require_candidate
    
    incoming = client.get("/api/v1/invitations/incoming")
    viewed = next(i for i in incoming.json() if i["id"] == inv_id)
    assert viewed["status"] == "viewed"
    assert viewed["subject"] == payload["subject"]
    assert viewed["message"] == payload["message"]
    r = client.post(f"/api/v1/invitations/{inv_id}/accept")
    assert r.status_code == 200
    
    # Check after accept (employer view)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    r = client.get("/api/v1/invitations/sent")
    inv = next(i for i in r.json() if i["id"] == inv_id)
    assert inv["candidate_fio"] is not None, "FIO should be revealed after accept"
    assert inv["candidate_contacts"] is not None
    assert inv["candidate_pseudonym"] is None, "Pseudonym should be removed"
    
    contacts = inv["candidate_contacts"]
    fio = inv["candidate_fio"]
    r = client.post(f"/api/v1/invitations/{inv_id}/hire")
    assert r.status_code == 200
    r = client.get("/api/v1/invitations/sent")
    hired = next(i for i in r.json() if i["id"] == inv_id)
    assert hired["status"] == "hired"
    assert hired["candidate_contacts"] == contacts
    assert hired["candidate_fio"] == fio
    assert hired["candidate_pseudonym"] is None

    # Check decline branch
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    r = client.post("/api/v1/invitations/", json=payload)
    inv_id_2 = r.json()["id"]
    
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_candidate] = override_require_candidate
    client.app.dependency_overrides[get_current_user] = override_require_candidate
    
    client.post(f"/api/v1/invitations/{inv_id_2}/decline")
    
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    r = client.get("/api/v1/invitations/sent")
    inv_2 = next(i for i in r.json() if i["id"] == inv_id_2)
    assert inv_2["candidate_fio"] is None, "Contacts should remain hidden after decline"
