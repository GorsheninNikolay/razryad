import datetime
from typing import Dict, Any, Optional

def create_invitation(
    employer_id: str,
    candidate_id: str,
    subject: str,
    message: str,
    salary_min: Optional[int],
    salary_max: Optional[int],
    company_name: str,
    contact_person: str,
    contact_method: str,
    expires_at: datetime.datetime
) -> dict:
    if not salary_min or not salary_max:
        raise ValueError("Вилка ЗП обязательна для создания приглашения")
        
    # TODO: rate limit & trust score checks
    
    invitation = {
        "id": "inv_123",
        "employer_id": employer_id,
        "candidate_id": candidate_id,
        "subject": subject,
        "message": message,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "company_name": company_name,
        "contact_person": contact_person,
        "contact_method": contact_method,
        "status": "sent",
        "expires_at": expires_at,
        "created_at": datetime.datetime.utcnow()
    }
    return invitation

def accept_invitation(invitation: dict) -> dict:
    if invitation["status"] not in ["sent", "viewed"]:
        raise ValueError("Cannot accept invitation in status: " + invitation["status"])
        
    invitation["status"] = "accepted"
    
    # Create ContactRevealLog
    reveal_log = {
        "invitation_id": invitation["id"],
        "revealed_at": datetime.datetime.utcnow(),
        "employer_id": invitation["employer_id"],
        "candidate_id": invitation["candidate_id"]
    }
    
    return {
        "status": "accepted",
        "employer_contacts": {
            "company_name": invitation["company_name"],
            "contact_person": invitation["contact_person"],
            "contact_method": invitation["contact_method"]
        },
        "candidate_contacts_revealed": True,
        "reveal_log": reveal_log
    }

def serialize_candidate_for_employer(candidate: dict, invitation_status: str) -> dict:
    """Псевдонимизация до согласия.
    
    Per contract §5: before invitation acceptance, employer sees:
    - Specialization, grade, skills, fsp_highlights (always)
    - team_role, work_format, years_of_experience (always - per §5)
    - pseudonym (before acceptance)
    - NO bio, city, workplace, FIO, contacts, email, phone (hidden)
    """
    grade_value = candidate.get("grade", "Middle")
    grade_names = {0: "Intern", 1: "Junior", 2: "Middle", 3: "Senior", 4: "Lead"}
    if isinstance(grade_value, int):
        grade_value = grade_names.get(grade_value, "Middle")
    
    res = {
        "id": candidate["id"],
        "specialization": candidate.get("specialization", "Backend"),
        "grade": grade_value,
        "skills": candidate.get("skills", []),
        "fsp_highlights": candidate.get("fsp_highlights", []),
        # Per §5: these are visible before invitation acceptance
        "team_role": candidate.get("team_role"),
        "work_format": candidate.get("work_format"),
        "years_of_experience": candidate.get("years_of_experience")
    }
    
    if invitation_status == "accepted":
        res["fio"] = candidate.get("fio")
        res["contacts"] = candidate.get("contacts")
        res["workplace"] = candidate.get("workplace")
        res["bio"] = candidate.get("bio")
    else:
        # псевдонимизация
        short_id = str(candidate["id"])[:4].upper()
        res["pseudonym"] = f"{res['specialization']} · {res['grade']} · #{short_id}"
        # Make sure no personal data is leaked
        res.pop("fio", None)
        res.pop("contacts", None)
        res.pop("workplace", None)
        res.pop("bio", None)
        
    return res
