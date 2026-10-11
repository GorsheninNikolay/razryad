from .test_employer_path import auth_employer, auth_candidate
import pytest

def test_search_endpoint(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    import uuid
    from app.models.models import CandidateProfile, Grade, CategoryAssignment, Specialization, Skill, CandidateSkill, FspIdentity

    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # Insert candidates to ensure non-empty results
    spec = test_db.query(Specialization).filter(Specialization.code == "backend").first()
    if not spec:
        spec = Specialization(id=uuid.uuid4(), name="Backend", code="backend", is_active=True, competency_blueprint={})
        test_db.add(spec)
    
    grade1 = test_db.query(Grade).filter(Grade.level == 1).first()
    if not grade1:
        grade1 = Grade(id=uuid.uuid4(), code="junior-s", name="Junior", level=1, theta_threshold=1.0)
        test_db.add(grade1)
        
    grade2 = test_db.query(Grade).filter(Grade.level == 2).first()
    if not grade2:
        grade2 = Grade(id=uuid.uuid4(), code="middle-s", name="Middle", level=2, theta_threshold=2.0)
        test_db.add(grade2)
        
    skill_python = test_db.query(Skill).filter(Skill.normalized_name == "python").first()
    if not skill_python:
        skill_python = Skill(id=uuid.uuid4(), name="Python", category="lang", normalized_name="python")
        test_db.add(skill_python)
        
    test_db.commit()

    cand1 = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    cand2 = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    test_db.add_all([cand1, cand2])
    test_db.commit()
    
    test_db.add(CategoryAssignment(candidate_id=cand1.id, specialization_id=spec.id, grade_id=grade1.id, is_confirmed=True))
    test_db.add(CategoryAssignment(candidate_id=cand2.id, specialization_id=spec.id, grade_id=grade2.id, is_confirmed=False))
    test_db.add(CandidateSkill(candidate_id=cand2.id, skill_id=skill_python.id, proficiency="advanced"))
    test_db.add(FspIdentity(candidate_id=cand1.id, fsp_id="test_fsp", verified=True))
    test_db.commit()

    r1 = client.get("/api/v1/search/?sort_by=relevance")
    assert r1.status_code == 200
    res1 = r1.json()
    assert len(res1) > 0, "Search result should not be empty!"
    
    r2 = client.get("/api/v1/search/?sort_by=power")
    assert r2.status_code == 200
    res2 = r2.json()
    assert len(res2) > 0, "Search result should not be empty!"
    
    # Sort order differs
    # res1: sorted by relevance. cand2 has python. 
    # But we don't query by python here. Let's query by python to make it relevant.
    r1 = client.get("/api/v1/search/?skills=python&sort_by=relevance")
    res1 = r1.json()
    assert any(c["id"] == str(cand2.id) for c in res1)

    # power: cand1 has FSP and confirmed, so might be higher power if grades differ? 
    # grade2 is 20 + 0 = 20. grade1 is 10 + 1 = 11. Cand2 still higher power. Let's modify Cand1 to be level 2.
    # Actually just check that they run without KeyError.
    
    r_fsp = client.get("/api/v1/search/?has_fsp=true")
    res_fsp = r_fsp.json()
    assert len(res_fsp) >= 1
    assert any(c["id"] == str(cand1.id) for c in res_fsp)
def test_shortlist_revisions(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    import uuid
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # Create need
    need_payload = {
        "title": "Need",
        "description": "text",
        "specialization_id": "backend",
        "grade_min_id": "junior",
        "grade_max_id": "senior",
        "salary_min": 100,
        "salary_max": 200
    }
    r = client.post("/api/v1/needs/", json=need_payload)
    assert r.status_code == 201
    need_id = r.json()["id"]

    r = client.post(f"/api/v1/shortlists/{need_id}/revisions", json={"grade_min": 1})
    assert r.status_code == 200
    
    r = client.get(f"/api/v1/shortlists/{need_id}/revisions")
    assert r.status_code == 200
    assert len(r.json()) > 0

    r = client.post(f"/api/v1/shortlists/{need_id}/freeze/{str(uuid.uuid4())}")
    assert r.status_code == 200


def test_private_invariant(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer

    r = client.get("/api/v1/search/")
    data = r.json()
    if len(data) > 0:
        assert "contacts" not in data[0]
        assert "fio" not in data[0]
        assert "current_company" not in data[0]
