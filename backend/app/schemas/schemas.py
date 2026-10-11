from pydantic import BaseModel, ConfigDict
from typing import Optional, List
import uuid

class CompanyBase(BaseModel):
    name: str
    legal_name: Optional[str] = None
    inn: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    pass

class CompanyOut(CompanyBase):
    id: uuid.UUID
    
    model_config = ConfigDict(from_attributes=True)

class VacancyBase(BaseModel):
    title: str
    description: str
    specialization_id: str  # Code ("backend") or UUID; API resolves
    grade_min_id: str  # Code ("junior") or UUID; API resolves
    grade_max_id: str  # Code ("senior") or UUID; API resolves
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    requirements: dict = {}
    status: Optional[str] = "draft"
    work_format: Optional[str] = None
    location: Optional[str] = None
    
    model_config = ConfigDict(extra='forbid')

class VacancyCreate(VacancyBase):
    pass

class VacancyUpdate(VacancyBase):
    pass

class VacancyOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    employer_id: uuid.UUID
    title: str
    description: str
    specialization_id: uuid.UUID  # Stored as UUID in DB
    grade_min_id: uuid.UUID  # Stored as UUID in DB
    grade_max_id: uuid.UUID  # Stored as UUID in DB
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    requirements: dict = {}
    status: Optional[str] = "draft"
    work_format: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ApplicationBase(BaseModel):
    vacancy_id: uuid.UUID
    cover_letter: Optional[str] = None

class ApplicationCreate(ApplicationBase):
    model_config = ConfigDict(extra='forbid')

class ApplicationUpdateStatus(BaseModel):
    status: str
    note: Optional[str] = None
    
    model_config = ConfigDict(extra='forbid')

class ApplicationOutCandidate(ApplicationBase):
    id: uuid.UUID
    status: str
    
    model_config = ConfigDict(from_attributes=True)

class ApplicationOutEmployer(ApplicationBase):
    id: uuid.UUID
    candidate_id: uuid.UUID
    status: str
    candidate_data: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)
