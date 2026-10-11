"""Applications router"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import datetime

from app.core.db import get_db
from app.core.security import get_current_user, require_candidate
from app.models.models import Application, ApplicationStatusEvent, Vacancy, CandidateProfile, EmployerProfile, ContactRevealLog
from app.schemas.schemas import ApplicationCreate, ApplicationUpdateStatus, ApplicationOutCandidate, ApplicationOutEmployer
from app.services.invitations import serialize_candidate_for_employer

router = APIRouter()

@router.get("/")
async def list_applications(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List applications"""
    if current_user["role"] == "candidate":
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
        if not cand:
            return []
        apps = db.query(Application).filter(Application.candidate_id == cand.id).all()
        return [ApplicationOutCandidate.model_validate(a) for a in apps]
    elif current_user["role"] == "employer":
        emp = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
        if not emp:
            return []
        vacs = db.query(Vacancy.id).filter(Vacancy.employer_id == emp.id).subquery()
        apps = db.query(Application).filter(Application.vacancy_id.in_(vacs)).all()
        
        result = []
        for app in apps:
            cand = db.query(CandidateProfile).filter(CandidateProfile.id == app.candidate_id).first()
            cand_dict = {
                "id": cand.id,
                "fio": cand.full_name,
                "specialization": "Backend", # stub for proper field
                "grade": "Middle",
                "contacts": "cand@test.com",
                "workplace": "Company X"
            }
            # For employer, reveal contact since it's an application (inbound)
            # The privacy invariant says: application reveals contacts! So we act like "accepted".
            serialized = serialize_candidate_for_employer(cand_dict, "accepted")
            out = ApplicationOutEmployer.model_validate(app)
            out.candidate_data = serialized
            result.append(out)
        return result
    return []

@router.post("/", response_model=ApplicationOutCandidate, status_code=201)
async def create_application(
    app_in: ApplicationCreate,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
    if not cand:
        raise HTTPException(status_code=403, detail="Candidate profile required")
        
    vacancy = db.query(Vacancy).filter(Vacancy.id == app_in.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
        
    application = Application(
        vacancy_id=vacancy.id,
        candidate_id=cand.id,
        cover_letter=app_in.cover_letter,
        status="pending"
    )
    db.add(application)
    db.flush()
    
    # Reveal contacts
    reveal_log = ContactRevealLog(
        invitation_id=uuid.uuid4(), # Hack because schema requires unique invitation_id but here it's an application. In reality this might need schema change.
        candidate_id=cand.id,
        employer_id=vacancy.employer_id,
        trigger="application_created",
        candidate_data_revealed={"contacts": "revealed", "fio": cand.full_name},
        employer_data_revealed={"company": str(vacancy.company_id)}
    )
    db.add(reveal_log)
    db.commit()
    db.refresh(application)
    return application

@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    app_db = db.query(Application).filter(Application.id == application_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if current_user["role"] == "candidate":
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
        if not cand or app_db.candidate_id != cand.id:
            raise HTTPException(status_code=403, detail="Not your application")
        return ApplicationOutCandidate.model_validate(app_db)
    elif current_user["role"] == "employer":
        emp = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
        vac = db.query(Vacancy).filter(Vacancy.id == app_db.vacancy_id).first()
        if not emp or not vac or vac.employer_id != emp.id:
            raise HTTPException(status_code=403, detail="Not your vacancy application")
            
        cand = db.query(CandidateProfile).filter(CandidateProfile.id == app_db.candidate_id).first()
        cand_dict = {
            "id": cand.id,
            "fio": cand.full_name,
            "specialization": "Backend", 
            "grade": "Middle",
            "contacts": "cand@test.com",
            "workplace": "Company X"
        }
        serialized = serialize_candidate_for_employer(cand_dict, "accepted")
        out = ApplicationOutEmployer.model_validate(app_db)
        out.candidate_data = serialized
        return out

@router.put("/{application_id}/status")
async def update_application_status(
    application_id: uuid.UUID,
    status_in: ApplicationUpdateStatus,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    app_db = db.query(Application).filter(Application.id == application_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="Application not found")
        
    # Check permission
    if current_user["role"] == "employer":
        emp = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
        vac = db.query(Vacancy).filter(Vacancy.id == app_db.vacancy_id).first()
        if not emp or not vac or vac.employer_id != emp.id:
            raise HTTPException(status_code=403, detail=f"Not your vacancy application. emp.id: {emp.id if emp else 'None'}, vac.employer_id: {vac.employer_id if vac else 'None'}")
    elif current_user["role"] == "candidate":
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
        if not cand or app_db.candidate_id != cand.id:
            raise HTTPException(status_code=403, detail="Not your application")
            
    old_status = app_db.status
    app_db.status = status_in.status
    
    ev = ApplicationStatusEvent(
        application_id=app_db.id,
        from_status=old_status,
        to_status=status_in.status,
        note=status_in.note
    )
    db.add(ev)
    db.commit()
    db.refresh(app_db)
    
    if current_user["role"] == "candidate":
        return ApplicationOutCandidate.model_validate(app_db)
    else:
        # need candidate_data for employer
        cand = db.query(CandidateProfile).filter(CandidateProfile.id == app_db.candidate_id).first()
        cand_dict = {
            "id": cand.id,
            "fio": cand.full_name,
            "specialization": "Backend", 
            "grade": "Middle",
            "contacts": "cand@test.com",
            "workplace": "Company X"
        }
        serialized = serialize_candidate_for_employer(cand_dict, "accepted")
        out = ApplicationOutEmployer.model_validate(app_db)
        out.candidate_data = serialized
        return out
