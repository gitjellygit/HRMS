"""Centralized HR policy defaults for project sourcing incentives."""
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, String, DateTime, select
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
    if user.role not in HR_ROLES:
        raise HTTPException(403,"Only HR may change bonus policies")
    row=db.get(CompanyPolicy,"default_project_bonus_inr")
    if row is None:
        row=CompanyPolicy(key="default_project_bonus_inr",decimal_value=body.default_project_bonus_inr)
        db.add(row)
    row.decimal_value=body.default_project_bonus_inr
    row.updated_by=user.id
    row.updated_at=datetime.now(timezone.utc)
    db.commit()
    return get_bonus_policy(user,db)
