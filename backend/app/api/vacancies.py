"""Vacancies router"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.security import require_employer
from app.models.models import Vacancy, EmployerProfile, Specialization, Grade
from app.schemas.schemas import VacancyCreate, VacancyUpdate, VacancyOut

router = APIRouter()


def resolve_spec_or_grade(db: Session, value: str, entity_type: str = "specialization") -> uuid.UUID:
    """Resolve code or UUID to entity UUID."""
    Model = Specialization if entity_type == "specialization" else Grade
    
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


@router.get("/", response_model=list[VacancyOut])
async def list_vacancies(
    mine: bool = True,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """List vacancies.
    
    For employers: defaults to their own vacancies (mine=true).
    Use ?mine=false for public board.
    For candidates/public: always shows all published vacancies.
    """
    from app.core.security import decode_token
    
    query = db.query(Vacancy)
    
    # Try to get current user from token (optional)
    current_user = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = decode_token(token)
            # Normalize payload to match expected format (id, role)
            current_user = {
                "id": payload.get("user_id") or payload.get("sub"),
                "role": payload.get("role")
            }
        except:
            pass
    
    # If authenticated as employer and mine=true (default), filter to their vacancies
    if current_user and current_user.get("role") == "employer" and mine:
        # Get employer profile to filter by employer_id
        from app.models.models import User, EmployerProfile
        user = db.query(User).filter(User.id == current_user["id"]).first()
        if user and user.employer_profile:
            query = query.filter(Vacancy.employer_id == user.employer_profile.id)
    
    return query.all()

@router.get("/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(vacancy_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get vacancy details"""
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy

@router.post("/", response_model=VacancyOut, status_code=201)
async def create_vacancy(
    vacancy_in: VacancyCreate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    """Create vacancy"""
    # Salary validation per brief requirement 2.1
    if vacancy_in.salary_min is None or vacancy_in.salary_max is None:
        raise HTTPException(status_code=422, detail="Вилка ЗП (salary_min и salary_max) обязательна для вакансии.")
    if vacancy_in.salary_min > vacancy_in.salary_max:
        raise HTTPException(status_code=422, detail="Минимальная зарплата не может быть больше максимальной.")
        
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer profile required")
    
    # Resolve codes to UUIDs
    spec_id = resolve_spec_or_grade(db, vacancy_in.specialization_id, "specialization")
    grade_min_id = resolve_spec_or_grade(db, vacancy_in.grade_min_id, "grade")
    grade_max_id = resolve_spec_or_grade(db, vacancy_in.grade_max_id, "grade")
        
    vacancy = Vacancy(
        title=vacancy_in.title,
        description=vacancy_in.description,
        specialization_id=spec_id,
        grade_min_id=grade_min_id,
        grade_max_id=grade_max_id,
        salary_min=vacancy_in.salary_min,
        salary_max=vacancy_in.salary_max,
        requirements=vacancy_in.requirements,
        status=vacancy_in.status,
        company_id=employer.company_id,
        employer_id=employer.id
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy

@router.put("/{vacancy_id}", response_model=VacancyOut)
async def update_vacancy(
    vacancy_id: uuid.UUID,
    vacancy_in: VacancyUpdate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    """Update vacancy"""
    # Validation if salaries are provided
    if vacancy_in.salary_min is not None and vacancy_in.salary_max is not None:
        if vacancy_in.salary_min > vacancy_in.salary_max:
            raise HTTPException(status_code=422, detail="Минимальная зарплата не может быть больше максимальной.")
            
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
        
    if not employer or vacancy.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Not your vacancy")
    
    # Resolve codes to UUIDs if provided
    for field in ['specialization_id', 'grade_min_id', 'grade_max_id']:
        value = getattr(vacancy_in, field, None)
        if value is not None:
            entity_type = "specialization" if field == "specialization_id" else "grade"
            resolved_uuid = resolve_spec_or_grade(db, value, entity_type)
            setattr(vacancy_in, field, resolved_uuid)
        
    for k, v in vacancy_in.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(vacancy, k, v)
        
    db.commit()
    db.refresh(vacancy)
    return vacancy
