"""People operations: offers, onboarding, policy acknowledgments, tickets and exits (39–42)."""
from __future__ import annotations
import io
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean,Date,DateTime,ForeignKey,Integer,Numeric,String,Text,UniqueConstraint,select,func
from sqlalchemy.orm import Mapped,Session,mapped_column
from .main import Base,Employee,current_user,db_session
from .bonus_policy import CompanyPolicyRecord

router=APIRouter(prefix="/people",tags=["People operations"])
HR=("super_admin","admin","hr")
FIN=HR+("accountant",)
def now():return datetime.now(timezone.utc)
def hr(user:Employee=Depends(current_user)):
    if user.role not in HR:raise HTTPException(403,"HR access required")
    return user
def finance(user:Employee=Depends(current_user)):
    if user.role not in FIN:raise HTTPException(403,"Finance/HR access required")
    return user

class OfferTemplate(Base):
    __tablename__="offer_templates"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    body:Mapped[str]=mapped_column(Text)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Offer(Base):
    __tablename__="offer_letters"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    template_id:Mapped[int]=mapped_column(ForeignKey("offer_templates.id"))
    title:Mapped[str]=mapped_column(String(140))
    salary_inr:Mapped[Decimal]=mapped_column(Numeric(13,2))
    start_date:Mapped[date]=mapped_column(Date)
    rendered_body:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(25),default="issued")
    signed_name:Mapped[str]=mapped_column(String(120),default="")
    signed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    signed_ip:Mapped[str]=mapped_column(String(64),default="")
    issued_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    issued_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class OnboardTask(Base):
    __tablename__="onboard_tasks"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    category:Mapped[str]=mapped_column(String(35))
    title:Mapped[str]=mapped_column(String(180))
    assigned_to:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    due_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    status:Mapped[str]=mapped_column(String(20),default="pending")
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    note:Mapped[str]=mapped_column(Text,default="")

class AssetAllocation(Base):
    __tablename__="asset_allocations"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    asset_name:Mapped[str]=mapped_column(String(120))
    serial_number:Mapped[str]=mapped_column(String(120),unique=True)
    allocated_at:Mapped[date]=mapped_column(Date,default=date.today)
    returned_at:Mapped[date|None]=mapped_column(Date,nullable=True)

class Announcement(Base):
    __tablename__="people_announcements"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(160))
    body:Mapped[str]=mapped_column(Text)
    published:Mapped[bool]=mapped_column(Boolean,default=True)
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PolicyAcknowledgement(Base):
    __tablename__="people_policy_acknowledgements"
    id:Mapped[int]=mapped_column(primary_key=True)
    policy_id:Mapped[int]=mapped_column(ForeignKey("company_policy_records.id"))
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    acknowledged_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("policy_id","employee_id",name="uq_policy_employee_ack"),)

class HelpTicket(Base):
    __tablename__="helpdesk_tickets"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    subject:Mapped[str]=mapped_column(String(150))
    category:Mapped[str]=mapped_column(String(35))
    description:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(25),default="open")
    assigned_to:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    closed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class HelpMessage(Base):
    __tablename__="helpdesk_messages"
    id:Mapped[int]=mapped_column(primary_key=True)
    ticket_id:Mapped[int]=mapped_column(ForeignKey("helpdesk_tickets.id"),index=True)
    author_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    body:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExitRequest(Base):
    __tablename__="people_exits"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    requested_last_day:Mapped[date]=mapped_column(Date)
    approved_last_day:Mapped[date|None]=mapped_column(Date,nullable=True)
    notice_days:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(25),default="pending")
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExitClearance(Base):
    __tablename__="people_exit_clearances"
    id:Mapped[int]=mapped_column(primary_key=True)
    exit_id:Mapped[int]=mapped_column(ForeignKey("people_exits.id"),index=True)
    department:Mapped[str]=mapped_column(String(80))
    status:Mapped[str]=mapped_column(String(20),default="pending")
    note:Mapped[str]=mapped_column(Text,default="")
    approved_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    __table_args__=(UniqueConstraint("exit_id","department",name="uq_exit_clearance_department"),)

class FinalSettlement(Base):
    __tablename__="people_final_settlements"
    id:Mapped[int]=mapped_column(primary_key=True)
    exit_id:Mapped[int]=mapped_column(ForeignKey("people_exits.id"),unique=True)
    unpaid_salary:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    leave_encashment:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    gratuity:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    recovery:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    net:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    status:Mapped[str]=mapped_column(String(25),default="draft")
    approved_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)

class TemplateIn(BaseModel):
    name:str=Field(min_length=3,max_length=120)
    body:str=Field(min_length=50,max_length=15000)
class OfferIn(BaseModel):
    employee_id:int
    template_id:int
    title:str=Field(min_length=2,max_length=140)
    salary_inr:Decimal=Field(gt=0,le=100000000)
    start_date:date
class AcceptIn(BaseModel):
    signed_name:str=Field(min_length=3,max_length=120)
    consent:bool
class TaskIn(BaseModel):
    employee_id:int
    category:Literal["documents","assets","induction","access","other"]
    title:str=Field(min_length=3,max_length=180)
    assigned_to:int|None=None
    due_date:date|None=None
class AssetIn(BaseModel):
    employee_id:int
    asset_name:str=Field(min_length=3,max_length=120)
    serial_number:str=Field(min_length=3,max_length=120)
class AnnouncementIn(BaseModel):
    title:str=Field(min_length=3,max_length=160)
    body:str=Field(min_length=10,max_length=10000)
    published:bool=True
class TicketIn(BaseModel):
    subject:str=Field(min_length=4,max_length=150)
    category:Literal["payroll","leave","attendance","it","documents","other"]
    description:str=Field(min_length=10,max_length=5000)
class HelpMessageIn(BaseModel):
    body:str=Field(min_length=2,max_length=3000)
class ExitIn(BaseModel):
    requested_last_day:date
    reason:str=Field(min_length=10,max_length=3000)
class ExitReviewIn(BaseModel):
    approved:bool
    notice_days:int=Field(default=30,ge=0,le=365)
    approved_last_day:date|None=None
class ClearanceIn(BaseModel):
    department:Literal["it","finance","hr","assets","manager"]
    approved:bool
    note:str=Field(default="",max_length=1000)
class SettlementIn(BaseModel):
    unpaid_salary:Decimal=Field(default=0,ge=0,le=100000000)
    leave_encashment:Decimal=Field(default=0,ge=0,le=100000000)
    gratuity:Decimal=Field(default=0,ge=0,le=100000000)
    recovery:Decimal=Field(default=0,ge=0,le=100000000)

def offers_view(o:Offer):
    return {k:getattr(o,k) for k in ("id","employee_id","title","salary_inr","start_date","status","issued_at","signed_at","signed_name")}

@router.post("/offer-templates",status_code=201)
def create_template(body:TemplateIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if db.scalar(select(OfferTemplate.id).where(OfferTemplate.name==body.name)):raise HTTPException(409,"Template already exists.")
    obj=OfferTemplate(**body.model_dump());db.add(obj);db.commit();db.refresh(obj)
    return {"id":obj.id,"name":obj.name}

@router.get("/offer-templates")
def templates(user:Employee=Depends(hr),db:Session=Depends(db_session)):
    return [{"id":o.id,"name":o.name,"body":o.body,"active":o.active}
        for o in db.scalars(select(OfferTemplate).order_by(OfferTemplate.name)).all()]

@router.post("/offers",status_code=201)
def issue_offer(body:OfferIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    emp=db.get(Employee,body.employee_id)
    tmpl=db.get(OfferTemplate,body.template_id)
    if not emp or not tmpl or not tmpl.active:raise HTTPException(422,"Select an employee and active template")
    # Safe substitution with an allowlist, no arbitrary template expressions.
    substitutions={"employee_name":emp.name,"job_title":body.title,"monthly_salary_inr":f"{body.salary_inr:,.2f}",
                    "start_date":body.start_date.isoformat(),"company_name":"JellyGit"}
    from string import Template
    try:body_text=Template(tmpl.body).substitute(substitutions)
    except (KeyError,ValueError):raise HTTPException(422,"Template contains unsupported placeholders.")
    obj=Offer(employee_id=emp.id,template_id=tmpl.id,title=body.title,salary_inr=body.salary_inr,
              start_date=body.start_date,rendered_body=body_text,issued_by=user.id)
    db.add(obj);db.commit();db.refresh(obj)
    return offers_view(obj)

@router.get("/offers")
def list_offers(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in HR:raise HTTPException(403)
    q=select(Offer).order_by(Offer.id.desc())
    if scope=="mine":q=q.where(Offer.employee_id==user.id)
    return [offers_view(x) for x in db.scalars(q).all()]

def offer_auth(db:Session,offer_id:int,user:Employee):
    row=db.get(Offer,offer_id)
    if not row:raise HTTPException(404)
    if row.employee_id!=user.id and user.role not in HR:raise HTTPException(403)
    return row

@router.post("/offers/{offer_id}/accept")
def accept_offer(offer_id:int,body:AcceptIn,request:Request,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=offer_auth(db,offer_id,user)
    if row.employee_id!=user.id:raise HTTPException(403,"Only the addressee may sign.")
    if row.status!="issued":raise HTTPException(409,"Offer is no longer awaiting acceptance.")
    if not body.consent:raise HTTPException(422,"Affirmative consent is required to sign.")
    if " ".join(body.signed_name.lower().split())!=" ".join(user.name.lower().split()):
        raise HTTPException(422,"Typed legal name must match your profile.")
    row.status="accepted";row.signed_name=body.signed_name;row.signed_at=now()
    row.signed_ip=request.client.host[:64] if request.client else ""
    db.commit()
    return {"status":"accepted","signed_at":row.signed_at,
            "signature_type":"authenticated typed-name acknowledgement; not third-party qualified e-signature"}

@router.get("/offers/{offer_id}/pdf")
def offer_pdf(offer_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=offer_auth(db,offer_id,user)
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape
    buffer=io.BytesIO()
    pdf=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=45,rightMargin=45)
    styles=getSampleStyleSheet()
    content=[Paragraph("JellyGit - Offer Letter",styles["Heading1"]),Spacer(1,20)]
    for paragraph in row.rendered_body.splitlines():
        if paragraph.strip():content.append(Paragraph(escape(paragraph),styles["Normal"]));content.append(Spacer(1,10))
    if row.status=="accepted":
        content.append(Paragraph("Accepted by: "+escape(row.signed_name),styles["Normal"]))
        content.append(Paragraph("Accepted (UTC): "+str(row.signed_at),styles["Normal"]))
    pdf.build(content);buffer.seek(0)
    return StreamingResponse(buffer,media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="offer-{row.id}.pdf"',
                 "Cache-Control":"private, no-store"})

@router.post("/onboarding/tasks",status_code=201)
def add_task(body:TaskIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Employee not found")
    if body.assigned_to and not db.get(Employee,body.assigned_to):raise HTTPException(422,"Assignee not found")
    row=OnboardTask(**body.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

@router.get("/onboarding/tasks")
def list_tasks(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    who=employee_id or user.id
    if who!=user.id and user.role not in HR:raise HTTPException(403)
    return [{"id":x.id,"employee_id":x.employee_id,"category":x.category,"title":x.title,
             "due_date":x.due_date,"status":x.status,"assigned_to":x.assigned_to}
            for x in db.scalars(select(OnboardTask).where(OnboardTask.employee_id==who)).all()]

@router.post("/onboarding/tasks/{task_id}/complete")
def complete_task(task_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(OnboardTask,task_id)
    if not row:raise HTTPException(404)
    if user.role not in HR and row.assigned_to!=user.id:raise HTTPException(403)
    if row.status!="pending":raise HTTPException(409)
    row.status="completed";row.completed_at=now();db.commit()
    return {"status":row.status}

@router.post("/onboarding/assets",status_code=201)
def allocate_asset(body:AssetIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Employee not found")
    if db.scalar(select(AssetAllocation.id).where(AssetAllocation.serial_number==body.serial_number)):
        raise HTTPException(409,"Asset serial number already allocated.")
    row=AssetAllocation(**body.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"allocated_at":row.allocated_at}

@router.get("/onboarding/assets")
def list_assets(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    who=employee_id or user.id
    if who!=user.id and user.role not in HR:raise HTTPException(403)
    return [{"id":x.id,"asset_name":x.asset_name,"serial_number":x.serial_number,
             "allocated_at":x.allocated_at,"returned_at":x.returned_at}
            for x in db.scalars(select(AssetAllocation).where(AssetAllocation.employee_id==who)).all()]

@router.post("/onboarding/assets/{asset_id}/return")
def return_asset(asset_id:int,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=db.get(AssetAllocation,asset_id)
    if not row:raise HTTPException(404)
    if row.returned_at:raise HTTPException(409,"Already returned.")
    row.returned_at=date.today();db.commit()
    return {"returned_at":row.returned_at}

@router.post("/announcements",status_code=201)
def publish(body:AnnouncementIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=Announcement(**body.model_dump(),created_by=user.id);db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"title":row.title}

@router.get("/announcements")
def announcements(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(Announcement).order_by(Announcement.id.desc())
    if user.role not in HR:q=q.where(Announcement.published.is_(True))
    return [{"id":x.id,"title":x.title,"body":x.body,"created_at":x.created_at}
        for x in db.scalars(q.limit(100)).all()]

@router.get("/policy-acknowledgements")
def policy_acknowledgements(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    p=db.scalars(select(CompanyPolicyRecord).where(CompanyPolicyRecord.active.is_(True)).order_by(CompanyPolicyRecord.id.desc())).all()
    ids={a.policy_id for a in db.scalars(select(PolicyAcknowledgement).where(
        PolicyAcknowledgement.employee_id==user.id)).all()}
    return [{"id":x.id,"title":x.title,"category":x.category,"effective_date":x.effective_date,
             "acknowledged":x.id in ids} for x in p]

@router.post("/policy-acknowledgements/{policy_id}",status_code=201)
def acknowledge_policy(policy_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    p=db.get(CompanyPolicyRecord,policy_id)
    if not p or not p.active:raise HTTPException(404)
    if db.scalar(select(PolicyAcknowledgement.id).where(PolicyAcknowledgement.policy_id==policy_id,
                                                      PolicyAcknowledgement.employee_id==user.id)):
        return {"acknowledged":True,"already":True}
    db.add(PolicyAcknowledgement(employee_id=user.id,policy_id=policy_id));db.commit()
    return {"acknowledged":True}

@router.post("/helpdesk",status_code=201)
def open_ticket(body:TicketIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=HelpTicket(**body.model_dump(),employee_id=user.id);db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

@router.get("/helpdesk")
def tickets(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in HR:raise HTTPException(403)
    q=select(HelpTicket).order_by(HelpTicket.id.desc())
    if scope=="mine":q=q.where(HelpTicket.employee_id==user.id)
    return [{"id":x.id,"employee_id":x.employee_id,"subject":x.subject,"category":x.category,
             "description":x.description,"status":x.status,"created_at":x.created_at}
        for x in db.scalars(q).all()]

@router.post("/helpdesk/{ticket_id}/messages",status_code=201)
def ticket_message(ticket_id:int,body:HelpMessageIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    t=db.get(HelpTicket,ticket_id)
    if not t:raise HTTPException(404)
    if user.role not in HR and t.employee_id!=user.id:raise HTTPException(403)
    if t.status=="closed":raise HTTPException(409,"Closed ticket cannot receive messages")
    row=HelpMessage(ticket_id=t.id,author_id=user.id,body=body.body)
    db.add(row);db.commit();return {"sent":True}

@router.get("/helpdesk/{ticket_id}/messages")
def ticket_messages(ticket_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    t=db.get(HelpTicket,ticket_id)
    if not t:raise HTTPException(404)
    if user.role not in HR and t.employee_id!=user.id:raise HTTPException(403)
    return [{"author_id":x.author_id,"body":x.body,"created_at":x.created_at}
        for x in db.scalars(select(HelpMessage).where(HelpMessage.ticket_id==ticket_id).order_by(HelpMessage.id)).all()]

@router.post("/helpdesk/{ticket_id}/close")
def close_ticket(ticket_id:int,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    t=db.get(HelpTicket,ticket_id)
    if not t:raise HTTPException(404)
    t.status="closed";t.closed_at=now();db.commit()
    return {"status":t.status}

@router.post("/exits",status_code=201)
def resign(body:ExitIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if body.requested_last_day<date.today():raise HTTPException(422,"Last working day cannot be in the past.")
    existing=db.scalar(select(ExitRequest).where(ExitRequest.employee_id==user.id,
                       ExitRequest.status.in_(("pending","approved"))))
    if existing:raise HTTPException(409,"Active resignation request already exists.")
    row=ExitRequest(employee_id=user.id,**body.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

@router.get("/exits")
def list_exits(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in FIN:raise HTTPException(403)
    q=select(ExitRequest).order_by(ExitRequest.id.desc())
    if scope=="mine":q=q.where(ExitRequest.employee_id==user.id)
    return [{"id":x.id,"employee_id":x.employee_id,"requested_last_day":x.requested_last_day,
             "approved_last_day":x.approved_last_day,"notice_days":x.notice_days,"reason":x.reason,
             "status":x.status} for x in db.scalars(q).all()]

@router.post("/exits/{exit_id}/review")
def review_exit(exit_id:int,body:ExitReviewIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=db.execute(select(ExitRequest).where(ExitRequest.id==exit_id).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404)
    if row.employee_id==user.id:raise HTTPException(403,"Self approval not allowed")
    if row.status!="pending":raise HTTPException(409)
    if body.approved:
        approved_day=body.approved_last_day or max(row.requested_last_day,date.today()+timedelta(days=body.notice_days))
        if approved_day<date.today():raise HTTPException(422)
        row.status="approved";row.approved_last_day=approved_day;row.notice_days=body.notice_days
        for department in ("it","finance","hr","assets","manager"):
            db.add(ExitClearance(exit_id=row.id,department=department))
    else:row.status="rejected"
    row.reviewed_by=user.id;row.reviewed_at=now()
    db.commit()
    return {"status":row.status,"approved_last_day":row.approved_last_day}

@router.get("/exits/{exit_id}/clearances")
def list_clearances(exit_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(ExitRequest,exit_id)
    if not row:raise HTTPException(404)
    if row.employee_id!=user.id and user.role not in FIN:raise HTTPException(403)
    return [{"id":x.id,"department":x.department,"status":x.status,"note":x.note}
       for x in db.scalars(select(ExitClearance).where(ExitClearance.exit_id==exit_id)).all()]

@router.post("/exits/{exit_id}/clearances")
def review_clearance(exit_id:int,body:ClearanceIn,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=db.scalar(select(ExitClearance).where(ExitClearance.exit_id==exit_id,
                                             ExitClearance.department==body.department))
    if not row:raise HTTPException(404)
    if row.status!="pending":raise HTTPException(409)
    row.status="approved" if body.approved else "blocked";row.note=body.note;row.approved_by=user.id
    db.commit();return {"status":row.status}

@router.put("/exits/{exit_id}/settlement")
def draft_settlement(exit_id:int,body:SettlementIn,user:Employee=Depends(finance),db:Session=Depends(db_session)):
    exit_row=db.get(ExitRequest,exit_id)
    if not exit_row or exit_row.status!="approved":raise HTTPException(422,"Approve resignation before settlement")
    row=db.scalar(select(FinalSettlement).where(FinalSettlement.exit_id==exit_id))
    if row and row.status!="draft":raise HTTPException(409,"Settlement already finalized")
    if not row:row=FinalSettlement(exit_id=exit_id);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    row.net=body.unpaid_salary+body.leave_encashment+body.gratuity-body.recovery
    db.commit();return {"status":row.status,"net":row.net}

@router.post("/exits/{exit_id}/settlement/approve")
def approve_settlement(exit_id:int,user:Employee=Depends(hr),db:Session=Depends(db_session)):
    row=db.scalar(select(FinalSettlement).where(FinalSettlement.exit_id==exit_id))
    if not row:raise HTTPException(404)
    if row.status!="draft":raise HTTPException(409)
    exit_row=db.get(ExitRequest,exit_id)
    if exit_row.employee_id==user.id:raise HTTPException(403)
    clearance=db.scalars(select(ExitClearance).where(ExitClearance.exit_id==exit_id)).all()
    if not clearance or any(x.status!="approved" for x in clearance):
        raise HTTPException(422,"All departmental clearances are required.")
    row.status="approved";row.approved_by=user.id
    db.commit();return {"status":row.status,"net":row.net}
