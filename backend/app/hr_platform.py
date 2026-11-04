"""HR analytics, notification outbox, change audit and accounting-export integration."""
from __future__ import annotations
import csv
import io
import os
import smtplib
import ssl
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from email.message import EmailMessage
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String,Text,UniqueConstraint,select,func
from sqlalchemy.orm import Mapped,Session,mapped_column

from .main import Base,Employee,Attendance,Document,current_user,db_session
from .employee_core import EmployeeCore,DocumentMetadata
from .leave_management import LeaveRequest
from .payroll import PayrollRun,PayrollLine,ExpenseClaim
from .people_ops import ExitRequest,Offer,HelpTicket

router=APIRouter(prefix="/platform",tags=["Analytics & Notifications"])
HR=("super_admin","admin","hr")
FIN=HR+("accountant",)
def now():return datetime.now(timezone.utc)
def hr(user:Employee=Depends(current_user)):
    if user.role not in HR:raise HTTPException(403,"HR access required")
    return user
def finance(user:Employee=Depends(current_user)):
    if user.role not in FIN:raise HTTPException(403,"Finance access required")
    return user

class AuditEvent(Base):
    __tablename__="platform_audit"
    id:Mapped[int]=mapped_column(primary_key=True)
    actor_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True,index=True)
    action:Mapped[str]=mapped_column(String(100),index=True)
    resource:Mapped[str]=mapped_column(String(120))
    reason:Mapped[str]=mapped_column(Text,default="")
    ip:Mapped[str]=mapped_column(String(64),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class NotifyRule(Base):
    __tablename__="platform_notify_rules"
    id:Mapped[int]=mapped_column(primary_key=True)
    event:Mapped[str]=mapped_column(String(70),unique=True)
    email:Mapped[bool]=mapped_column(Boolean,default=True)
    sms:Mapped[bool]=mapped_column(Boolean,default=False)
    push:Mapped[bool]=mapped_column(Boolean,default=False)
    whatsapp:Mapped[bool]=mapped_column(Boolean,default=False)
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)

class NotifyPreference(Base):
    __tablename__="platform_notify_preferences"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),unique=True)
    email:Mapped[bool]=mapped_column(Boolean,default=True)
    sms:Mapped[bool]=mapped_column(Boolean,default=False)
    push:Mapped[bool]=mapped_column(Boolean,default=False)
    whatsapp:Mapped[bool]=mapped_column(Boolean,default=False)

class Outbox(Base):
    __tablename__="platform_outbox"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    event:Mapped[str]=mapped_column(String(70),index=True)
    channel:Mapped[str]=mapped_column(String(20))
    subject:Mapped[str]=mapped_column(String(180))
    message:Mapped[str]=mapped_column(Text)
    dedupe_key:Mapped[str]=mapped_column(String(180),unique=True)
    status:Mapped[str]=mapped_column(String(25),default="queued")
    error:Mapped[str]=mapped_column(String(300),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    sent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class RuleIn(BaseModel):
    event:Literal["approval","birthday","document_expiry","announcement","onboarding","exit","payroll"]
    enabled:bool=True
    email:bool=True
    sms:bool=False
    push:bool=False
    whatsapp:bool=False

class PreferencesIn(BaseModel):
    email:bool=True
    sms:bool=False
    push:bool=False
    whatsapp:bool=False

class NotifyIn(BaseModel):
    event:Literal["approval","birthday","document_expiry","announcement","onboarding","exit","payroll"]
    employee_id:int
    subject:str=Field(min_length=3,max_length=180)
    message:str=Field(min_length=3,max_length=2000)
    reference:str=Field(min_length=1,max_length=90)

def audit(db:Session,actor:int|None,action:str,resource:str,reason:str="",ip:str=""):
    db.add(AuditEvent(actor_id=actor,action=action,resource=resource,
                      reason=reason[:500],ip=ip[:64]))

def enqueue(db:Session,event:str,employee_id:int,subject:str,message:str,reference:str)->int:
    rule=db.scalar(select(NotifyRule).where(NotifyRule.event==event))
    if rule and not rule.enabled:return 0
    prefs=db.scalar(select(NotifyPreference).where(NotifyPreference.employee_id==employee_id))
    if not db.get(Employee,employee_id):return 0
    channels=[]
    for ch in ("email","sms","push","whatsapp"):
        if (getattr(rule,ch) if rule else ch=="email") and (getattr(prefs,ch) if prefs else ch=="email"):
            channels.append(ch)
    count=0
    for channel in channels:
        key=f"{event}:{employee_id}:{reference}:{channel}"
        if db.scalar(select(Outbox.id).where(Outbox.dedupe_key==key)):continue
        db.add(Outbox(employee_id=employee_id,event=event,channel=channel,
                      subject=subject,message=message,dedupe_key=key))
        count+=1
    return count

@router.get("/analytics")
def analytics(year:int=date.today().year,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if not 2020<=year<=2100:raise HTTPException(422)
    people=db.scalars(select(Employee)).all()
    headcount=sum(p.status=="active" for p in people)
    by_department=dict(Counter(p.department or "Unassigned" for p in people if p.status=="active"))
    joiners=sum(p.joining_date.year==year for p in people)
    exits=db.scalars(select(ExitRequest).where(
        ExitRequest.status=="approved",ExitRequest.approved_last_day>=date(year,1,1),
        ExitRequest.approved_last_day<=date(year,12,31))).all()
    attrition=len(exits)
    leaves=db.scalars(select(LeaveRequest).where(LeaveRequest.status=="approved",
        LeaveRequest.start_date>=date(year,1,1),LeaveRequest.start_date<=date(year,12,31))).all()
    leave_by_type=dict(Counter(x.leave_type for x in leaves))
    punches=db.scalars(select(Attendance).where(Attendance.punch_in>=datetime(year,1,1,tzinfo=timezone.utc),
        Attendance.punch_in<datetime(year+1,1,1,tzinfo=timezone.utc))).all()
    punch_by_month=dict(Counter(x.punch_in.strftime("%Y-%m") for x in punches))
    costs=db.execute(select(PayrollRun.year,PayrollRun.month,func.sum(PayrollLine.net))
                     .join(PayrollLine,PayrollLine.run_id==PayrollRun.id)
                     .where(PayrollRun.year==year,PayrollRun.status=="approved")
                     .group_by(PayrollRun.year,PayrollRun.month)).all()
    return {"year":year,"headcount":headcount,"by_department":by_department,
            "joiners":joiners,"approved_exits":attrition,
            "attrition_ratio_pct":round(100*attrition/max(1,headcount+attrition),2),
            "approved_leaves_by_type":leave_by_type,
            "attendance_sessions_by_month":punch_by_month,
            "net_payroll_by_month":{f"{y}-{m:02d}":float(amount) for y,m,amount in costs},
            "scope_note":"Attrition denominator is a snapshot estimate, not average headcount."}

@router.get("/audit")
def audits(limit:int=100,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if not 1<=limit<=500:raise HTTPException(422)
    return [{"id":x.id,"actor_id":x.actor_id,"action":x.action,"resource":x.resource,
             "reason":x.reason,"created_at":x.created_at}
            for x in db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()]

@router.get("/notifications")
def my_notifications(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    return [{"id":x.id,"event":x.event,"subject":x.subject,"message":x.message,
             "status":x.status,"created_at":x.created_at}
            for x in db.scalars(select(Outbox).where(Outbox.employee_id==user.id)
                                .order_by(Outbox.id.desc()).limit(100)).all()]

@router.get("/notification-preferences")
def my_preferences(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    r=db.scalar(select(NotifyPreference).where(NotifyPreference.employee_id==user.id))
    return {c:getattr(r,c) if r else c=="email" for c in ("email","sms","push","whatsapp")}

@router.put("/notification-preferences")
def set_my_preferences(body:PreferencesIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.scalar(select(NotifyPreference).where(NotifyPreference.employee_id==user.id))
    if not row:row=NotifyPreference(employee_id=user.id);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    audit(db,user.id,"notification_preferences_updated",f"employee:{user.id}")
    db.commit();return body.model_dump()

@router.get("/notification-rules")
def rules(user:Employee=Depends(hr),db:Session=Depends(db_session)):
    return [{k:getattr(r,k) for k in ("id","event","email","sms","push","whatsapp","enabled")}
            for r in db.scalars(select(NotifyRule)).all()]

@router.put("/notification-rules")
def save_rule(body:RuleIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=db.scalar(select(NotifyRule).where(NotifyRule.event==body.event))
    if not row:row=NotifyRule(event=body.event);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    audit(db,user.id,"notification_rule_changed",body.event)
    db.commit();return body.model_dump()

@router.post("/notifications/queue")
def manual_notification(body:NotifyIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    count=enqueue(db,body.event,body.employee_id,body.subject,body.message,body.reference)
    audit(db,user.id,"notification_queued",f"{body.event}:{body.employee_id}")
    db.commit()
    return {"queued":count,"note":"Queueing is not proof of external delivery."}

@router.post("/notifications/scan")
def scan_reminders(user:Employee=Depends(hr),db:Session=Depends(db_session)):
    today=date.today()
    birthdays=db.scalars(select(EmployeeCore,Employee).join(
        Employee,Employee.id==EmployeeCore.employee_id).where(
        Employee.status=="active",EmployeeCore.date_of_birth.is_not(None))).all()
    n=0
    for core,employee in birthdays:
        if (core.date_of_birth.month,core.date_of_birth.day)==(today.month,today.day):
            n+=enqueue(db,"birthday",employee.id,"Happy birthday!",
                       f"Wishing you a wonderful birthday, {employee.name}!",
                       today.isoformat())
    docs=db.execute(select(DocumentMetadata,Document).join(
        Document,Document.id==DocumentMetadata.document_id).where(
        DocumentMetadata.expiry_date>=today,
        DocumentMetadata.expiry_date<=today+timedelta(days=30))).all()
    for meta,document in docs:
        n+=enqueue(db,"document_expiry",document.employee_id,"Document renewal reminder",
                    f"Your document {document.name} expires on {meta.expiry_date}.",
                    f"{document.id}:{meta.expiry_date}")
    audit(db,user.id,"notification_scan",today.isoformat(),f"queued={n}")
    db.commit()
    return {"queued":n,"note":"Run using your monitored scheduler daily."}

@router.post("/notifications/deliver-email")
def deliver_email(limit:int=25,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if not 1<=limit<=100:raise HTTPException(422)
    host=os.getenv("SMTP_HOST","")
    port=int(os.getenv("SMTP_PORT","587"))
    sender=os.getenv("SMTP_FROM","")
    username=os.getenv("SMTP_USERNAME","")
    password=os.getenv("SMTP_PASSWORD","")
    if not host or not sender:raise HTTPException(503,"SMTP provider is not configured")
    queued=db.scalars(select(Outbox).where(Outbox.channel=="email",Outbox.status=="queued")
                     .order_by(Outbox.id).limit(limit).with_for_update(skip_locked=True)).all()
    sent=0
    # SMTP delivery is not transactional; mark attempts and retry with provider-side idempotency.
    for x in queued:
        recipient=db.get(Employee,x.employee_id)
        if not recipient or recipient.status!="active":x.status="skipped";continue
        msg=EmailMessage()
        msg["From"]=sender;msg["To"]=recipient.email
        msg["Subject"]=x.subject;msg.set_content(x.message)
        try:
            with smtplib.SMTP(host,port,timeout=8) as server:
                server.starttls(context=ssl.create_default_context())
                if username and password:server.login(username,password)
                server.send_message(msg)
            x.status="sent";x.sent_at=now();sent+=1
        except Exception as exc:
            x.status="failed";x.error=str(exc)[:240]
    audit(db,user.id,"email_notifications_processed","outbox",f"sent={sent},attempted={len(queued)}")
    db.commit()
    return {"sent":sent,"attempted":len(queued),"note":"SMS, WhatsApp and push adapters are not configured."}

@router.get("/integrations")
def integrations(user:Employee=Depends(hr)):
    return {"biometric":{"configured":bool(os.getenv("HRMS_BIOMETRIC_SHARED_TOKEN")),
                         "mode":"signed event staging; vendor mapping required"},
            "email":{"configured":bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")),
                     "mode":"SMTP outbound"},
            "accounting":{"mode":"approved payroll CSV export; no accounting-platform push"},
            "sms":{"configured":False},"whatsapp":{"configured":False},
            "push":{"configured":False},"sso":{"configured":False}}

@router.get("/accounting/payroll.csv")
def payroll_csv(run_id:int,user:Employee=Depends(finance),db:Session=Depends(db_session)):
    run=db.get(PayrollRun,run_id)
    if not run or run.status!="approved":raise HTTPException(404,"Approved payroll run required")
    output=io.StringIO();writer=csv.writer(output)
    writer.writerow(["Employee ID","Employee name","Pay period","Gross INR","LOP INR","PF INR",
                     "ESI INR","PT INR","TDS INR","Other INR","Net INR"])
    rows=db.scalars(select(PayrollLine).where(PayrollLine.run_id==run_id)).all()
    def safe(v):
        txt=str(v)
        return "'"+txt if txt.startswith(("=","+","-","@")) else txt
    for row in rows:
        person=db.get(Employee,row.employee_id)
        writer.writerow([row.employee_id,safe(person.name),f"{run.year}-{run.month:02d}",row.gross,
                         row.lop_deduction,row.pf,row.esi,row.pt,row.tds,row.other_deductions,row.net])
    audit(db,user.id,"accounting_csv_exported",f"payroll_run:{run_id}")
    db.commit()
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
             headers={"Content-Disposition":f'attachment; filename="payroll-{run.year}-{run.month:02d}.csv"',
                      "Cache-Control":"private, no-store"})
