"""Centralized HR policy defaults for project sourcing incentives."""
from decimal import Decimal
from typing import Literal
from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, String, DateTime, Date, Text, Integer, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, current_user, db_session

router=APIRouter(prefix="/policies",tags=["Company Policies"])

class CompanyPolicy(Base):
    __tablename__="company_policies"
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    decimal_value:Mapped[Decimal]=mapped_column(Numeric(12,2))
    updated_by:Mapped[int | None]=mapped_column(nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

DEFAULT_BONUS_INR=Decimal("10000.00")
HR_ROLES={"super_admin","admin","hr"}

class BonusPolicyIn(BaseModel):
    default_project_bonus_inr:Decimal=Field(ge=0,le=100000000,decimal_places=2)

def policy_default(db:Session)->Decimal:
    row=db.get(CompanyPolicy,"default_project_bonus_inr")
    return Decimal(row.decimal_value) if row else DEFAULT_BONUS_INR

@router.get("/project-bonus")
def get_bonus_policy(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HR_ROLES:
        raise HTTPException(403,"Only HR may view company bonus policies")
    return {"default_project_bonus_inr":float(policy_default(db)),"currency":"INR",
            "milestone_days":30,"award_status":"planned"}

@router.put("/project-bonus")
def set_bonus_policy(body:BonusPolicyIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("super_admin","admin"):
        raise HTTPException(403,"Admin approval required; HR must submit a governance request")
    row=db.get(CompanyPolicy,"default_project_bonus_inr")
    if row is None:
        row=CompanyPolicy(key="default_project_bonus_inr",decimal_value=body.default_project_bonus_inr)
        db.add(row)
    row.decimal_value=body.default_project_bonus_inr
    row.updated_by=user.id
    row.updated_at=datetime.now(timezone.utc)
    db.commit()
    return get_bonus_policy(user,db)


class CompanyPolicyRecord(Base):
    __tablename__="company_policy_records"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    title:Mapped[str]=mapped_column(String(150))
    category:Mapped[str]=mapped_column(String(40))
    description:Mapped[str]=mapped_column(Text)
    effective_date:Mapped[date]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(default=True)
    created_by:Mapped[int]=mapped_column(Integer)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class PolicyRecordIn(BaseModel):
    title:str=Field(min_length=3,max_length=150)
    category:Literal["general","leave","attendance","payroll","security","onboarding"]
    description:str=Field(min_length=20,max_length=10000)
    effective_date:date
    active:bool=True

@router.get("/records")
def list_company_policies(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HR_ROLES:
        raise HTTPException(403,"HR access required")
    rows=db.scalars(select(CompanyPolicyRecord).order_by(CompanyPolicyRecord.id.desc())).all()
    return [{"id":r.id,"title":r.title,"category":r.category,"description":r.description,
             "effective_date":r.effective_date,"active":r.active,"created_at":r.created_at} for r in rows]

@router.post("/records",status_code=201)
def create_company_policy(body:PolicyRecordIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("super_admin","admin"):
        raise HTTPException(403,"Admin approval required; HR must submit a governance request")
    row=CompanyPolicyRecord(title=body.title.strip(),category=body.category,
                            description=body.description.strip(),effective_date=body.effective_date,
                            active=body.active,created_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"title":row.title,"category":row.category,
            "description":row.description,"effective_date":row.effective_date,"active":row.active}
