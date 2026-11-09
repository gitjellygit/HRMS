"""HR-defined monthly salary earnings and deductions with payslip snapshots."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, db_session, current_user

router=APIRouter(prefix="/payroll",tags=["Salary Components"])
HR=("hr","admin","super_admin")

class SalaryComponent(Base):
    __tablename__="pay_salary_components"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    code:Mapped[str]=mapped_column(String(35),primary_key=True)
    title:Mapped[str]=mapped_column(String(100))
    kind:Mapped[str]=mapped_column(String(15))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    effective_from:Mapped[date]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    updated_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class SalaryComponentVersion(Base):
    """Retains every approved component revision with its effective date."""
    __tablename__="pay_salary_component_versions"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    code:Mapped[str]=mapped_column(String(35),index=True)
    title:Mapped[str]=mapped_column(String(100))
    kind:Mapped[str]=mapped_column(String(15))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    effective_from:Mapped[date]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(Boolean)
    changed_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    changed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),
        default=lambda:datetime.now(timezone.utc))


class PayslipComponent(Base):
    __tablename__="pay_slip_component_snapshots"
    line_id:Mapped[int]=mapped_column(ForeignKey("pay_run_lines.id"),primary_key=True)
    code:Mapped[str]=mapped_column(String(35),primary_key=True)
    title:Mapped[str]=mapped_column(String(100))
    kind:Mapped[str]=mapped_column(String(15))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))

class ComponentIn(BaseModel):
    employee_id:int=Field(gt=0)
    code:str=Field(pattern=r"^[a-z][a-z0-9_]{1,34}$")
    title:str=Field(min_length=2,max_length=100)
    kind:Literal["earning","deduction"]
    amount:Decimal=Field(ge=0,le=100000000,decimal_places=2)
    effective_from:date
    active:bool=True

def view(row:SalaryComponent):
    return {"employee_id":row.employee_id,"code":row.code,"title":row.title,
            "kind":row.kind,"amount":row.amount,
            "effective_from":row.effective_from,"active":row.active}

def effective_components(db:Session,employee_id:int,as_of:date):
    """Resolve the most recent approved version *effective by this date*."""
    versions=db.scalars(select(SalaryComponentVersion).where(
        SalaryComponentVersion.employee_id==employee_id,
        SalaryComponentVersion.effective_from<=as_of).order_by(
        SalaryComponentVersion.effective_from.desc(),
        SalaryComponentVersion.id.desc())).all()
    chosen={}
    for version in versions:
        chosen.setdefault(version.code,version)
    # Legacy records are valid only if no version exists for that code;
    # a newer future-dated edit must not replace a historic version.
    legacy=db.scalars(select(SalaryComponent).where(
        SalaryComponent.employee_id==employee_id,SalaryComponent.effective_from<=as_of)).all()
    for row in legacy:
        if row.code not in chosen and not db.scalar(select(SalaryComponentVersion.id).where(
                SalaryComponentVersion.employee_id==employee_id,
                SalaryComponentVersion.code==row.code).limit(1)):
            chosen[row.code]=row
    return [x for x in sorted(chosen.values(),key=lambda v:v.code) if x.active]

@router.get("/components")
def components(employee_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HR and user.id!=employee_id:raise HTTPException(403,"Only HR or the employee can view these salary components")
    return [view(x) for x in db.scalars(select(SalaryComponent).where(
        SalaryComponent.employee_id==employee_id).order_by(SalaryComponent.code)).all()]

def apply_component(db:Session,body:ComponentIn,reviewer_id:int):
    person=db.get(Employee,body.employee_id)
    if not person or person.status!="active":raise HTTPException(422,"Active employee required")
    row=db.get(SalaryComponent,(body.employee_id,body.code))
    if row is not None and not db.scalar(select(SalaryComponentVersion.id).where(
            SalaryComponentVersion.employee_id==body.employee_id,
            SalaryComponentVersion.code==body.code).limit(1)):
        db.add(SalaryComponentVersion(employee_id=row.employee_id,code=row.code,title=row.title,
            kind=row.kind,amount=row.amount,effective_from=row.effective_from,
            active=row.active,changed_by=row.updated_by))
    if row is None:
        row=SalaryComponent(employee_id=body.employee_id,code=body.code,updated_by=reviewer_id)
        db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    row.updated_by=reviewer_id
    db.add(SalaryComponentVersion(**body.model_dump(),changed_by=reviewer_id))
    return view(row)


@router.put("/components")
def save_component(body:ComponentIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    raise HTTPException(403,detail={"field":"approval","message":
        "Salary components require independent approval. Submit a salary_component request through /governance/requests."})
