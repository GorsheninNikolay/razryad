import pytest
from app.services.invitations import create_invitation, serialize_candidate_for_employer
import datetime

def test_invitation_no_salary():
    with pytest.raises(ValueError, match="Вилка ЗП обязательна"):
        create_invitation(
            employer_id="e1", candidate_id="c1", subject="Subj", message="Msg",
            salary_min=None, salary_max=None, company_name="C",
            contact_person="P", contact_method="M", expires_at=datetime.datetime.utcnow()
        )

def test_pseudonymization_before_accept():
    candidate = {
        "id": "a7f3bxyz",
        "specialization": "Backend",
        "grade": "Middle",
        "fio": "Ivan Ivanov",
        "contacts": "ivan@example.com",
        "workplace": "Yandex",
        "skills": ["python"]
    }
    
    res = serialize_candidate_for_employer(candidate, "sent")
    assert "fio" not in res
    assert "contacts" not in res
    assert "workplace" not in res
    assert res["pseudonym"] == "Backend · Middle · #A7F3"
    
    res2 = serialize_candidate_for_employer(candidate, "accepted")
    assert "fio" in res2
    assert res2["fio"] == "Ivan Ivanov"
    assert "contacts" in res2
