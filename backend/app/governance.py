"""Admin approvals for policy publication and manual leave entitlements."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .bonus_policy import CompanyPolicy, CompanyPolicyRecord, BonusPolicyIn, PolicyRecordIn
from .leave_management import LeavePolicy, PolicyIn, EntitlementIn
from .employee_core import LeaveEntitlement

router=APIRouter(prefix="/governance",tags=["Admin approval"])
ADMINS=("super_admin","admin")
HRS=ADMINS+("hr",)

class ChangeRequest(Base):
    __tablename__="governance_change_requests"
    id:Mapped[int]=mapped_column(primary_key=True)
    kind:Mapped[str]=mapped_column(String(40))
    payload:Mapped[str]=mapped_column(Text)
    reason:Mapped[str]=mapped_column(String(1000))
    status:Mapped[str]=mapped_column(String(20),default="pending")
    submitted_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    review_note:Mapped[str]=mapped_column(String(1000),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class Proposed(BaseModel):
    kind:str
    payload:dict
    reason:str=Field(min_length=10,max_length=1000)

class Decision(BaseModel):
    approve:bool
    reason:str=Field(min_length=10,max_length=1000)

SCHEMAS={"company_policy":PolicyRecordIn,"leave_policy":PolicyIn,
         "leave_allocation":EntitlementIn,"bonus_policy":BonusPolicyIn}

def submit(db,user,kind,payload,reason):
    if user.role not in HRS:raise HTTPException(403,"HR access required")
    if kind not in SCHEMAS:raise HTTPException(422,"Unsupported change category")
    if len(reason.strip())<10:raise HTTPException(422,"Reason must be at least ten characters")
    data=SCHEMAS[kind].model_validate(payload).model_dump(mode="json")
    row=ChangeRequest(kind=kind,payload=json.dumps(data),reason=reason.strip(),submitted_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":"pending","kind":row.kind,"admin_approval_required":True}

@router.post("/requests",status_code=201)
def propose(body:Proposed,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    return submit(db,user,body.kind,body.payload,body.reason)

@router.get("/requests")
def list_requests(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HRS:raise HTTPException(403,"HR access required")
    q=select(ChangeRequest).order_by(ChangeRequest.id.desc())
    if user.role not in ADMINS:q=q.where(ChangeRequest.submitted_by==user.id)
    return [{"id":x.id,"kind":x.kind,"payload":json.loads(x.payload),
             "reason":x.reason,"status":x.status,"submitted_by":x.submitted_by,
             "reviewed_by":x.reviewed_by,"review_note":x.review_note}
            for x in db.scalars(q.limit(500)).all()]

def apply(db,row):
    data=json.loads(row.payload)
    if row.kind=="company_policy":
        p=PolicyRecordIn.model_validate(data)
        db.add(CompanyPolicyRecord(title=p.title,category=p.category,description=p.description,
              effective_date=p.effective_date,active=p.active,created_by=row.submitted_by))
    elif row.kind=="bonus_policy":
        p=BonusPolicyIn.model_validate(data)
        x=db.get(CompanyPolicy,"default_project_bonus_inr")
        if not x:
            x=CompanyPolicy(key="default_project_bonus_inr",decimal_value=p.default_project_bonus_inr)
            db.add(x)
        x.decimal_value=p.default_project_bonus_inr;x.updated_by=row.reviewed_by
        x.updated_at=datetime.now(timezone.utc)
    elif row.kind=="leave_policy":
        p=PolicyIn.model_validate(data)
        x=db.scalar(select(LeavePolicy).where(LeavePolicy.leave_type==p.leave_type).with_for_update())
        if not x:x=LeavePolicy(leave_type=p.leave_type);db.add(x)
        for key,value in p.model_dump(exclude={"leave_type","approval_chain"}).items():setattr(x,key,value)
        x.approval_chain=",".join(p.approval_chain)
    elif row.kind=="leave_allocation":
        p=EntitlementIn.model_validate(data)
        user=db.get(Employee,p.employee_id)
        if not user or user.status!="active":raise HTTPException(422,"Employee is not active")
        kind=db.scalar(select(LeavePolicy.id).where(LeavePolicy.leave_type==p.leave_type,
                                                    LeavePolicy.active.is_(True)))
        if not kind:raise HTTPException(422,"Active leave type required")
        x=db.scalar(select(LeaveEntitlement).where(
            LeaveEntitlement.employee_id==p.employee_id,
            LeaveEntitlement.year==p.year,LeaveEntitlement.leave_type==p.leave_type).with_for_update())
        if x is None:
            x=LeaveEntitlement(employee_id=p.employee_id,year=p.year,leave_type=p.leave_type)
            db.add(x)
        x.allocated_days=p.allocated_days

@router.post("/requests/{request_id}/review")
def review(request_id:int,body:Decision,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ADMINS:raise HTTPException(403,"Admin approval required")
    x=db.scalar(select(ChangeRequest).where(ChangeRequest.id==request_id).with_for_update())
    if not x:raise HTTPException(404,"Request not found")
    if x.status!="pending":raise HTTPException(409,"Already reviewed")
    if x.submitted_by==user.id:raise HTTPException(403,"Self approval prohibited")
    x.reviewed_by=user.id;x.review_note=body.reason
    x.reviewed_at=datetime.now(timezone.utc)
    if body.approve:apply(db,x)
    x.status="approved" if body.approve else "rejected"
    db.commit()
    return {"id":x.id,"status":x.status,"reviewed_by":x.reviewed_by}
