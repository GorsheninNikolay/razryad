from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.security import require_employer, get_current_user
from app.models.models import Need, EmployerProfile, Specialization, Grade
from app.schemas.needs import NeedCreate, NeedUpdate, NeedOut
from app.services.matching import parse_need_text

router = APIRouter()


def resolve_specialization_or_grade(db: Session, value: str, entity_type: str = "specialization") -> uuid.UUID:
    """Resolve code or UUID to entity UUID.
    
    entity_type: "specialization" or "grade"
    """
    Model = Specialization if entity_type == "specialization" else Grade
    field_name = "specialization_id" if entity_type == "specialization" else "grade_id"
    
    # Try as code first
    obj = db.query(Model).filter(Model.code == value).first()
    if obj:
        return obj.id
    
    # Try as UUID
    try:
        candidate_uuid = uuid.UUID(str(value))
        obj = db.get(Model, candidate_uuid)
        if obj:
            return obj.id
    except (ValueError, AttributeError, TypeError):
        pass
    
    # Not found
    valid = ', '.join(o.code for o in db.query(Model).order_by(Model.code).all())
    entity_label = "Специализация" if entity_type == "specialization" else "Грейд"
    raise HTTPException(
        status_code=422,
        detail=f'{entity_label} не найдена; допустимые значения: {valid}'
    )


@router.post("/", response_model=NeedOut, status_code=201)
async def create_need(
    need_in: NeedCreate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer profile required")
    
    # Resolve codes to UUIDs
    spec_id = resolve_specialization_or_grade(db, need_in.specialization_id, "specialization")
    grade_min_id = resolve_specialization_or_grade(db, need_in.grade_min_id, "grade")
    grade_max_id = resolve_specialization_or_grade(db, need_in.grade_max_id, "grade")
    
    parsed = parse_need_text(need_in.description)
    
    # Build parsed_data with ONLY actual extracted values - no fake confidence
    # parse_need_text currently only extracts must_have_skills from text
    parsed_data = {
        "source": {
            # User-provided (confirmed) fields
            "specialization": str(spec_id) if spec_id else None,
            "grade_range": {
                "min": str(grade_min_id) if grade_min_id else None,
                "max": str(grade_max_id) if grade_max_id else None
            },
            # Extracted from text (if any)
            "must_have_skills": parsed.get("must_have_skills", []),
            "nice_to_have_skills": parsed.get("nice_to_have_skills", []),
            # These are NOT extracted by parse_need_text, so return None or omit
            "role": None,
            "work_format": None,
            "domain": None
        },
        # Explicitly state which fields were extracted from text
        # This helps frontend understand what was recognized vs what was not
        "parsed_fields": ["must_have_skills"] if parsed.get("must_have_skills") else [],
        # Skills extracted from text, also visible separately for clarity
        "extracted_skills": parsed.get("must_have_skills", [])
    }
    
    # Override skills if parser found any
    if parsed.get("must_have_skills"):
        # Just simple append for demo
        combined_skills = list(set(need_in.must_have_skills + parsed.get("must_have_skills", [])))
        need_in.must_have_skills = combined_skills

    need = Need(
        title=need_in.title,
        description=need_in.description,
        specialization_id=spec_id,
        grade_min_id=grade_min_id,
        grade_max_id=grade_max_id,
        must_have_skills=need_in.must_have_skills,
        nice_to_have_skills=need_in.nice_to_have_skills,
        salary_min=need_in.salary_min,
        salary_max=need_in.salary_max,
        work_format=need_in.work_format,
        location=need_in.location,
        employer_id=employer.id
    )
    
    db.add(need)
    db.commit()
    db.refresh(need)
    
    out = NeedOut.model_validate(need)
    out.parsed_data = parsed_data
    return out

@router.get("/", response_model=list[NeedOut])
async def list_needs(
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        return []
    return db.query(Need).filter(Need.employer_id == employer.id).all()

@router.get("/{need_id}", response_model=NeedOut)
async def get_need(
    need_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")
    return need

@router.patch("/{need_id}", response_model=NeedOut)
async def update_need(
    need_id: uuid.UUID,
    need_in: NeedUpdate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")
    
    # Resolve codes to UUIDs if provided
    for field in ['specialization_id', 'grade_min_id', 'grade_max_id']:
        value = getattr(need_in, field, None)
        if value is not None:
            entity_type = "specialization" if field == "specialization_id" else "grade"
            resolved_uuid = resolve_specialization_or_grade(db, value, entity_type)
            setattr(need_in, field, resolved_uuid)
    
    for k, v in need_in.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(need, k, v)
        
    db.commit()
    db.refresh(need)
    return need

@router.get("/{need_id}/categories")
async def get_need_categories(
    need_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")
        
    return [{"id": str(need.specialization_id), "name": "Category 1"}] # dummy
