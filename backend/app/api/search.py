from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.security import require_employer, get_current_user
from app.models.models import CandidateProfile, CategoryAssignment, Grade, CandidateSkill, Skill, Specialization, FspIdentity

router = APIRouter()

from sqlalchemy.orm import selectinload

@router.get("/")
async def search_candidates(
    specialization_id: str = None,
    grade_min: str = None,
    grade_max: str = None,
    skills: str = None,
    q: str = None,
    has_fsp: bool = None,
    sort_by: str = "relevance", # or "power"
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    query = db.query(CandidateProfile).options(
        selectinload(CandidateProfile.category_assignment),
        selectinload(CandidateProfile.fsp_identity),
        selectinload(CandidateProfile.skills)
    ).join(CategoryAssignment)
    
    if specialization_id:
        import uuid
        try:
            val = uuid.UUID(specialization_id)
            query = query.filter(CategoryAssignment.specialization_id == val)
        except ValueError:
            # It's a code
            spec = db.query(Specialization).filter(Specialization.code == specialization_id).first()
            if not spec:
                valid = [s.code for s in db.query(Specialization).all()]
                raise HTTPException(status_code=422, detail=f"Specialization not found. Valid codes: {valid}")
            query = query.filter(CategoryAssignment.specialization_id == spec.id)
            
    candidates = query.all()
    results = []
    
    from app.services.invitations import serialize_candidate_for_employer
    
    # Backward-compatible alias: never silently ignore legacy q.
    if q and not skills:
        skills = q
    skill_list = [s.strip().lower() for s in skills.split(',')] if skills else []
    
    # Pre-fetch all grades, skills, specializations to avoid N+1 inside loop
    all_grades = {g.id: g.level for g in db.query(Grade).all()}
    all_skills = {s.id: s.normalized_name for s in db.query(Skill).all()}
    all_specs = {s.id: s.name for s in db.query(Specialization).all()}
    
    for cand in candidates:
        cat_assign = cand.category_assignment
        if not cat_assign: continue
        
        c_level = all_grades.get(cat_assign.grade_id, 0)
        
        if grade_min and c_level < int(grade_min): continue
        if grade_max and c_level > int(grade_max): continue
        
        fsp_rec = cand.fsp_identity
        if has_fsp and (not fsp_rec or not fsp_rec.verified):
            continue
            
        c_skills = []
        for cs in cand.skills:
            s_name = all_skills.get(cs.skill_id)
            if s_name:
                c_skills.append(s_name)
                
        if skill_list:
            if not any(s in c_skills for s in skill_list):
                continue
        
        relevance = len(set(skill_list) & set(c_skills)) if skill_list else 1
        power = (c_level * 10) + (1 if cat_assign.is_confirmed else 0) + (getattr(fsp_rec, 'fsp_index', 0.0) if fsp_rec else 0.0)
        
        spec_name = all_specs.get(cat_assign.specialization_id, "Unknown")
        
        cand_data = {
            "id": cand.id,
            "specialization": spec_name,
            "grade": c_level,
            "skills": c_skills,
            "is_confirmed": cat_assign.is_confirmed,
            "fsp_index": getattr(fsp_rec, 'fsp_index', 0.0) if fsp_rec else 0.0,
            "relevance": relevance,
            "power": power,
            "team_role": cand.team_role,
            "work_format": cand.work_format,
            "years_of_experience": cand.years_of_experience
        }
        
        results.append(cand_data)
        
    if sort_by == "power":
        results.sort(key=lambda x: x["power"], reverse=True)
    else:
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
    return [serialize_candidate_for_employer(cand, "sent") for cand in results[:50]]
