"""Companies router"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.security import get_current_user, require_employer
from app.models.models import Company, EmployerProfile
from app.schemas.schemas import CompanyCreate, CompanyUpdate, CompanyOut

router = APIRouter()

@router.get("/", response_model=list[CompanyOut])
async def list_companies(db: Session = Depends(get_db)):
    """List companies"""
    companies = db.query(Company).limit(100).all()
    return companies

@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get company details"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.post("/", response_model=CompanyOut, status_code=201)
async def create_company(
    company_in: CompanyCreate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    """Create company (for employers)"""
    company = Company(**company_in.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    
    # Check if employer profile exists, if not create/update
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer:
        employer = EmployerProfile(
            user_id=current_user["id"],
            company_id=company.id,
            full_name=current_user.get("email", "Employer")
        )
        db.add(employer)
        db.commit()
        
    return company

@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: uuid.UUID,
    company_in: CompanyUpdate,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    if not employer or employer.company_id != company_id:
        raise HTTPException(status_code=403, detail="You can only edit your own company")
        
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    for k, v in company_in.model_dump(exclude_unset=True).items():
        setattr(company, k, v)
        
    db.commit()
    db.refresh(company)
    return company
