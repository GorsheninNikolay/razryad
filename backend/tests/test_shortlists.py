import datetime
from .test_employer_path import auth_employer, auth_candidate
import pytest
import uuid

def test_shortlist_ranking(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    
    # Needs to inject actual mock DB context correctly
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
        
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # 1. We need some candidates, specializations and skills in the DB.
    # We will let the test populate them.
    from app.models.models import CandidateProfile, Grade, CandidateSkill, Skill, Specialization, CategoryAssignment
    
    spec = test_db.query(Specialization).filter(Specialization.code == "backend").first()
    if not spec:
        spec = Specialization(id=uuid.uuid4(), code="backend", name="Backend", is_active=True, competency_blueprint={})
        test_db.add(spec)
    
    grade1 = test_db.query(Grade).filter(Grade.level == 1).first()
    if not grade1:
        grade1 = Grade(id=uuid.uuid4(), code="junior", name="Junior", level=1, theta_threshold=1.0)
        test_db.add(grade1)
        
    grade2 = test_db.query(Grade).filter(Grade.level == 2).first()
    if not grade2:
        grade2 = Grade(id=uuid.uuid4(), code="middle", name="Middle", level=2, theta_threshold=2.0)
        test_db.add(grade2)
        
    grade3 = test_db.query(Grade).filter(Grade.level == 3).first()
    if not grade3:
        grade3 = Grade(id=uuid.uuid4(), code="senior", name="Senior", level=3, theta_threshold=3.0)
        test_db.add(grade3)
    
    skill1 = test_db.query(Skill).filter(Skill.normalized_name == "python").first()
    if not skill1:
        skill1 = Skill(id=uuid.uuid4(), name="Python", category="language", normalized_name="python")
        test_db.add(skill1)
        
    skill2 = test_db.query(Skill).filter(Skill.normalized_name == "docker").first()
    if not skill2:
        skill2 = Skill(id=uuid.uuid4(), name="Docker", category="tool", normalized_name="docker")
        test_db.add(skill2)
        
    test_db.commit()
    
    # C1: Middle Backend, has python and docker
    cand1 = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    test_db.add(cand1)
    test_db.commit()
    test_db.add(CategoryAssignment(candidate_id=cand1.id, specialization_id=spec.id, grade_id=grade2.id, is_confirmed=True))
    test_db.add(CandidateSkill(candidate_id=cand1.id, skill_id=skill1.id, proficiency="advanced"))
    test_db.add(CandidateSkill(candidate_id=cand1.id, skill_id=skill2.id, proficiency="advanced"))
    
    # C2: Senior Backend, has python, missing docker
    cand2 = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    test_db.add(cand2)
    test_db.commit()
    test_db.add(CategoryAssignment(candidate_id=cand2.id, specialization_id=spec.id, grade_id=grade3.id, is_confirmed=True))
    test_db.add(CandidateSkill(candidate_id=cand2.id, skill_id=skill1.id, proficiency="advanced"))
    
    # C3: Junior Backend, missing both
    cand3 = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    test_db.add(cand3)
    test_db.commit()
    test_db.add(CategoryAssignment(candidate_id=cand3.id, specialization_id=spec.id, grade_id=grade1.id, is_confirmed=False))
    
    test_db.commit()

    # Create need
    need_payload = {
        "title": "Need Backend",
        "description": "text",
        "specialization_id": str(spec.id),
        "grade_min_id": str(grade1.id),
        "grade_max_id": str(grade2.id),
        "must_have_skills": ["python", "docker"],
        "salary_min": 100,
        "salary_max": 200
    }
    r = client.post("/api/v1/needs/", json=need_payload)
    assert r.status_code == 201
    need_id = r.json()["id"]
    
    # Fetch shortlist
    r = client.get(f"/api/v1/shortlists/{need_id}")
    assert r.status_code == 200
    
    data = r.json()
    assert data["total_filtered"] >= 3
    items = data["items"]
    
    assert next(item for item in items if item["candidate"]["id"] == str(cand1.id))["candidate"]["is_confirmed"] is True
    assert next(item for item in items if item["candidate"]["id"] == str(cand3.id))["candidate"]["is_confirmed"] is False
    senior = next(item for item in items if item["candidate"]["id"] == str(cand2.id))
    assert senior["candidate"]["is_confirmed"] is True
    assert senior["explanation"]["grade_match"] == .8

    # Check that scores are ordered
    scores = [item["match_score"] for item in items]
    assert scores == sorted(scores, reverse=True)
    
    # Top should be cand1 (has both skills and correct grade)
    assert items[0]["candidate"]["id"] == str(cand1.id)
    assert "python" in items[0]["explanation"]["skills_matched"]
    assert items[0]["explanation"]["grade_qualifier"] != "Не в диапазоне"
    assert items[0]["explanation"]["grade_match"] > 0
    
    # Assert missing logic correctly detected
    assert "docker" in items[1]["explanation"]["skills_missing"]
    

def test_fsp_pool_percentile(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    import uuid
    from app.models.models import CandidateProfile, Grade, CategoryAssignment, FspIdentity, Specialization
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # We need a specialization and a grade
    spec = test_db.query(Specialization).first()
    grade = test_db.query(Grade).first()
    
    # Create two candidates in the same pool, one with FSP and one without
    cand_fsp = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    cand_no_fsp = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    test_db.add_all([cand_fsp, cand_no_fsp])
    test_db.commit()
    
    test_db.add(CategoryAssignment(candidate_id=cand_fsp.id, specialization_id=spec.id, grade_id=grade.id, is_confirmed=True))
    test_db.add(CategoryAssignment(candidate_id=cand_no_fsp.id, specialization_id=spec.id, grade_id=grade.id, is_confirmed=True))
    test_db.commit()
    
    fsp_id_row = FspIdentity(candidate_id=cand_fsp.id, fsp_id="FSP-TEST", verified=True)
    test_db.add(fsp_id_row)
    test_db.commit()
    from app.models.models import FspAchievement
    test_db.add(FspAchievement(fsp_identity_id=fsp_id_row.id, event_name="Olympiad", event_level="international", place=1, event_date=datetime.datetime(2023, 1, 1).date(), discipline="Programming", verification_status="verified"))
    test_db.commit()
    
    # Create need
    need_payload = {
        "title": "Need Backend",
        "description": "text",
        "specialization_id": str(spec.id),
        "grade_min_id": str(grade.id),
        "grade_max_id": str(grade.id),
        "must_have_skills": [],
        "salary_min": 100,
        "salary_max": 200
    }
    r = client.post("/api/v1/needs/", json=need_payload)
    need_id = r.json()["id"]
    
    r = client.get(f"/api/v1/shortlists/{need_id}")
    items = r.json()["items"]
    
    # Check that cand_no_fsp is not penalized with 0 because of variance vs cand_fsp
    # Wait, the rule is "отсутствие истории ФСП не является штрафом".
    # Because there IS variance (0.8 and 0.0), the formula in `matching.py` says `a_fsp = fsp_pool_percentile`.
    # Cand_fsp will get 1.0 (max), Cand_no_fsp will get 0.0 (min). 
    # BUT wait! If variance is not zero, cand_no_fsp gets 0.0 percentile, meaning 0.0 * weight_fsp = 0 points for FSP.
    # While cand_fsp gets 1.0 * weight_fsp points. Is that a penalty? "Отсутствие ФСП не является штрафом, но наличие даёт бонус". Yes, that means 0 is just base.
    
    # Let's ensure the scores differ correctly
    cand_fsp_item = next(i for i in items if i["candidate"]["id"] == str(cand_fsp.id))
    cand_no_fsp_item = next(i for i in items if i["candidate"]["id"] == str(cand_no_fsp.id))
    
    assert cand_fsp_item["match_score"] > cand_no_fsp_item["match_score"]
import pytest
import uuid

def test_revisions_and_freeze_idor(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    from app.models.models import Need, EmployerProfile, User, ShortlistRevision
    
    # We need a secondary employer to test IDOR
    emp2_id = uuid.uuid4()
    emp2_user_id = uuid.uuid4()
    test_db.add(User(id=emp2_user_id, email="emp2@test.com", role="employer", password_hash="x", email_confirmed=True))
    test_db.add(EmployerProfile(id=emp2_id, user_id=emp2_user_id, company_id=auth_employer["company_id"], full_name="emp2", position="pos", phone="123"))
    test_db.commit()

    # Create need as auth_employer
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # Fetch random spec and grade
    from app.models.models import Specialization, Grade
    spec = test_db.query(Specialization).filter(Specialization.code == "backend").first()
    grade = test_db.query(Grade).first()
    
    need_payload = {
        "title": "Need Backend",
        "description": "text",
        "specialization_id": str(spec.id),
        "grade_min_id": str(grade.id),
        "grade_max_id": str(grade.id),
        "must_have_skills": [],
        "salary_min": 100,
        "salary_max": 200
    }
    r = client.post("/api/v1/needs/", json=need_payload)
    need_id = r.json()["id"]
    
    # Switch to employer 2
    def override_require_employer2():
        return {"id": emp2_user_id, "email": "emp2@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer2
    client.app.dependency_overrides[get_current_user] = override_require_employer2
    
    # Attempt to access revisions
    r_rev = client.get(f"/api/v1/shortlists/{need_id}/revisions")
    assert r_rev.status_code == 404, "IDOR in list_revisions"
    
    # Attempt to create revision
    r_create = client.post(f"/api/v1/shortlists/{need_id}/revisions", json={"grade_min": 1})
    assert r_create.status_code == 404, "IDOR in create_revision"
    
    # Attempt to freeze candidate
    r_freeze = client.post(f"/api/v1/shortlists/{need_id}/freeze/{uuid.uuid4()}")
    assert r_freeze.status_code == 404, "IDOR in freeze_candidate"
    
def test_search_specialization_codes(client, test_db, auth_employer):
    from app.core.security import require_employer, get_current_user
    from app.core.db import get_db
    
    _db_override = client.app.dependency_overrides.get(get_db)
    client.app.dependency_overrides.clear()
    if _db_override: client.app.dependency_overrides[get_db] = _db_override
    
    def override_require_employer():
        return {"id": auth_employer["user_id"], "email": "emp@test.com", "role": "employer"}
    client.app.dependency_overrides[require_employer] = override_require_employer
    client.app.dependency_overrides[get_current_user] = override_require_employer
    
    # By code
    r = client.get("/api/v1/search/?specialization_id=backend")
    assert r.status_code == 200
    
    # By fake code
    r = client.get("/api/v1/search/?specialization_id=fake-code")
    assert r.status_code == 422
    assert "Valid codes" in r.text
    
    # By UUID
    from app.models.models import Specialization
    spec = test_db.query(Specialization).filter(Specialization.code == "backend").first()
    r = client.get(f"/api/v1/search/?specialization_id={spec.id}")
    assert r.status_code == 200

