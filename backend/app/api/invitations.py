from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import datetime

from app.core.db import get_db
from app.core.security import get_current_user, require_employer, require_candidate
from app.models.models import Invitation, EmployerProfile, CandidateProfile, ContactRevealLog, InvitationStatusEvent
from app.schemas.needs import InvitationCreate, InvitationOut, InvitationStatusUpdate
from app.services.invitations import serialize_candidate_for_employer

router = APIRouter()

@router.post("/", response_model=InvitationOut, status_code=201)
async def create_invitation(
    inv_in: InvitationCreate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    if inv_in.salary_min is None or inv_in.salary_max is None:
        raise HTTPException(status_code=422, detail="Вилка ЗП обязательна для создания приглашения")
    if inv_in.salary_min <= 0:
        raise HTTPException(status_code=422, detail="Минимальная зарплата должна быть больше нуля")
    if inv_in.salary_min > inv_in.salary_max:
        raise HTTPException(status_code=422, detail="Минимальная зарплата не может быть больше максимальной")
    
    # Validate that candidate_id is a CandidateProfile, not a User
    candidate_profile = db.query(CandidateProfile).filter(
        CandidateProfile.id == inv_in.candidate_id
    ).first()
    
    if not candidate_profile:
        raise HTTPException(
            status_code=422,
            detail="candidate_id должен быть идентификатором профиля кандидата, а не пользователя"
        )
        
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer profile required")
        
    inv = Invitation(
        employer_id=employer.id,
        candidate_id=inv_in.candidate_id,
        vacancy_id=inv_in.vacancy_id,
        need_id=inv_in.need_id,
        subject=inv_in.subject,
        message=inv_in.message,
        salary_min=inv_in.salary_min,
        salary_max=inv_in.salary_max,
        company_name=inv_in.company_name,
        contact_person=inv_in.contact_person,
        contact_method=inv_in.contact_method,
        expires_at=inv_in.expires_at or (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)),
        status="sent"
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    
    # Add initial event
    ev = InvitationStatusEvent(
        invitation_id=inv.id,
        from_status=None,
        to_status="sent",
        actor="employer"
    )
    db.add(ev)
    db.commit()
    return inv

@router.get("/sent")
async def list_invitations(
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        return []
        
    # Expiration logic
    invs = db.query(Invitation).filter(Invitation.employer_id == employer.id).all()
    now = datetime.datetime.now(datetime.timezone.utc)
    updated = False
    for inv in invs:
        if inv.status in ["sent", "viewed"] and inv.expires_at.replace(tzinfo=datetime.timezone.utc) < now:
            ev = InvitationStatusEvent(invitation_id=inv.id, from_status=inv.status, to_status="expired", actor="system")
            db.add(ev)
            inv.status = "expired"
            updated = True
            
    if updated: db.commit()
    

    from app.services.invitations import serialize_candidate_for_employer
    from app.models.models import ContactRevealLog
    
    res = []
    for inv in invs:
        cand = inv.candidate
        from app.models.models import User
        cand_user = db.query(User).filter(User.id == cand.user_id).first()
        
        cand_data = {
            "id": cand.id,
            "fio": getattr(cand, "full_name", None) or (cand_user.email if cand_user else "Unknown Candidate"),
            "contacts": {"email": cand_user.email if cand_user else "Unknown", "phone": getattr(cand, "phone", None)},
            "workplace": {"company": getattr(cand, "current_company", None), "position": getattr(cand, "current_position", None)}
        }
        
        safe_cand = serialize_candidate_for_employer(cand_data, inv.status)
        
        inv_dict = {
            "id": inv.id,
            "candidate_id": inv.candidate_id,
            "need_id": inv.need_id,
            "vacancy_id": inv.vacancy_id,
            "subject": inv.subject,
            "message": inv.message,
            "salary_min": inv.salary_min,
            "salary_max": inv.salary_max,
            "company_name": inv.company_name,
            "contact_person": inv.contact_person,
            "contact_method": inv.contact_method,
            "expires_at": inv.expires_at,
            "employer_id": inv.employer_id,
            "status": inv.status,
            "created_at": inv.created_at,
            "candidate_fio": safe_cand.get("fio"),
            "candidate_contacts": safe_cand.get("contacts"),
            "candidate_workplace": safe_cand.get("workplace"),
            "candidate_pseudonym": safe_cand.get("pseudonym")
        }
        
        if inv.status == "accepted":
            # ensure logged
            existing_log = db.query(ContactRevealLog).filter(
                ContactRevealLog.employer_id == employer.id,
                ContactRevealLog.candidate_id == cand.id,
                ContactRevealLog.invitation_id == inv.id
            ).first()
            if not existing_log:
                db.add(ContactRevealLog(
                    employer_id=employer.id, 
                    candidate_id=cand.id, 
                    invitation_id=inv.id,
                    revealed_at=datetime.datetime.now(datetime.timezone.utc), 
                    reason="invitation_accepted"
                ))
                db.commit()
                
        res.append(inv_dict)
        
    return res


@router.get("/incoming")
async def list_incoming_invitations(
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
    if not cand:
        return []
        
    invs = db.query(Invitation).filter(Invitation.candidate_id == cand.id).all()
    now = datetime.datetime.now(datetime.timezone.utc)
    updated = False
    for inv in invs:
        if inv.status in ["sent", "viewed"] and inv.expires_at.replace(tzinfo=datetime.timezone.utc) < now:
            ev = InvitationStatusEvent(invitation_id=inv.id, from_status=inv.status, to_status="expired", actor="system")
            db.add(ev)
            inv.status = "expired"
            updated = True
        elif inv.status == "sent" and inv.expires_at.replace(tzinfo=datetime.timezone.utc) >= now:
            # Transition to viewed when candidate loads list
            ev = InvitationStatusEvent(invitation_id=inv.id, from_status="sent", to_status="viewed", actor="candidate")
            db.add(ev)
            inv.status = "viewed"
            updated = True
            
    if updated: db.commit()
    
    return [InvitationOut.model_validate(inv) for inv in invs]

@router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    return await accept_decline_invitation(invitation_id, "accept", current_user, db)

@router.post("/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    return await accept_decline_invitation(invitation_id, "decline", current_user, db)

@router.post("/{invitation_id}/withdraw")
async def withdraw_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    inv = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not inv or not employer or inv.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    old_status = inv.status
    if old_status not in ["sent", "viewed"]:
        raise HTTPException(status_code=400, detail=f"Cannot withdraw invitation in status {old_status}")
        
    inv.status = "withdrawn"
    ev = InvitationStatusEvent(invitation_id=inv.id, from_status=old_status, to_status="withdrawn", actor="employer")
    db.add(ev)
    db.commit()
    return {"status": inv.status}

@router.post("/{invitation_id}/hire")
async def hire_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    inv = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not inv or not employer or inv.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    old_status = inv.status
    if old_status != "accepted":
        raise HTTPException(status_code=400, detail=f"Cannot hire candidate with invitation in status {old_status}")
        
    inv.status = "hired"
    ev = InvitationStatusEvent(invitation_id=inv.id, from_status=old_status, to_status="hired", actor="employer")
    db.add(ev)
    db.commit()
    return {"status": inv.status}

async def accept_decline_invitation(
    invitation_id: uuid.UUID,
    action: str,
    current_user: dict = Depends(require_candidate),
    db: Session = Depends(get_db)
):
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
    inv = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    
    if not inv or not cand or inv.candidate_id != cand.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    old_status = inv.status
    if old_status not in ["sent", "viewed"]:
        raise HTTPException(status_code=400, detail=f"Cannot {action} invitation in status {old_status}")
        
    inv.status = "accepted" if action == "accept" else "declined"
    
    ev = InvitationStatusEvent(
        invitation_id=inv.id,
        from_status=old_status,
        to_status=inv.status,
        actor="candidate"
    )
    db.add(ev)
    
    # Dual opt-in reveal
    if action == "accept":
        reveal = ContactRevealLog(
            invitation_id=inv.id,
            candidate_id=cand.id,
            employer_id=inv.employer_id,
            trigger="invitation_accepted",
            candidate_data_revealed={"contacts": cand.phone, "fio": cand.full_name},
            employer_data_revealed={"company_name": inv.company_name, "contact_method": inv.contact_method}
        )
        db.add(reveal)
        
    db.commit()
    db.refresh(inv)
    return {"status": inv.status}

@router.get("/{invitation_id}/history")
async def get_invitation_history(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inv = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not inv: raise HTTPException(status_code=404, detail="Invitation not found")
        
    if current_user["role"] == "employer":
        employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
        if not employer or inv.employer_id != employer.id:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif current_user["role"] == "candidate":
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user["id"]).first()
        if not cand or inv.candidate_id != cand.id:
            raise HTTPException(status_code=403, detail="Forbidden")
            
    events = db.query(InvitationStatusEvent).filter(InvitationStatusEvent.invitation_id == invitation_id).order_by(InvitationStatusEvent.created_at.asc()).all()
    return [{"from_status": e.from_status, "to_status": e.to_status, "actor": e.actor, "created_at": e.created_at} for e in events]
