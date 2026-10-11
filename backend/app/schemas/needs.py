from pydantic import field_validator, model_validator
from pydantic import model_validator
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
import uuid
import datetime

class NeedCreate(BaseModel):
    title: str
    description: str
    specialization_id: str  # Code ("backend") or UUID; API resolves
    grade_min_id: str  # Code ("junior") or UUID; API resolves
    grade_max_id: str  # Code ("senior") or UUID; API resolves
    must_have_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    salary_min: int
    salary_max: int
    work_format: Optional[str] = None
    location: Optional[str] = None
    
    model_config = ConfigDict(extra='forbid')

class NeedUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    specialization_id: Optional[str] = None  # Code or UUID
    grade_min_id: Optional[str] = None  # Code or UUID
    grade_max_id: Optional[str] = None  # Code or UUID
    must_have_skills: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    
    model_config = ConfigDict(extra='forbid')

class NeedOut(BaseModel):
    id: uuid.UUID
    employer_id: uuid.UUID
    title: str
    description: str
    specialization_id: uuid.UUID  # Stored as UUID in DB
    grade_min_id: uuid.UUID  # Stored as UUID in DB
    grade_max_id: uuid.UUID  # Stored as UUID in DB
    must_have_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    salary_min: int
    salary_max: int
    work_format: Optional[str] = None
    location: Optional[str] = None
    parsed_data: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class InvitationCreate(BaseModel):
    candidate_id: uuid.UUID
    
    @field_validator('salary_min')
    @classmethod
    def check_salary_min(cls, v):
        if v <= 0: raise ValueError("Минимальная зарплата должна быть больше нуля")
        return v
        
    @model_validator(mode='after')
    def validate_salaries(self):
        if self.salary_min and self.salary_max and self.salary_min > self.salary_max:
            raise ValueError("Минимальная зарплата не может быть больше максимальной")
        return self




    need_id: Optional[uuid.UUID] = None
    need_id: Optional[uuid.UUID] = None
    vacancy_id: Optional[uuid.UUID] = None
    subject: str
    message: str
    salary_min: int
    salary_max: int
    company_name: str
    contact_person: str
    contact_method: str
    expires_at: Optional[datetime.datetime] = None

    

class InvitationOut(InvitationCreate):
    id: uuid.UUID
    employer_id: uuid.UUID
    status: str
    created_at: datetime.datetime
    
    # Reveal fields
    candidate_fio: Optional[str] = None
    candidate_contacts: Optional[dict] = None
    candidate_workplace: Optional[dict] = None
    candidate_pseudonym: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class InvitationStatusUpdate(BaseModel):
    status: str

class ShortlistRevisionOut(BaseModel):
    id: uuid.UUID
    revision: int
    filters: dict
    ranking_params: dict
    candidate_count: int
    created_at: datetime.datetime
    
    model_config = ConfigDict(from_attributes=True)
