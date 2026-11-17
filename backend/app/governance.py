"""Admin approvals for policy publication and manual leave entitlements."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .bonus_policy import CompanyPolicy, CompanyPolicyRecord, BonusPolicyIn, PolicyRecordIn
from .leave_management import LeavePolicy, PolicyIn, EntitlementIn, apply_leave_policy
from .employee_core import LeaveEntitlement
from .payroll import SalaryIn, StatutoryIn, apply_salary_structure, apply_statutory_settings
from .payroll_components import ComponentIn, apply_component

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
         "leave_allocation":EntitlementIn,"bonus_policy":BonusPolicyIn,
         "salary_structure":SalaryIn,"statutory_settings":StatutoryIn,
         "salary_component":ComponentIn}
PAYROLL_KINDS=("salary_structure","statutory_settings","salary_component")

def submit(db,user,kind,payload,reason):
    if user.role not in HRS:raise HTTPException(403,"HR access required")
    if kind not in SCHEMAS:raise HTTPException(422,"Unsupported change category")
    if len(reason.strip())<10:raise HTTPException(422,"Reason must be at least ten characters")
    data=SCHEMAS[kind].model_validate(payload).model_dump(mode="json")
    if kind in PAYROLL_KINDS:
        employee=db.get(Employee,data["employee_id"])
        if not employee:raise HTTPException(422,detail={"field":"employee_id","message":"Employee not found"})
        if employee.id==user.id:raise HTTPException(403,"You cannot propose changes to your own compensation.")
        if employee.role=="super_admin" and user.role!="super_admin":
            raise HTTPException(403,"Only Super Admin can propose another Super Admin's compensation.")
        if kind=="salary_structure":
            pay=SalaryIn.model_validate(data)
            if pay.other_deductions>pay.basic+pay.hra+pay.allowances:
                raise HTTPException(422,detail={"field":"other_deductions","message":"Deductions exceed gross pay."})
    # Reject duplicate pending proposals by the same requester, without deleting
    # any previously submitted or completed audit history.
    comparable=json.dumps(data,sort_keys=True,separators=(",",":"))
    pending=db.scalars(select(ChangeRequest).where(
        ChangeRequest.kind==kind,ChangeRequest.submitted_by==user.id,
        ChangeRequest.status=="pending")).all()
    for existing in pending:
        if json.dumps(json.loads(existing.payload),sort_keys=True,separators=(",",":"))==comparable:
            raise HTTPException(409,detail={"field":"request","message":
                f"An identical {kind.replace('_',' ')} request is already awaiting approval (#{existing.id}). Open Admin approvals to review it."})
    row=ChangeRequest(kind=kind,payload=json.dumps(data),reason=reason.strip(),submitted_by=user.id)
    db.add(row);db.flush()
    from .notification_center import add_inbox
    admins=db.scalars(select(Employee.id).where(Employee.role.in_(ADMINS),Employee.status=="active",
                                Employee.id!=user.id)).all()
    for admin_id in admins:
        add_inbox(db,admin_id,"approval",f"Approval needed: {kind.replace('_',' ')}",
                  f"{user.name} requested approval for {kind.replace('_',' ')}. Open Admin approvals to review.","governance")
    db.commit();db.refresh(row)
    return {"id":row.id,"status":"pending","kind":row.kind,"admin_approval_required":True}

@router.post("/requests",status_code=201)
def propose(body:Proposed,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    return submit(db,user,body.kind,body.payload,body.reason)

@router.get("/requests")
def list_requests(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HRS:raise HTTPException(403,"HR access required")
    q=select(ChangeRequest).order_by(ChangeRequest.id.desc())
    if user.role not in ADMINS:q=q.where(ChangeRequest.submitted_by==user.id)
    rows=db.scalars(q.limit(500)).all()
    people_ids={n for row in rows for n in (row.submitted_by,row.reviewed_by) if n is not None}
    people={p.id:p.name for p in db.scalars(select(Employee).where(Employee.id.in_(people_ids))).all()} if people_ids else {}
    return [{"id":x.id,"kind":x.kind,"payload":json.loads(x.payload),
             "reason":x.reason,"status":x.status,"submitted_by":x.submitted_by,
             "submitted_by_name":people.get(x.submitted_by,"Former employee"),
             "reviewed_by":x.reviewed_by,
             "reviewed_by_name":people.get(x.reviewed_by,"Former employee") if x.reviewed_by else None,
             "review_note":x.review_note,"created_at":x.created_at,"reviewed_at":x.reviewed_at}
            for x in rows]

def apply(db,row):
    data=json.loads(row.payload)
    if row.kind=="company_policy":
        p=PolicyRecordIn.model_validate(data)
        published=CompanyPolicyRecord(title=p.title,category=p.category,description=p.description,
              effective_date=p.effective_date,active=p.active,audience_ids=json.dumps(p.audience_ids),created_by=row.submitted_by)
        db.add(published)
        if p.active:
            from .notification_center import add_inbox
            recipients=p.audience_ids or list(db.scalars(select(Employee.id).where(Employee.status=="active")).all())
            for recipient_id in recipients:
                add_inbox(db,recipient_id,"policy",f"New company policy: {p.title}",
                          f"A new {p.category} policy is available in the Policy Hub. Effective {p.effective_date}.","policies")
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
        apply_leave_policy(db,p,row.reviewed_by,reason=row.reason if hasattr(row,"reason") else "")
    elif row.kind in PAYROLL_KINDS:
        target_id=data["employee_id"]
        if target_id==row.reviewed_by:
            raise HTTPException(403,"You cannot approve changes to your own compensation.")
        if row.kind=="salary_structure":
            apply_salary_structure(db,SalaryIn.model_validate(data),row.reviewed_by)
        elif row.kind=="statutory_settings":
            apply_statutory_settings(db,StatutoryIn.model_validate(data),row.reviewed_by)
        else:
            apply_component(db,ComponentIn.model_validate(data),row.reviewed_by)
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
    if x.kind in PAYROLL_KINDS:
        target=db.get(Employee,json.loads(x.payload)["employee_id"])
        if not target:raise HTTPException(422,"Employee not found")
        if target.id==user.id:raise HTTPException(403,"Cannot approve your own compensation.")
        if target.role=="super_admin" and user.role!="super_admin":
            raise HTTPException(403,"Only another Super Admin can approve that change.")
    x.reviewed_by=user.id;x.review_note=body.reason
    x.reviewed_at=datetime.now(timezone.utc)
    if body.approve:apply(db,x)
    x.status="approved" if body.approve else "rejected"
    from .notification_center import add_inbox
    add_inbox(db,x.submitted_by,"approval",
              f"Your {x.kind.replace('_',' ')} request was {x.status}",
              f"{user.name} {x.status} your admin approval request. Open Admin approvals to review the result.","governance")
    db.commit()
    return {"id":x.id,"status":x.status,"reviewed_by":x.reviewed_by}
