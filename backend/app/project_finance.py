"""Accountant project billing: draft invoicing, schedule controls and immutable period boundaries.

Invoice generation never sends an email or transfers money. Finance reviews drafts
before recording a sent or paid state. PostgreSQL uniquely guards schedule windows.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import io
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, Project, current_user, db_session
from .project_management import ProjectDetail, serialize

router=APIRouter(prefix="/finance",tags=["Project Finance & Invoices"])
HR=("super_admin","admin","hr")
FINANCE=HR+("accountant",)
def now():return datetime.now(timezone.utc)

class ProjectBilling(Base):
    __tablename__="finance_project_billing"
    project_id:Mapped[int]=mapped_column(ForeignKey("projects.id"),primary_key=True)
    recipient_type:Mapped[str]=mapped_column(String(24),default="client")
    recipient_name:Mapped[str]=mapped_column(String(180),default="")
    recipient_email:Mapped[str]=mapped_column(String(255),default="")
    recipient_phone:Mapped[str]=mapped_column(String(40),default="")
    billing_address:Mapped[str]=mapped_column(Text,default="")
    billing_day:Mapped[int|None]=mapped_column(Integer,nullable=True)
    payment_terms_days:Mapped[int]=mapped_column(Integer,default=15)
    billing_frequency:Mapped[str]=mapped_column(String(20),default="monthly",server_default="monthly")
    end_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    stopped_at:Mapped[date|None]=mapped_column(Date,nullable=True)
    updated_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class ProjectCharge(Base):
    """Recipient-specific invoice pricing, independent of the placement rate."""
    __tablename__="finance_project_charges"
    project_id:Mapped[int]=mapped_column(ForeignKey("projects.id"),primary_key=True)
    recipient_type:Mapped[str]=mapped_column(String(24),primary_key=True)
    pricing_mode:Mapped[str]=mapped_column(String(20),default="fixed_rate")
    rate_unit:Mapped[str]=mapped_column(String(20),default="hour",server_default="hour")
    pricing_value:Mapped[Decimal]=mapped_column(Numeric(14,2))
    tax_rate_pct:Mapped[Decimal]=mapped_column(Numeric(6,2),default=Decimal("0"))
    updated_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))


class ChargeIn(BaseModel):
    recipient_type:Literal["client","vendor","candidate"]
    pricing_mode:Literal["fixed_rate","percentage"]
    rate_unit:Literal["hour","day","week","month","project"]="hour"
    pricing_value:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    tax_rate_pct:Decimal=Field(default=0,ge=0,le=100,decimal_places=2)

    @model_validator(mode="after")
    def ensure_percentage(self):
        if self.pricing_mode=="percentage" and self.pricing_value>100:
            raise ValueError("Percentage of placement rate cannot exceed 100.")
        return self


def charge_view(row:ProjectCharge):
    return {"project_id":row.project_id,"recipient_type":row.recipient_type,
            "pricing_mode":row.pricing_mode,"rate_unit":row.rate_unit,"pricing_value":row.pricing_value,
            "tax_rate_pct":row.tax_rate_pct}

def charge_rate(db:Session,project_id:int,recipient_type:str,placement_rate:Decimal)->Decimal:
    row=db.get(ProjectCharge,(project_id,recipient_type))
    if row is None:return placement_rate
    if row.pricing_mode=="percentage":
        return (placement_rate*row.pricing_value/Decimal(100)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    return Decimal(row.pricing_value)


class ClientInvoice(Base):
    __tablename__="finance_invoices"
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey("projects.id"),index=True)
    recipient_type:Mapped[str]=mapped_column(String(24))
    recipient_name:Mapped[str]=mapped_column(String(180))
    recipient_email:Mapped[str]=mapped_column(String(255),default="")
    recipient_phone:Mapped[str]=mapped_column(String(40),default="")
    billing_address:Mapped[str]=mapped_column(Text,default="")
    period_start:Mapped[date]=mapped_column(Date)
    period_end:Mapped[date]=mapped_column(Date)
    issue_date:Mapped[date]=mapped_column(Date)
    due_date:Mapped[date]=mapped_column(Date)
    quantity:Mapped[Decimal]=mapped_column(Numeric(12,2))
    unit_rate:Mapped[Decimal]=mapped_column(Numeric(14,2))
    subtotal:Mapped[Decimal]=mapped_column(Numeric(14,2))
    tax_rate_pct:Mapped[Decimal]=mapped_column(Numeric(6,2))
    tax_amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    total:Mapped[Decimal]=mapped_column(Numeric(14,2))
    currency:Mapped[str]=mapped_column(String(3))
    status:Mapped[str]=mapped_column(String(20),default="draft")
    source:Mapped[str]=mapped_column(String(20),default="manual")
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    paid_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    reference:Mapped[str]=mapped_column(String(120),default="")
    __table_args__=(UniqueConstraint("project_id","period_start","period_end","recipient_type",
                                     name="uq_finance_project_invoice_window"),)

class FinanceAudit(Base):
    __tablename__="finance_audit"
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey("projects.id"),index=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    event:Mapped[str]=mapped_column(String(60))
    note:Mapped[str]=mapped_column(Text,default="")
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class BillingIn(BaseModel):
    recipient_type:Literal["client","vendor","candidate"]
    recipient_name:str=Field(min_length=2,max_length=180)
    recipient_email:EmailStr|None=None
    recipient_phone:str=Field(default="",max_length=40)
    billing_address:str=Field(default="",max_length=2000)
    billing_day:int|None=Field(default=None,ge=1,le=28)
    payment_terms_days:int=Field(default=15,ge=0,le=180)
    billing_frequency:Literal["weekly","biweekly","monthly"]="monthly"
    end_date:date|None=None

class ProjectStateIn(BaseModel):
    active:bool
    reason:str=Field(min_length=10,max_length=500)
    end_date:date|None=None

class InvoiceIn(BaseModel):
    project_id:int
    period_start:date
    period_end:date
    quantity:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    tax_rate_pct:Decimal|None=Field(default=None,ge=0,le=100,decimal_places=2)
    issue_date:date=Field(default_factory=date.today)
    @model_validator(mode="after")
    def validate_window(self):
        if self.period_end<self.period_start:raise ValueError("Invoice period end precedes start.")
        if self.issue_date>date.today():raise ValueError("Cannot issue invoices in the future.")
        return self

class ScheduleIn(BaseModel):
    as_of:date=Field(default_factory=date.today)
    project_id:int|None=None

class InvoiceStatusIn(BaseModel):
    status:Literal["sent","paid","void"]
    reference:str=Field(default="",max_length=120)

def authorized(user:Employee):
    if user.role not in FINANCE:raise HTTPException(403,"Finance/HR permission required")
def hr_only(user:Employee):
    if user.role not in HR:raise HTTPException(403,"Only HR can change project status")
def project_detail(db:Session,project_id:int):
    p=db.get(Project,project_id);d=db.get(ProjectDetail,project_id)
    if not p or not d:raise HTTPException(404,"Billable project not found")
    return p,d
def live_period(p:Project,d:ProjectDetail,profile:ProjectBilling|None,start:date,end:date,as_of:date):
    if p.status!="active" or (profile and profile.stopped_at is not None):
        raise HTTPException(409,"Inactive projects cannot generate invoices")
    if not d.start_date:raise HTTPException(422,"Project start date required")
    if start<d.start_date:raise HTTPException(422,"Invoice starts before project start")
    if end<start:raise HTTPException(422,"Invalid period")
    if as_of>date.today():raise HTTPException(422,"Future service periods are not billable")
    if end>as_of:raise HTTPException(422,"Cannot invoice future service dates")
    if profile and profile.end_date and end>profile.end_date:
        raise HTTPException(409,"Invoice period exceeds project end date")
def invoice_view(x:ClientInvoice,as_of:date|None=None):
    as_of=as_of or date.today()
    state="overdue" if x.status=="sent" and x.due_date<as_of else x.status
    return {k:getattr(x,k) for k in ("id","project_id","recipient_type","recipient_name",
      "recipient_email","recipient_phone","billing_address","period_start","period_end",
      "issue_date","due_date","quantity","unit_rate","subtotal","tax_rate_pct","tax_amount",
      "total","currency","source","reference")} | {"status":state,"stored_status":x.status}
def billing_view(p:Project,d:ProjectDetail,profile:ProjectBilling|None):
    data=serialize(p,d)
    data["billing"]=({"recipient_type":profile.recipient_type,"recipient_name":profile.recipient_name,
       "recipient_email":profile.recipient_email,"recipient_phone":profile.recipient_phone,
       "billing_address":profile.billing_address,"billing_day":profile.billing_day,
       "payment_terms_days":profile.payment_terms_days,"billing_frequency":profile.billing_frequency,"end_date":profile.end_date,
       "stopped_at":profile.stopped_at} if profile else None)
    return data
def audit(db:Session,user:Employee,project_id:int,event:str,note:str=""):
    db.add(FinanceAudit(project_id=project_id,actor_id=user.id,event=event,note=note[:2000]))
def create_row(db:Session,user:Employee,p:Project,d:ProjectDetail,c:ProjectBilling,
               start:date,end:date,quantity:Decimal,tax:Decimal,issued:date,source:str):
    live_period(p,d,c,start,end,issued)
    if not c.recipient_name:raise HTTPException(422,"Billing recipient required")
    existing=db.scalar(select(ClientInvoice.id).where(
      ClientInvoice.project_id==p.id,ClientInvoice.period_start==start,
      ClientInvoice.period_end==end,ClientInvoice.recipient_type==c.recipient_type))
    if existing:raise HTTPException(409,"Invoice already exists for this project, recipient and period")
    rate=charge_rate(db,p.id,c.recipient_type,Decimal(d.rate));money=lambda n:n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    pricing=db.get(ProjectCharge,(p.id,c.recipient_type))
    applied_tax=Decimal(tax) if tax is not None else Decimal(pricing.tax_rate_pct if pricing else 0)
    subtotal=money(rate*quantity);tax_amount=money(subtotal*applied_tax/Decimal(100))
    x=ClientInvoice(project_id=p.id,recipient_type=c.recipient_type,
       recipient_name=c.recipient_name,recipient_email=c.recipient_email,
       recipient_phone=c.recipient_phone,billing_address=c.billing_address,
       period_start=start,period_end=end,issue_date=issued,
       due_date=issued+timedelta(days=c.payment_terms_days),quantity=quantity,
       unit_rate=rate,subtotal=subtotal,tax_rate_pct=applied_tax,
       tax_amount=tax_amount,total=subtotal+tax_amount,currency=d.currency,
       created_by=user.id,source=source)
    db.add(x);db.flush();audit(db,user,p.id,"invoice_created",source)
    return x

@router.get("/projects")
def finance_projects(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    projects=db.scalars(select(Project).order_by(Project.id.desc())).all()
    details={x.project_id:x for x in db.scalars(select(ProjectDetail).where(
        ProjectDetail.project_id.in_([p.id for p in projects]))).all()}
    profiles={x.project_id:x for x in db.scalars(select(ProjectBilling).where(
        ProjectBilling.project_id.in_([p.id for p in projects]))).all()}
    charges=db.scalars(select(ProjectCharge).where(ProjectCharge.project_id.in_([p.id for p in projects]))).all()
    by_project={}
    for charge in charges:by_project.setdefault(charge.project_id,[]).append(charge_view(charge))
    result=[]
    for p in projects:
        if p.id not in details:continue
        entry=billing_view(p,details[p.id],profiles.get(p.id))
        entry["charges"]=by_project.get(p.id,[])
        result.append(entry)
    return result

@router.put("/projects/{project_id}/charges")
def save_charge(project_id:int,body:ChargeIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    project,detail=project_detail(db,project_id)
    if project.status!="active":raise HTTPException(409,"Inactive project pricing is locked")
    row=db.get(ProjectCharge,(project_id,body.recipient_type))
    if row is None:
        row=ProjectCharge(project_id=project_id,recipient_type=body.recipient_type,
                          updated_by=user.id,pricing_value=body.pricing_value)
        db.add(row)
    row.pricing_mode=body.pricing_mode
    row.rate_unit=body.rate_unit
    row.pricing_value=body.pricing_value
    row.tax_rate_pct=body.tax_rate_pct
    row.updated_by=user.id
    audit(db,user,project_id,"pricing_updated",
          f"{body.recipient_type}: {body.pricing_mode} {body.pricing_value}")
    db.commit()
    return charge_view(row) | {"effective_rate":charge_rate(db,project_id,body.recipient_type,Decimal(detail.rate))}


class BillingConfigurationIn(BaseModel):
    """One transactional save for billing contact, cadence and independent invoice rate."""
    recipient_type:Literal["client","vendor","candidate"]="client"
    recipient_name:str=Field(min_length=2,max_length=180)
    recipient_email:EmailStr|None=None
    recipient_phone:str=Field(default="",max_length=40)
    billing_address:str=Field(default="",max_length=2000)
    billing_day:int=Field(ge=1,le=28)
    payment_terms_days:int=Field(ge=0,le=180)
    billing_frequency:Literal["weekly","biweekly","monthly"]="monthly"
    rate_unit:Literal["hour","day","week","month","project"]="hour"
    invoice_rate:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    tax_rate_pct:Decimal=Field(ge=0,le=100,decimal_places=2)


@router.put("/projects/{project_id}/configuration")
def save_billing_configuration(project_id:int,body:BillingConfigurationIn,
                               user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    p,d=project_detail(db,project_id)
    if p.status!="active":raise HTTPException(409,"Inactive projects cannot be edited")
    existing=db.get(ProjectBilling,project_id)
    if existing and existing.stopped_at:raise HTTPException(409,"Project billing has stopped")
    profile=existing or ProjectBilling(project_id=project_id,updated_by=user.id)
    if not existing:db.add(profile)
    for key in ("recipient_type","recipient_name","recipient_email","recipient_phone",
                "billing_address","billing_day","payment_terms_days","billing_frequency"):
        value=getattr(body,key)
        setattr(profile,key,value or "" if key=="recipient_email" else value)
    profile.updated_by=user.id
    charge=db.get(ProjectCharge,(project_id,body.recipient_type))
    if charge is None:
        charge=ProjectCharge(project_id=project_id,recipient_type=body.recipient_type,
                             updated_by=user.id,pricing_value=body.invoice_rate)
        db.add(charge)
    charge.pricing_mode="fixed_rate"
    charge.pricing_value=body.invoice_rate
    charge.rate_unit=body.rate_unit
    charge.tax_rate_pct=body.tax_rate_pct
    charge.updated_by=user.id
    audit(db,user,project_id,"billing_configuration_saved",
          f"cadence={body.billing_frequency}, rate={body.invoice_rate}/{body.rate_unit}")
    db.commit()
    return {"saved":True,"project_id":project_id,"billing_frequency":profile.billing_frequency,
            "invoice_rate":charge.pricing_value,"rate_unit":charge.rate_unit}

@router.put("/projects/{project_id}/billing")
def set_billing(project_id:int,body:BillingIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    p,d=project_detail(db,project_id)
    if body.end_date and d.start_date and body.end_date<d.start_date:
        raise HTTPException(422,"End date precedes project start")
    c=db.get(ProjectBilling,project_id)
    if c is None:
        c=ProjectBilling(project_id=project_id,updated_by=user.id)
        db.add(c)
    if c.stopped_at is not None:raise HTTPException(409,"Inactive project billing is locked")
    if user.role not in HR and c.end_date!=body.end_date:
        raise HTTPException(403,"Only HR can alter a project end date")
    for k,v in body.model_dump().items():
        setattr(c,k,"" if v is None and k=="recipient_email" else v)
    c.updated_by=user.id
    audit(db,user,p.id,"billing_updated")
    db.commit()
    return billing_view(p,d,c)

@router.put("/projects/{project_id}/lifecycle")
def change_project_state(project_id:int,body:ProjectStateIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    hr_only(user)
    p,d=project_detail(db,project_id)
    c=db.get(ProjectBilling,project_id)
    if c is None:
        c=ProjectBilling(project_id=project_id,updated_by=user.id)
        db.add(c)
    if body.end_date and d.start_date and body.end_date<d.start_date:
        raise HTTPException(422,"End date precedes project start")
    if body.active:
        if p.status=="active":raise HTTPException(409,"Project already active")
        # Requires an explicit audit reason to restart invoicing after a stop.
        p.status="active";c.stopped_at=None;c.end_date=body.end_date
        audit(db,user,p.id,"project_reactivated",body.reason)
    else:
        if p.status!="active":raise HTTPException(409,"Project already inactive")
        # A future end date is scheduled without prematurely preventing final invoicing.
        if body.end_date and body.end_date>date.today():
            c.end_date=body.end_date
            audit(db,user,p.id,"project_end_scheduled",body.reason)
        else:
            p.status="inactive";c.stopped_at=body.end_date or date.today()
            c.end_date=body.end_date or date.today()
            audit(db,user,p.id,"project_deactivated",body.reason)
    c.updated_by=user.id;db.commit()
    return {"project_id":p.id,"status":p.status,"end_date":c.end_date,"stopped_at":c.stopped_at}

@router.get("/invoices")
def invoices(project_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    q=select(ClientInvoice).order_by(ClientInvoice.id.desc())
    if project_id:q=q.where(ClientInvoice.project_id==project_id)
    return [invoice_view(x) for x in db.scalars(q.limit(1000)).all()]

@router.post("/invoices",status_code=201)
def create_invoice(body:InvoiceIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    p,d=project_detail(db,body.project_id);c=db.get(ProjectBilling,p.id)
    if c is None:raise HTTPException(422,"Configure project billing first")
    x=create_row(db,user,p,d,c,body.period_start,body.period_end,body.quantity,
                 body.tax_rate_pct,body.issue_date,"manual")
    db.commit();db.refresh(x);return invoice_view(x)

@router.post("/schedules/run")
def run_schedule(body:ScheduleIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    if body.as_of!=date.today() and user.role not in ("admin","super_admin"):
        raise HTTPException(403,"Historical schedule runs require admin")
    q=select(ProjectBilling).where(ProjectBilling.billing_day.is_not(None))
    if body.project_id is not None:q=q.where(ProjectBilling.project_id==body.project_id)
    created=[];skipped=[];tasks_created=[]
    from .billing_reviews import BillableReview, create_review
    for c in db.scalars(q).all():
        p=db.get(Project,c.project_id);d=db.get(ProjectDetail,c.project_id)
        if not p or not d or not d.start_date or p.status!="active" or c.stopped_at:
            skipped.append({"project_id":c.project_id,"reason":"inactive or invalid project"});continue
        if c.end_date and body.as_of>c.end_date:
            p.status="inactive";c.stopped_at=c.end_date
            db.commit();skipped.append({"project_id":p.id,"reason":"project ended; schedule disabled"});continue
        end=c.end_date
        cadence=c.billing_frequency or "monthly"
        if cadence=="monthly":
            scheduled=body.as_of.day==c.billing_day
        else:
            # For weekly/biweekly schedules, billing_day represents weekday 1=Mon..7=Sun.
            anchor=d.start_date
            weekday=(c.billing_day-1)%7+1
            days_elapsed=(body.as_of-anchor).days
            scheduled=(body.as_of.isoweekday()==weekday and
                       (cadence=="weekly" or days_elapsed//7%2==0))
        if body.as_of>d.start_date and (scheduled or (end and body.as_of==end)):
            prior=db.scalar(select(func.max(ClientInvoice.period_end)).where(
                ClientInvoice.project_id==p.id,ClientInvoice.recipient_type==c.recipient_type))
            other=db.scalar(select(func.max(BillableReview.period_end)).where(BillableReview.project_id==p.id))
            last=max([x for x in (prior,other) if x is not None],default=None)
            start=max(d.start_date,last+timedelta(days=1) if last else d.start_date)
            period_end=min(body.as_of,end) if end else body.as_of
            if start>period_end:
                skipped.append({"project_id":p.id,"reason":"nothing to bill"});continue
            task=create_review(db,user,p.id,start,period_end,body.as_of)
            if task:
                db.commit()
                tasks_created.append(task)
            else:
                skipped.append({"project_id":p.id,"reason":"review already exists"})
        else:
            skipped.append({"project_id":p.id,"reason":"not scheduled today or already ended"})
    return {"as_of":body.as_of,"created":created,"tasks_created":tasks_created,"skipped":skipped,"email_sent":False}

@router.post("/invoices/{invoice_id}/status")
def change_status(invoice_id:int,body:InvoiceStatusIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    x=db.get(ClientInvoice,invoice_id)
    if not x:raise HTTPException(404,"Invoice not found")
    if x.status in ("paid","void"):raise HTTPException(409,"Final invoice cannot be changed")
    if body.status=="sent" and x.status!="draft":raise HTTPException(409,"Only draft can be sent")
    if body.status=="paid" and x.status!="sent":raise HTTPException(409,"Invoice must be marked sent first")
    x.status=body.status;x.reference=body.reference
    if body.status=="paid":x.paid_at=now()
    audit(db,user,x.project_id,"invoice_"+body.status,body.reference)
    db.commit();return invoice_view(x)

@router.get("/invoices/{invoice_id}.pdf")
def invoice_pdf(invoice_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    x=db.get(ClientInvoice,invoice_id)
    if not x:raise HTTPException(404,"Invoice not found")
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape
    buf=io.BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4);styles=getSampleStyleSheet()
    safe=lambda s:escape(str(s or ""))
    story=[Paragraph("JellyGit — Invoice Draft / Recorded Invoice",styles["Heading1"]),
      Spacer(1,12),Paragraph("Invoice #"+str(x.id)+" — "+safe(x.status).upper(),styles["Normal"]),
      Paragraph("Bill to: "+safe(x.recipient_name)+" ("+safe(x.recipient_type)+")",styles["Normal"]),
      Paragraph("Email: "+safe(x.recipient_email)+" | Phone: "+safe(x.recipient_phone),styles["Normal"]),
      Paragraph("Address: "+safe(x.billing_address),styles["Normal"]),
      Paragraph("Service period: "+str(x.period_start)+" to "+str(x.period_end),styles["Normal"]),
      Paragraph("Issued: "+str(x.issue_date)+" | Due: "+str(x.due_date),styles["Normal"]),Spacer(1,12)]
    story.append(Table([["Qty","Rate","Subtotal","Tax","Total"],
       [str(x.quantity),str(x.unit_rate),str(x.subtotal),str(x.tax_amount),str(x.total)+" "+x.currency]]))
    story.append(Spacer(1,15));story.append(Paragraph("Payment is tracked in HRMS; this document is not evidence of payment.",styles["Normal"]))
    doc.build(story);buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",
      headers={"Content-Disposition":f'attachment; filename="invoice-{x.id}.pdf"',
               "Cache-Control":"private, no-store"})

@router.get("/audit")
def finance_audit(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    return [{"project_id":x.project_id,"actor_id":x.actor_id,"event":x.event,"note":x.note,
             "at":x.at} for x in db.scalars(select(FinanceAudit).order_by(FinanceAudit.id.desc()).limit(300)).all()]
