"""HR operations 39-45: offers, onboarding, announcements, helpdesk,
exit workflow, analytics, notification outbox and audit events.
These are internal workflows, not a certified e-signature or messaging provider.
"""
import io
import os
import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, Attendance, current_user, db_session
from .employee_core import EmployeeCore
from .leave_management import LeaveRequest
from .payroll import PayrollLine, PayrollRun

router=APIRouter(prefix="/people",tags=["People Operations"])
HR=("super_admin","admin","hr")
FIN=HR+("accountant",)
def now():return datetime.now(timezone.utc)
def is_hr(user):return user.role in HR
def require_hr(user):
    if not is_hr(user):raise HTTPException(403,"HR access required.")
def owned(user,owner):
    if user.id!=owner and not is_hr(user):raise HTTPException(403,"Access restricted to owner or HR.")
def audit(db,actor,kind,object_id,action,note=""):
    db.add(HRAudit(actor_id=actor.id,kind=kind,object_id=object_id,action=action,note=note[:500]))

class HRAudit(Base):
    __tablename__="people_audit"
    id:Mapped[int]=mapped_column(primary_key=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    kind:Mapped[str]=mapped_column(String(50))
    object_id:Mapped[int]=mapped_column(Integer)
    action:Mapped[str]=mapped_column(String(50))
    note:Mapped[str]=mapped_column(String(500),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class OfferTemplate(Base):
    __tablename__="people_offer_templates"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    content:Mapped[str]=mapped_column(Text)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Offer(Base):
    __tablename__="people_offers"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    template_id:Mapped[int]=mapped_column(ForeignKey("people_offer_templates.id"))
    title:Mapped[str]=mapped_column(String(150))
    annual_ctc:Mapped[Decimal]=mapped_column(Numeric(13,2))
    joining_date:Mapped[date]=mapped_column(Date)
    rendered_content:Mapped[str]=mapped_column(Text)
    document_hash:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(20),default="draft")
    signed_name:Mapped[str|None]=mapped_column(String(150),nullable=True)
    signed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class OnboardingTask(Base):
    __tablename__="people_onboarding_tasks"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    category:Mapped[str]=mapped_column(String(30))
    title:Mapped[str]=mapped_column(String(150))
    due_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    assigned_to:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    asset_code:Mapped[str]=mapped_column(String(120),default="")
    status:Mapped[str]=mapped_column(String(20),default="pending")
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class Announcement(Base):
    __tablename__="people_announcements"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(180))
    body:Mapped[str]=mapped_column(Text)
    requires_ack:Mapped[bool]=mapped_column(Boolean,default=False)
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class AnnouncementAck(Base):
    __tablename__="people_announcement_acks"
    id:Mapped[int]=mapped_column(primary_key=True)
    announcement_id:Mapped[int]=mapped_column(ForeignKey("people_announcements.id"))
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class HelpdeskTicket(Base):
    __tablename__="people_helpdesk_tickets"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    category:Mapped[str]=mapped_column(String(35))
    subject:Mapped[str]=mapped_column(String(160))
    description:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(25),default="open")
    hr_response:Mapped[str]=mapped_column(Text,default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExitCase(Base):
    __tablename__="people_exit_cases"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    reason:Mapped[str]=mapped_column(Text)
    requested_date:Mapped[date]=mapped_column(Date)
    notice_days:Mapped[int]=mapped_column(Integer)
    planned_last_day:Mapped[date]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(30),default="requested")
    clearance_assets:Mapped[bool]=mapped_column(Boolean,default=False)
    clearance_it:Mapped[bool]=mapped_column(Boolean,default=False)
    clearance_finance:Mapped[bool]=mapped_column(Boolean,default=False)
    final_settlement_inr:Mapped[Decimal|None]=mapped_column(Numeric(12,2),nullable=True)
    final_settlement_note:Mapped[str]=mapped_column(Text,default="")
    approved_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)

class NotifyRule(Base):
    __tablename__="people_notification_rules"
    id:Mapped[int]=mapped_column(primary_key=True)
    event:Mapped[str]=mapped_column(String(50),unique=True)
    email:Mapped[bool]=mapped_column(Boolean,default=True)
    sms:Mapped[bool]=mapped_column(Boolean,default=False)
    push:Mapped[bool]=mapped_column(Boolean,default=False)
    whatsapp:Mapped[bool]=mapped_column(Boolean,default=False)

class NotifyOutbox(Base):
    __tablename__="people_notification_outbox"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    event:Mapped[str]=mapped_column(String(50))
    subject:Mapped[str]=mapped_column(String(160))
    body:Mapped[str]=mapped_column(Text)
    channel:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(25),default="queued")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TemplateIn(BaseModel):
    name:str=Field(min_length=3,max_length=120)
    content:str=Field(min_length=30,max_length=10000)

class OfferIn(BaseModel):
    employee_id:int
    template_id:int
    title:str=Field(min_length=3,max_length=150)
    annual_ctc:Decimal=Field(ge=0,le=1000000000)
    joining_date:date

class SignIn(BaseModel):
    printed_name:str=Field(min_length=3,max_length=150)
    consent:bool

class TaskIn(BaseModel):
    employee_id:int
    category:Literal["document","asset","induction","hr","it"]
    title:str=Field(min_length=3,max_length=150)
    due_date:date|None=None
    assigned_to:int|None=None
    asset_code:str=Field(default="",max_length=120)

class AnnouncementIn(BaseModel):
    title:str=Field(min_length=4,max_length=180)
    body:str=Field(min_length=12,max_length=10000)
    requires_ack:bool=False

class TicketIn(BaseModel):
    category:Literal["payroll","leave","attendance","benefits","it","other"]
    subject:str=Field(min_length=4,max_length=160)
    description:str=Field(min_length=12,max_length=5000)

class TicketReply(BaseModel):
    status:Literal["in_progress","resolved","closed"]
    reply:str=Field(min_length=5,max_length=5000)

class ExitIn(BaseModel):
    reason:str=Field(min_length=10,max_length=2000)
    notice_days:int=Field(ge=0,le=365)
    requested_date:date=Field(default_factory=date.today)

class ExitUpdate(BaseModel):
    status:Literal["approved","rejected","clearance","settled"]
    clearance_assets:bool=False
    clearance_it:bool=False
    clearance_finance:bool=False
    final_settlement_inr:Decimal|None=Field(default=None,ge=0,le=100000000)
    final_settlement_note:str=Field(default="",max_length=2000)

class RuleIn(BaseModel):
    event:Literal["approval","birthday","document_renewal","helpdesk","offer","exit"]
    email:bool=True
    sms:bool=False
    push:bool=False
    whatsapp:bool=False

class QueueIn(BaseModel):
    employee_id:int
    event:Literal["approval","birthday","document_renewal","helpdesk","offer","exit"]
    subject:str=Field(min_length=4,max_length=160)
    body:str=Field(min_length=5,max_length=2500)

def notify(db,employee_id,event,subject,body):
    rule=db.scalar(select(NotifyRule).where(NotifyRule.event==event))
    channels=[c for c in ("email","sms","push","whatsapp") if not rule or getattr(rule,c)]
    if not rule:channels=["email"]
    for channel in channels:
        # A queued adapter is not a claim of delivery. No background sender until configured.
        db.add(NotifyOutbox(employee_id=employee_id,event=event,subject=subject,body=body,
                            channel=channel,status="queued"))

@router.post("/offer-templates",status_code=201)
def create_template(body:TemplateIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=OfferTemplate(**body.model_dump());db.add(row);db.flush()
    audit(db,user,"offer_template",row.id,"created");db.commit()
    return {"id":row.id,"name":row.name}

@router.get("/offer-templates")
def templates(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    return [{"id":r.id,"name":r.name,"content":r.content} for r in db.scalars(select(OfferTemplate)).all()]

@router.post("/offers",status_code=201)
def create_offer(body:OfferIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    emp=db.get(Employee,body.employee_id);templ=db.get(OfferTemplate,body.template_id)
    if not emp or not templ or not templ.active:raise HTTPException(422,"Choose a valid employee and active offer template.")
    content=templ.content
    # Offer templates may include {{salary_breakdown}} to show the reviewed items
    # that exist when the offer is generated. Sent offers remain immutable snapshots.
    from .payroll_components import effective_components
    from .payroll import SalaryStructure
    base=db.get(SalaryStructure,emp.id)
    breakdown=[]
    if base and base.effective_from<=body.joining_date:
        breakdown.extend([f"Basic salary: INR {base.basic}/month",
                          f"HRA: INR {base.hra}/month",
                          f"Other allowances: INR {base.allowances}/month",
                          f"Other deductions: INR {base.other_deductions}/month"])
    for item in effective_components(db,emp.id,body.joining_date):
        breakdown.append(f"{item.title} ({item.kind}): INR {item.amount}/month")
    content=content.replace("{{salary_breakdown}}","\n".join(breakdown) if breakdown else "Salary breakdown pending HR review")
    for key,value in (("employee_name",emp.name),("job_title",body.title),
            ("annual_ctc",str(body.annual_ctc)),("joining_date",body.joining_date.isoformat())):
        content=content.replace("{{"+key+"}}",value)
    digest=hashlib.sha256(content.encode()).hexdigest()
    row=Offer(employee_id=emp.id,template_id=templ.id,title=body.title,
              annual_ctc=body.annual_ctc,joining_date=body.joining_date,rendered_content=content,
              document_hash=digest,created_by=user.id)
    db.add(row);db.flush();audit(db,user,"offer",row.id,"created")
    db.commit();return {"id":row.id,"status":row.status,"hash":digest}

@router.get("/offers")
def list_offers(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(Offer).order_by(Offer.id.desc())
    if not is_hr(user):q=q.where(Offer.employee_id==user.id)
    return [{k:getattr(r,k) for k in ("id","employee_id","title","annual_ctc","joining_date",
                                    "status","signed_name","signed_at")} for r in db.scalars(q).all()]

@router.post("/offers/{offer_id}/send")
def send_offer(offer_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=db.get(Offer,offer_id)
    if not row:raise HTTPException(404)
    if row.status!="draft":raise HTTPException(409)
    row.status="sent";audit(db,user,"offer",row.id,"sent")
    notify(db,row.employee_id,"offer","Your employment offer","A new employment offer is available in HRMS.")
    db.commit();return {"status":row.status}

@router.post("/offers/{offer_id}/sign")
def sign_offer(offer_id:int,body:SignIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(Offer,offer_id)
    if not row:raise HTTPException(404)
    if row.employee_id!=user.id:raise HTTPException(403)
    if row.status!="sent":raise HTTPException(409,"Offer is not awaiting acceptance.")
    if not body.consent or body.printed_name.casefold().strip()!=user.name.casefold().strip():
        raise HTTPException(422,"Explicit consent and matching full printed name are required.")
    row.signed_name=body.printed_name.strip();row.signed_at=now();row.status="accepted"
    audit(db,user,"offer",row.id,"accepted","Employee typed-name acceptance; not a qualified e-sign provider")
    db.commit();return {"status":row.status,"signed_at":row.signed_at,
                        "signature_type":"internal_acknowledgment_not_qualified_esign"}

@router.get("/offers/{offer_id}.pdf")
def offer_pdf(offer_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    from reportlab.pdfgen import canvas
    row=db.get(Offer,offer_id)
    if not row:raise HTTPException(404)
    owned(user,row.employee_id)
    if row.status=="draft" and not is_hr(user):raise HTTPException(404)
    b=io.BytesIO();pdf=canvas.Canvas(b,pagesize=(595,842))
    pdf.setTitle("Employment Offer")
    pdf.setFont("Helvetica-Bold",18);pdf.drawString(45,784,"JellyGit | Employment Offer")
    pdf.setFont("Helvetica",10)
    from reportlab.lib.utils import simpleSplit
    y=740
    for original in row.rendered_content.splitlines():
        for line in simpleSplit(original,"Helvetica",10,490):
            if y<80:pdf.showPage();pdf.setFont("Helvetica",10);y=760
            pdf.drawString(45,y,line);y-=16
        y-=8
    if row.signed_at:
        if y<110:pdf.showPage();y=750
        pdf.drawString(45,y-25,"Acknowledged by "+row.signed_name+" on "+row.signed_at.isoformat())
    pdf.showPage();pdf.save();b.seek(0)
    return StreamingResponse(b,media_type="application/pdf",headers={
       "Content-Disposition":f'attachment; filename="offer-{offer_id}.pdf"',"Cache-Control":"private, no-store"})

@router.post("/onboarding",status_code=201)
def add_task(body:TaskIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Employee not found.")
    if body.assigned_to and not db.get(Employee,body.assigned_to):raise HTTPException(422,"Assignee not found.")
    row=OnboardingTask(**body.model_dump());db.add(row);db.flush()
    audit(db,user,"onboarding",row.id,"created");db.commit()
    return {"id":row.id,"status":row.status}

@router.get("/onboarding")
def tasks(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if employee_id:owned(user,employee_id)
    q=select(OnboardingTask).order_by(OnboardingTask.id.desc())
    if not is_hr(user):q=q.where((OnboardingTask.employee_id==user.id)|(OnboardingTask.assigned_to==user.id))
    elif employee_id:q=q.where(OnboardingTask.employee_id==employee_id)
    return [{k:getattr(r,k) for k in ("id","employee_id","category","title","due_date",
                              "assigned_to","asset_code","status")} for r in db.scalars(q).all()]

@router.post("/onboarding/{task_id}/complete")
def complete_task(task_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(OnboardingTask,task_id)
    if not row:raise HTTPException(404)
    if not is_hr(user) and row.assigned_to!=user.id:raise HTTPException(403,"Task assignee or HR only.")
    if row.status!="pending":raise HTTPException(409)
    row.status="completed";row.completed_at=now();audit(db,user,"onboarding",row.id,"completed")
    db.commit();return {"status":row.status}

@router.post("/announcements",status_code=201)
def add_announcement(body:AnnouncementIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=Announcement(**body.model_dump(),created_by=user.id);db.add(row);db.flush()
    audit(db,user,"announcement",row.id,"published");db.commit();return {"id":row.id}

@router.get("/announcements")
def announcements(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Announcement).order_by(Announcement.id.desc()).limit(100)).all()
    acked=set(db.scalars(select(AnnouncementAck.announcement_id).where(
        AnnouncementAck.employee_id==user.id)).all())
    return [{"id":r.id,"title":r.title,"body":r.body,"requires_ack":r.requires_ack,
             "acknowledged":r.id in acked,"published_at":r.published_at} for r in rows]

@router.post("/announcements/{announcement_id}/ack")
def acknowledge(announcement_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(Announcement,announcement_id)
    if not row:raise HTTPException(404)
    existing=db.scalar(select(AnnouncementAck.id).where(
        AnnouncementAck.announcement_id==announcement_id,AnnouncementAck.employee_id==user.id))
    if existing:return {"acknowledged":True}
    db.add(AnnouncementAck(announcement_id=announcement_id,employee_id=user.id))
    audit(db,user,"announcement",announcement_id,"acknowledged");db.commit()
    return {"acknowledged":True}

@router.post("/tickets",status_code=201)
def create_ticket(body:TicketIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=HelpdeskTicket(**body.model_dump(),employee_id=user.id);db.add(row);db.flush()
    audit(db,user,"ticket",row.id,"opened")
    for recipient in db.scalars(select(Employee.id).where(Employee.role.in_(HR),Employee.status=="active")).all():
        notify(db,recipient,"helpdesk","New HR helpdesk ticket",body.subject)
    db.commit();return {"id":row.id,"status":row.status}

@router.get("/tickets")
def tickets(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all":require_hr(user)
    q=select(HelpdeskTicket).order_by(HelpdeskTicket.id.desc())
    if scope=="mine":q=q.where(HelpdeskTicket.employee_id==user.id)
    return [{k:getattr(r,k) for k in ("id","employee_id","category","subject",
             "description","status","hr_response","updated_at")} for r in db.scalars(q).all()]

@router.post("/tickets/{ticket_id}/review")
def reply(ticket_id:int,body:TicketReply,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=db.get(HelpdeskTicket,ticket_id)
    if not row:raise HTTPException(404)
    if row.status=="closed":raise HTTPException(409)
    row.status=body.status;row.hr_response=body.reply;row.updated_at=now()
    audit(db,user,"ticket",row.id,"replied")
    notify(db,row.employee_id,"helpdesk","HR ticket update",row.subject+" is now "+row.status)
    db.commit();return {"status":row.status}

@router.post("/exits",status_code=201)
def request_exit(body:ExitIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if body.requested_date<date.today()-timedelta(days=7):raise HTTPException(422,"Request date is too old.")
    active=db.scalar(select(ExitCase.id).where(ExitCase.employee_id==user.id,
        ExitCase.status.in_(["requested","approved","clearance"])))
    if active:raise HTTPException(409,"An exit case is already in progress.")
    row=ExitCase(employee_id=user.id,reason=body.reason,
        requested_date=body.requested_date,notice_days=body.notice_days,
        planned_last_day=body.requested_date+timedelta(days=body.notice_days))
    db.add(row);db.flush();audit(db,user,"exit",row.id,"requested");db.commit()
    return {"id":row.id,"status":row.status,"last_day":row.planned_last_day}

@router.get("/exits")
def exits(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all":require_hr(user)
    q=select(ExitCase).order_by(ExitCase.id.desc())
    if scope=="mine":q=q.where(ExitCase.employee_id==user.id)
    return [{k:getattr(r,k) for k in ("id","employee_id","reason","requested_date","notice_days",
        "planned_last_day","status","clearance_assets","clearance_it","clearance_finance",
        "final_settlement_inr","final_settlement_note")} for r in db.scalars(q).all()]

@router.post("/exits/{exit_id}/review")
def review_exit(exit_id:int,body:ExitUpdate,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=db.get(ExitCase,exit_id)
    if not row:raise HTTPException(404)
    if row.status in ("settled","rejected"):raise HTTPException(409)
    if body.status=="settled":
        from .people_ops_extensions import ExitClearance
        approved=set(db.scalars(select(ExitClearance.kind).where(ExitClearance.exit_id==exit_id)).all())
        if not {"assets","it","finance"}.issubset(approved):
            raise HTTPException(422,"Documented asset, IT and Finance clearance approvals are required before settlement.")
        if not all((body.clearance_assets,body.clearance_it,body.clearance_finance)):
            raise HTTPException(422,"Asset, IT and Finance clearance are all required.")
        if body.final_settlement_inr is None:
            raise HTTPException(422,"F&F amount must be entered and reviewed by Finance.")
    row.status=body.status
    row.clearance_assets=body.clearance_assets
    row.clearance_it=body.clearance_it
    row.clearance_finance=body.clearance_finance
    row.final_settlement_inr=body.final_settlement_inr
    row.final_settlement_note=body.final_settlement_note
    row.approved_by=user.id
    audit(db,user,"exit",row.id,body.status)
    db.commit();return {"status":row.status,"settlement_paid":False}

@router.get("/analytics")
def analytics(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    today=date.today();start=date(today.year,1,1)
    total=db.scalar(select(func.count()).select_from(Employee).where(Employee.status=="active")) or 0
    inactive=db.scalar(select(func.count()).select_from(Employee).where(Employee.status!="active")) or 0
    pending_leave=db.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status=="pending")) or 0
    open_tickets=db.scalar(select(func.count()).select_from(HelpdeskTicket).where(HelpdeskTicket.status!="closed")) or 0
    payroll=db.execute(select(PayrollRun.period,func.sum(PayrollLine.net)).join(
        PayrollLine,PayrollLine.run_id==PayrollRun.id).where(PayrollRun.status=="published").group_by(
        PayrollRun.period).order_by(PayrollRun.period.desc()).limit(12)).all()
    dept=db.execute(select(Employee.department,func.count()).where(Employee.status=="active").group_by(
        Employee.department)).all()
    return {"active_headcount":total,"inactive_headcount":inactive,
            "attrition_proxy_pct":round(100*inactive/max(1,total+inactive),2),
            "pending_leave":pending_leave,"open_tickets":open_tickets,
            "departments":[{"department":n,"employees":count} for n,count in dept],
            "published_monthly_net":[{"period":period,"net":amount} for period,amount in payroll],
            "note":"Attrition proxy is inactive share, not trailing-12-month attrition. Payroll cost excludes employer taxes and gratuity."}

@router.put("/notification-rules")
def set_rule(body:RuleIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    row=db.scalar(select(NotifyRule).where(NotifyRule.event==body.event))
    if not row:row=NotifyRule(event=body.event);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    db.flush();audit(db,user,"notification_rule",row.id,"configured")
    db.commit();return body.model_dump()

@router.get("/notification-rules")
def get_rules(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    return [{k:getattr(r,k) for k in ("event","email","sms","push","whatsapp")}
            for r in db.scalars(select(NotifyRule)).all()]

@router.post("/notifications/queue")
def queue(body:QueueIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Invalid recipient.")
    notify(db,**body.model_dump());db.commit()
    return {"queued":True,"delivered":False}

@router.get("/notifications")
def notifications(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(NotifyOutbox).where(NotifyOutbox.employee_id==user.id).order_by(
        NotifyOutbox.id.desc()).limit(100)
    return [{"id":r.id,"event":r.event,"subject":r.subject,"body":r.body,
             "channel":r.channel,"status":r.status,"created_at":r.created_at} for r in db.scalars(q).all()]

@router.get("/audit")
def audit_log(kind:str|None=None,limit:int=50,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    if not 1<=limit<=200:raise HTTPException(422)
    q=select(HRAudit).order_by(HRAudit.id.desc()).limit(limit)
    if kind:q=q.where(HRAudit.kind==kind)
    return [{"id":r.id,"actor_id":r.actor_id,"kind":r.kind,"object_id":r.object_id,
             "action":r.action,"note":r.note,"created_at":r.created_at}
            for r in db.scalars(q).all()]

ORIENTATION_STEPS=(
 ("hr","Meet your HR buddy",3),
 ("document","Complete identity and payroll documents",7),
 ("it","Set up password and multi-factor authentication",2),
 ("asset","Receive laptop and company equipment",3),
 ("induction","Read and acknowledge employee handbook",7),
 ("induction","Attend leave and attendance walkthrough",5),
 ("induction","Complete first-week team and project orientation",7),
)

@router.post("/onboarding/orientation/{employee_id}")
def start_orientation(employee_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    person=db.get(Employee,employee_id)
    if not person or person.status!="active":raise HTTPException(422,"Active employee required")
    existing=set(db.scalars(select(OnboardingTask.title).where(
        OnboardingTask.employee_id==employee_id)).all())
    added=0
    for category,title,days in ORIENTATION_STEPS:
        if title in existing:continue
        task=OnboardingTask(employee_id=employee_id,category=category,title=title,
            due_date=date.today()+timedelta(days=days),assigned_to=employee_id)
        db.add(task);db.flush();audit(db,user,"orientation",task.id,"created")
        added+=1
    db.commit()
    return {"employee_id":employee_id,"created":added,"total_steps":len(ORIENTATION_STEPS)}

@router.get("/onboarding/orientation/{employee_id}")
def orientation_status(employee_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    owned(user,employee_id)
    titles=[x[1] for x in ORIENTATION_STEPS]
    rows=db.scalars(select(OnboardingTask).where(
        OnboardingTask.employee_id==employee_id,OnboardingTask.title.in_(titles))).all()
    completed=sum(x.status=="completed" for x in rows)
    return {"employee_id":employee_id,"total":len(rows),"completed":completed,
       "progress_pct":round(100*completed/len(rows),1) if rows else 0,
       "steps":[{"id":x.id,"title":x.title,"status":x.status,
                 "due_date":x.due_date} for x in rows]}
