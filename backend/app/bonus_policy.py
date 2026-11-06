"""Centralized HR policy defaults for project sourcing incentives."""
from decimal import Decimal
import secrets
import json
from typing import Literal
from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, String, DateTime, Date, Text, Integer, ForeignKey, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, current_user, db_session, UPLOAD_DIR
from fastapi.responses import FileResponse

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
    audience_ids:Mapped[str]=mapped_column(Text,default="[]",server_default="[]")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class PolicyAttachment(Base):
    __tablename__="company_policy_attachments"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    policy_id:Mapped[int]=mapped_column(ForeignKey("company_policy_records.id"),index=True)
    filename:Mapped[str]=mapped_column(String(180))
    storage_key:Mapped[str]=mapped_column(String(110))
    uploaded_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class PolicyRecordIn(BaseModel):
    title:str=Field(min_length=3,max_length=150)
    category:Literal["general","leave","attendance","payroll","security","onboarding"]
    description:str=Field(min_length=20,max_length=10000)
    effective_date:date
    active:bool=True
    audience_ids:list[int]=Field(default_factory=list,max_length=1000)


def visible_policy(row:CompanyPolicyRecord,user:Employee)->bool:
    if user.role in HR_ROLES:return True
    if not row.active:return False
    targets=json.loads(row.audience_ids or "[]")
    return not targets or user.id in targets

def record_json(db:Session,row:CompanyPolicyRecord):
    attachments=db.scalars(select(PolicyAttachment).where(PolicyAttachment.policy_id==row.id)).all()
    return {"id":row.id,"title":row.title,"category":row.category,
            "description":row.description,"effective_date":row.effective_date,"active":row.active,
            "audience_ids":json.loads(row.audience_ids or "[]"),
            "attachments":[{"id":a.id,"name":a.filename} for a in attachments]}

@router.get("/records")
def list_company_policies(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(CompanyPolicyRecord).order_by(CompanyPolicyRecord.id.desc())).all()
    return [record_json(db,r) for r in rows if visible_policy(r,user)]

@router.post("/records",status_code=201)
def create_company_policy(body:PolicyRecordIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("super_admin","admin"):
        raise HTTPException(403,"Admin approval required; HR must submit a governance request")
    if body.audience_ids:
        ids=set(db.scalars(select(Employee.id).where(
            Employee.id.in_(body.audience_ids),Employee.status=="active")).all())
        if ids!=set(body.audience_ids):raise HTTPException(422,"Select active employees for policy visibility")
    row=CompanyPolicyRecord(title=body.title.strip(),category=body.category,
                            description=body.description.strip(),effective_date=body.effective_date,
                            active=body.active,audience_ids=json.dumps(body.audience_ids),created_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return record_json(db,row)

@router.post("/records/{policy_id}/attachments",status_code=201)
async def upload_policy_document(policy_id:int,document:UploadFile=File(...),
                                 user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in HR_ROLES:raise HTTPException(403,"Only HR may attach policy documents")
    row=db.get(CompanyPolicyRecord,policy_id)
    if not row:raise HTTPException(404,"Publish the policy before attaching a document")
    payload=await document.read(5*1024*1024+1)
    if len(payload)>5*1024*1024:raise HTTPException(413,"Policy document must be under 5 MB")
    if not payload.startswith(b"%PDF-") or not (document.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422,"Choose a valid PDF policy document")
    UPLOAD_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    key="policy-"+secrets.token_hex(20)+".pdf"
    with (UPLOAD_DIR/key).open("xb") as file:file.write(payload)
    attachment=PolicyAttachment(policy_id=policy_id,filename=(document.filename or "policy.pdf")[:180],
                                storage_key=key,uploaded_by=user.id)
    db.add(attachment);db.commit();db.refresh(attachment)
    return {"id":attachment.id,"name":attachment.filename}

@router.get("/records/{policy_id}/attachments/{attachment_id}")
def get_policy_document(policy_id:int,attachment_id:int,user:Employee=Depends(current_user),
                        db:Session=Depends(db_session)):
    row=db.get(CompanyPolicyRecord,policy_id)
    if not row or not visible_policy(row,user):raise HTTPException(404,"Policy document not found")
    attachment=db.get(PolicyAttachment,attachment_id)
    if not attachment or attachment.policy_id!=policy_id:raise HTTPException(404,"Policy document not found")
    path=UPLOAD_DIR/attachment.storage_key
    if not path.is_file():raise HTTPException(404,"The document file is missing from storage")
    return FileResponse(path,media_type="application/pdf",filename=attachment.filename,
                        headers={"Cache-Control":"private, no-store"})
