"""Payroll and expenses (31–35). Versioned runs, financial segregation and no automatic disbursement."""
from __future__ import annotations
import io
import os
import uuid
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, Attendance, Bonus, UPLOAD_DIR, current_user, db_session
from .leave_management import LeaveRequest

router=APIRouter(prefix="/payroll",tags=["Payroll & Expenses"])
HR=("super_admin","admin","hr")
FINANCE=HR+("accountant",)
D=Decimal
ZERO=D("0.00")
Q=lambda amount:D(amount).quantize(D(".01"),rounding=ROUND_HALF_UP)
def now():return datetime.now(timezone.utc)
def require_finance(user:Employee=Depends(current_user)):
    if user.role not in FINANCE:raise HTTPException(403,"Finance/HR access required")
    return user
def require_hr(user:Employee=Depends(current_user)):
    if user.role not in HR:raise HTTPException(403,"HR access required")
    return user
def record(db,actor,target,action,reason):
    db.add(PayrollAudit(actor_id=actor,employee_id=target,action=action,reason=reason,at=now()))

class SalaryStructure(Base):
    __tablename__="salary_structures"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    effective_from:Mapped[date]=mapped_column(Date,index=True)
    basic:Mapped[Decimal]=mapped_column(Numeric(12,2))
    hra:Mapped[Decimal]=mapped_column(Numeric(12,2))
    allowances:Mapped[Decimal]=mapped_column(Numeric(12,2),default=ZERO)
    other_deductions:Mapped[Decimal]=mapped_column(Numeric(12,2),default=ZERO)
    monthly_tds:Mapped[Decimal]=mapped_column(Numeric(12,2),default=ZERO)
    monthly_pt:Mapped[Decimal]=mapped_column(Numeric(12,2),default=ZERO)
    pf_enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    esi_enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    state:Mapped[str]=mapped_column(String(50),default="MP")
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    __table_args__=(UniqueConstraint("employee_id","effective_from",name="uq_salary_structure_effective"),)

class StatutoryConfig(Base):
    __tablename__="statutory_config"
    id:Mapped[int]=mapped_column(primary_key=True)
    effective_from:Mapped[date]=mapped_column(Date,unique=True)
    pf_rate:Mapped[Decimal]=mapped_column(Numeric(6,4),default=D("0.12"))
    pf_wage_ceiling:Mapped[Decimal]=mapped_column(Numeric(12,2),default=D("25000"))
    esi_employee_rate:Mapped[Decimal]=mapped_column(Numeric(6,4),default=D("0.0075"))
    esi_employer_rate:Mapped[Decimal]=mapped_column(Numeric(6,4),default=D("0.0325"))
    esi_eligibility_ceiling:Mapped[Decimal]=mapped_column(Numeric(12,2),default=D("21000"))
    verified:Mapped[bool]=mapped_column(Boolean,default=False)
    note:Mapped[str]=mapped_column(Text,default="")

class PayrollRun(Base):
    __tablename__="payroll_runs"
    id:Mapped[int]=mapped_column(primary_key=True)
    year:Mapped[int]=mapped_column(Integer)
    month:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(20),default="draft")
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    note:Mapped[str]=mapped_column(Text,default="")
    __table_args__=(UniqueConstraint("year","month",name="uq_payroll_period"),)

class PayrollLine(Base):
    __tablename__="payroll_lines"
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("payroll_runs.id"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    scheduled_days:Mapped[int]=mapped_column(Integer)
    lop_days:Mapped[Decimal]=mapped_column(Numeric(7,2))
    present_days:Mapped[int]=mapped_column(Integer)
    basic:Mapped[Decimal]=mapped_column(Numeric(12,2))
    hra:Mapped[Decimal]=mapped_column(Numeric(12,2))
    allowances:Mapped[Decimal]=mapped_column(Numeric(12,2))
    gross:Mapped[Decimal]=mapped_column(Numeric(12,2))
    lop_deduction:Mapped[Decimal]=mapped_column(Numeric(12,2))
    pf:Mapped[Decimal]=mapped_column(Numeric(12,2))
    esi:Mapped[Decimal]=mapped_column(Numeric(12,2))
    pt:Mapped[Decimal]=mapped_column(Numeric(12,2))
    tds:Mapped[Decimal]=mapped_column(Numeric(12,2))
    other_deductions:Mapped[Decimal]=mapped_column(Numeric(12,2))
    net:Mapped[Decimal]=mapped_column(Numeric(12,2))
    review_note:Mapped[str]=mapped_column(Text,default="")
    __table_args__=(UniqueConstraint("run_id","employee_id",name="uq_payroll_line_employee"),)

class PayrollAudit(Base):
    __tablename__="payroll_audits"
    id:Mapped[int]=mapped_column(primary_key=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    employee_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    action:Mapped[str]=mapped_column(String(60))
    reason:Mapped[str]=mapped_column(Text,default="")
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExpenseClaim(Base):
    __tablename__="expense_claims"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    category:Mapped[str]=mapped_column(String(60))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    expense_date:Mapped[date]=mapped_column(Date)
    description:Mapped[str]=mapped_column(String(500))
    status:Mapped[str]=mapped_column(String(20),default="pending")
    receipt_key:Mapped[str]=mapped_column(String(90),default="")
    receipt_type:Mapped[str]=mapped_column(String(50),default="")
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    review_note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class StructureIn(BaseModel):
    employee_id:int
    effective_from:date
    basic:Decimal=Field(ge=0,le=100000000)
    hra:Decimal=Field(ge=0,le=100000000)
    allowances:Decimal=Field(default=ZERO,ge=0,le=100000000)
    other_deductions:Decimal=Field(default=ZERO,ge=0,le=100000000)
    monthly_tds:Decimal=Field(default=ZERO,ge=0,le=100000000)
    monthly_pt:Decimal=Field(default=ZERO,ge=0,le=100000)
    pf_enabled:bool=True
    esi_enabled:bool=False
    state:str=Field(default="MP",min_length=2,max_length=50)

class StatutoryIn(BaseModel):
    effective_from:date
    pf_rate:Decimal=Field(default=D(".12"),ge=0,le=.25)
    pf_wage_ceiling:Decimal=Field(default=D("25000"),ge=0)
    esi_employee_rate:Decimal=Field(default=D(".0075"),ge=0,le=.15)
    esi_employer_rate:Decimal=Field(default=D(".0325"),ge=0,le=.15)
    esi_eligibility_ceiling:Decimal=Field(default=D("21000"),ge=0)
    verified:bool=False
    note:str=Field(default="",max_length=2000)

class CreateRunIn(BaseModel):
    year:int=Field(ge=2020,le=2100)
    month:int=Field(ge=1,le=12)
    note:str=Field(default="",max_length=1000)

class ApproveIn(BaseModel):
    reason:str=Field(min_length=10,max_length=1000)

class ClaimIn(BaseModel):
    category:Literal["travel","meals","internet","equipment","medical","other"]
    amount:Decimal=Field(gt=0,le=1000000)
    expense_date:date
    description:str=Field(min_length=10,max_length=500)

class ReviewClaimIn(BaseModel):
    approve:bool
    note:str=Field(min_length=5,max_length=1000)

def structure_view(s:SalaryStructure):
    return {key:getattr(s,key) for key in ("id","employee_id","effective_from","basic","hra","allowances",
            "other_deductions","monthly_tds","monthly_pt","pf_enabled","esi_enabled","state")}

@router.post("/structures",status_code=201)
def set_structure(body:StructureIn,user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    employee=db.get(Employee,body.employee_id)
    if not employee or employee.status not in ("active","inactive"):
        raise HTTPException(422,"Employee not found")
    if Q(body.basic+body.hra+body.allowances)<=0:raise HTTPException(422,"Total salary must be positive.")
    current=db.scalar(select(SalaryStructure).where(SalaryStructure.employee_id==body.employee_id,
                                 SalaryStructure.effective_from==body.effective_from))
    if current:raise HTTPException(409,"Salary revision with this effective date already exists.")
    row=SalaryStructure(**body.model_dump(),created_by=user.id)
    db.add(row);record(db,user.id,body.employee_id,"salary_structure_created",str(body.effective_from))
    db.commit();db.refresh(row)
    return structure_view(row)

@router.get("/structures")
def list_structures(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    employee_id=employee_id or user.id
    if employee_id!=user.id and user.role not in FINANCE:raise HTTPException(403,"Cannot access another employee's salary")
    rows=db.scalars(select(SalaryStructure).where(SalaryStructure.employee_id==employee_id)
                    .order_by(SalaryStructure.effective_from.desc())).all()
    return [structure_view(x) for x in rows]

@router.put("/statutory")
def configure_statutory(body:StatutoryIn,user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    p=db.scalar(select(StatutoryConfig).where(StatutoryConfig.effective_from==body.effective_from))
    if not p:p=StatutoryConfig();db.add(p)
    for k,v in body.model_dump().items():setattr(p,k,v)
    record(db,user.id,None,"statutory_config_saved",str(body.effective_from))
    db.commit()
    return {"effective_from":p.effective_from,"verified":p.verified}

@router.get("/statutory")
def view_statutory(user:Employee=Depends(require_finance),db:Session=Depends(db_session)):
    rows=db.scalars(select(StatutoryConfig).order_by(StatutoryConfig.effective_from.desc())).all()
    return [{k:getattr(x,k) for k in ("effective_from","pf_rate","pf_wage_ceiling","esi_employee_rate",
                 "esi_employer_rate","esi_eligibility_ceiling","verified","note")} for x in rows]

def effective_statutory(db:Session,when:date):
    return db.scalar(select(StatutoryConfig).where(StatutoryConfig.effective_from<=when)
                     .order_by(StatutoryConfig.effective_from.desc()))

def prorated_days(employee:Employee,first:date,last:date):
    return max(0,(last-max(first,employee.joining_date)).days+1) if employee.joining_date<=last else 0

def build_run(db:Session,run:PayrollRun):
    first=date(run.year,run.month,1)
    last=date(run.year,run.month,monthrange(run.year,run.month)[1])
    statutory=effective_statutory(db,last)
    if not statutory or not statutory.verified:
        raise HTTPException(422,"A verified, effective-dated statutory configuration is required before payroll.")
    employees=db.scalars(select(Employee).where(Employee.status=="active")).all()
    all_lines=[]
    for emp in employees:
        structure=db.scalar(select(SalaryStructure).where(
            SalaryStructure.employee_id==emp.id,SalaryStructure.effective_from<=last
        ).order_by(SalaryStructure.effective_from.desc()))
        if not structure:continue
        active_days=prorated_days(emp,first,last)
        if not active_days:continue
        full_days=(last-first).days+1
        lop_rows=db.scalars(select(LeaveRequest).where(
            LeaveRequest.employee_id==emp.id,LeaveRequest.leave_type=="loss_of_pay",
            LeaveRequest.status=="approved",LeaveRequest.end_date>=first,LeaveRequest.start_date<=last)).all()
        # Partial-day LOP is counted only for a single date. Overlapping LOP requests
        # are blockers, never silently double deducted in salary.
        covered=set()
        lop=ZERO
        issues=[]
        for request in lop_rows:
            start=max(first,request.start_date,emp.joining_date)
            end=min(last,request.end_date)
            if start>end:continue
            days={start.fromordinal(o) for o in range(start.toordinal(),end.toordinal()+1)}
            if days & covered:issues.append("Overlapping approved loss-of-pay requests")
            covered|=days
            lop+=Q(len(days)* (D(".5") if request.day_part=="half" and start==end else D("1")))
        lop=min(lop,D(active_days))
        factor=D(active_days)/D(full_days)
        basic=Q(structure.basic*factor)
        hra=Q(structure.hra*factor)
        allowances=Q(structure.allowances*factor)
        gross=basic+hra+allowances
        lop_deduction=Q(gross*lop/D(active_days))
        paid_gross=max(ZERO,gross-lop_deduction)
        pf=Q(min(max(ZERO,basic-Q(basic*lop/D(active_days))),statutory.pf_wage_ceiling)*statutory.pf_rate) if structure.pf_enabled else ZERO
        esi=Q(paid_gross*statutory.esi_employee_rate) if structure.esi_enabled and gross<=statutory.esi_eligibility_ceiling else ZERO
        pt=Q(structure.monthly_pt)
        tds=Q(structure.monthly_tds)
        other=Q(structure.other_deductions)
        net=Q(paid_gross-pf-esi-pt-tds-other)
        punches=db.scalars(select(Attendance).where(Attendance.employee_id==emp.id,
                      Attendance.punch_in>=datetime(run.year,run.month,1,tzinfo=timezone.utc),
                      Attendance.punch_in<datetime(run.year+1,1,1,tzinfo=timezone.utc)
                        if run.month==12 else Attendance.punch_in<datetime(run.year,run.month+1,1,tzinfo=timezone.utc))).all()
        present=len({x.punch_in.date() for x in punches})
        if any(p.punch_out is None for p in punches):issues.append("One or more punches remain open")
        if net<0:issues.append("Net salary negative; review statutory/withholding fields")
        if present==0 and active_days>0:issues.append("No attendance sessions; verify WFH/on-duty/leave")
        line=PayrollLine(run_id=run.id,employee_id=emp.id,scheduled_days=active_days,
            lop_days=lop,present_days=present,basic=basic,hra=hra,allowances=allowances,gross=gross,
            lop_deduction=lop_deduction,pf=pf,esi=esi,pt=pt,tds=tds,other_deductions=other,net=net,
            review_note="; ".join(issues))
        all_lines.append(line)
    if not all_lines:raise HTTPException(422,"No active employees have effective salary structures.")
    return all_lines

@router.post("/runs",status_code=201)
def create_run(body:CreateRunIn,user:Employee=Depends(require_finance),db:Session=Depends(db_session)):
    existing=db.scalar(select(PayrollRun).where(PayrollRun.year==body.year,PayrollRun.month==body.month))
    if existing:raise HTTPException(409,"A payroll run already exists for this month.")
    run=PayrollRun(**body.model_dump(),created_by=user.id)
    db.add(run);db.flush()
    lines=build_run(db,run)
    db.add_all(lines)
    record(db,user.id,None,"payroll_draft_created",f"{body.year}-{body.month:02d}")
    db.commit()
    return {"id":run.id,"status":"draft","employees":len(lines)}

def line_view(x:PayrollLine):
    return {key:float(getattr(x,key)) if isinstance(getattr(x,key),Decimal) else getattr(x,key)
        for key in ("id","employee_id","scheduled_days","lop_days","present_days","basic","hra",
                    "allowances","gross","lop_deduction","pf","esi","pt","tds","other_deductions","net","review_note")}

@router.get("/runs")
def list_runs(user:Employee=Depends(require_finance),db:Session=Depends(db_session)):
    return [{"id":r.id,"year":r.year,"month":r.month,"status":r.status,"approved_at":r.approved_at}
        for r in db.scalars(select(PayrollRun).order_by(PayrollRun.id.desc())).all()]

@router.get("/runs/{run_id}")
def run_details(run_id:int,user:Employee=Depends(require_finance),db:Session=Depends(db_session)):
    run=db.get(PayrollRun,run_id)
    if not run:raise HTTPException(404)
    lines=db.scalars(select(PayrollLine).where(PayrollLine.run_id==run_id)).all()
    return {"id":run.id,"year":run.year,"month":run.month,"status":run.status,
            "lines":[line_view(x) for x in lines],
            "has_review_flags":any(bool(x.review_note) for x in lines)}

@router.post("/runs/{run_id}/lines/{line_id}/resolve")
def resolve_payroll_flag(run_id:int,line_id:int,body:ApproveIn,
                         user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    run=db.get(PayrollRun,run_id)
    if not run or run.status!="draft":raise HTTPException(409,"Only draft payroll flags may be reviewed.")
    line=db.get(PayrollLine,line_id)
    if not line or line.run_id!=run_id:raise HTTPException(404,"Payroll line not found")
    if not line.review_note:raise HTTPException(409,"No review flags remain.")
    previous=line.review_note
    line.review_note=""
    record(db,user.id,line.employee_id,"payroll_review_flags_acknowledged",
           f"Flags: {previous[:250]}; HR justification: {body.reason[:500]}")
    db.commit()
    return {"resolved":True,"line_id":line.id}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id:int,body:ApproveIn,user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    run=db.execute(select(PayrollRun).where(PayrollRun.id==run_id).with_for_update()).scalar_one_or_none()
    if not run:raise HTTPException(404)
    if run.status!="draft":raise HTTPException(409,"Payroll already finalized")
    if run.created_by==user.id:raise HTTPException(403,"Creator cannot approve own payroll run.")
    lines=db.scalars(select(PayrollLine).where(PayrollLine.run_id==run_id)).all()
    if any(x.review_note for x in lines):raise HTTPException(422,"Resolve payroll review flags before approval.")
    run.status="approved";run.approved_by=user.id;run.approved_at=now()
    record(db,user.id,None,"payroll_approved",body.reason)
    db.commit()
    return {"status":"approved","approved_at":run.approved_at}

@router.get("/payslips")
def my_payslips(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    who=employee_id or user.id
    if who!=user.id and user.role not in FINANCE:raise HTTPException(403)
    q=select(PayrollLine,PayrollRun).join(PayrollRun,PayrollRun.id==PayrollLine.run_id).where(
        PayrollLine.employee_id==who,PayrollRun.status=="approved").order_by(PayrollRun.year.desc(),PayrollRun.month.desc())
    return [{"run_id":run.id,"year":run.year,"month":run.month,"net":float(line.net)} for line,run in db.execute(q).all()]

@router.get("/payslips/{run_id}/pdf")
def payslip_pdf(run_id:int,employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    who=employee_id or user.id
    if who!=user.id and user.role not in FINANCE:raise HTTPException(403)
    run=db.get(PayrollRun,run_id)
    if not run or run.status!="approved":raise HTTPException(404,"Approved payslip not found")
    line=db.scalar(select(PayrollLine).where(PayrollLine.run_id==run_id,PayrollLine.employee_id==who))
    if not line:raise HTTPException(404)
    emp=db.get(Employee,who)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    buffer=io.BytesIO()
    p=canvas.Canvas(buffer,pagesize=A4)
    p.setTitle(f"JellyGit Payslip {run.year}-{run.month:02d}")
    w,h=A4
    p.setFillColorRGB(.13,.20,.37);p.rect(0,h-120,w,120,fill=1,stroke=0)
    p.setFillColor(colors.white);p.setFont("Helvetica-Bold",20);p.drawString(42,h-53,"JellyGit | Payslip")
    p.setFont("Helvetica",11);p.drawString(42,h-80,f"Salary period: {run.month:02d}/{run.year}")
    p.setFillColor(colors.black);p.setFont("Helvetica-Bold",13);p.drawString(42,h-155,emp.name[:70])
    p.setFont("Helvetica",10);p.drawString(42,h-173,emp.email[:82])
    labels=[("Basic salary",line.basic),("House rent allowance",line.hra),("Other allowances",line.allowances),
            ("Loss of pay",line.lop_deduction),("Provident fund",line.pf),("ESI",line.esi),
            ("Professional tax",line.pt),("Income tax withholding",line.tds),("Other deductions",line.other_deductions),
            ("NET PAY",line.net)]
    y=h-220
    for i,(label,amount) in enumerate(labels):
        if i==len(labels)-1:p.setFont("Helvetica-Bold",13);p.line(42,y+19,w-42,y+19)
        else:p.setFont("Helvetica",11)
        p.drawString(45,y,label);p.drawRightString(w-45,y,f"INR {Q(amount):,.2f}");y-=35
    p.setFont("Helvetica",9);p.setFillColor(colors.grey)
    p.drawString(42,75,"System-generated document. Confidential employee information.")
    p.drawString(42,60,"Payroll calculations require approved statutory policy and company review.")
    p.showPage();p.save();buffer.seek(0)
    return StreamingResponse(buffer,media_type="application/pdf",
      headers={"Content-Disposition":f'attachment; filename="payslip-{run.year}-{run.month:02d}.pdf"',
               "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@router.post("/claims",status_code=201)
def create_claim(body:ClaimIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if body.expense_date>date.today():raise HTTPException(422,"Future expense dates are not permitted.")
    row=ExpenseClaim(employee_id=user.id,**body.model_dump());db.add(row);db.flush()
    record(db,user.id,user.id,"expense_submitted",f"claim {row.id}")
    db.commit();return {"id":row.id,"status":row.status}

@router.get("/claims")
def claims(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in FINANCE:raise HTTPException(403)
    q=select(ExpenseClaim).order_by(ExpenseClaim.id.desc())
    if scope=="mine":q=q.where(ExpenseClaim.employee_id==user.id)
    return [{key:getattr(row,key) for key in ("id","employee_id","category","amount","expense_date",
            "description","status","review_note","receipt_key")}
            for row in db.scalars(q).all()]

def claim_auth(db:Session,claim_id:int,user:Employee)->ExpenseClaim:
    claim=db.get(ExpenseClaim,claim_id)
    if not claim:raise HTTPException(404)
    if claim.employee_id!=user.id and user.role not in FINANCE:raise HTTPException(403)
    return claim

@router.post("/claims/{claim_id}/receipt")
async def upload_receipt(claim_id:int,document:UploadFile=File(...),
                         user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    claim=claim_auth(db,claim_id,user)
    if claim.employee_id!=user.id or claim.status!="pending":
        raise HTTPException(403,"Only the submitter may add a receipt to a pending claim.")
    content=await document.read(5*1024*1024+1)
    if len(content)>5*1024*1024:raise HTTPException(413,"Receipt must be under 5 MB.")
    pdf=content.startswith(b"%PDF-")
    png=content.startswith(bytes.fromhex("89504e470d0a1a0a"))
    jpg=content.startswith(bytes.fromhex("ffd8ff"))
    if not (pdf or png or jpg):raise HTTPException(415,"Receipt must be PDF, PNG or JPEG.")
    ext="pdf" if pdf else "png" if png else "jpg"
    folder=UPLOAD_DIR/"receipts"
    folder.mkdir(parents=True,exist_ok=True)
    key=uuid.uuid4().hex+"."+ext
    path=folder/key
    with path.open("xb") as fh:fh.write(content)
    path.chmod(0o600)
    old=claim.receipt_key
    claim.receipt_key=key;claim.receipt_type=ext
    db.commit()
    if old:(folder/Path(old).name).unlink(missing_ok=True)
    return {"has_receipt":True}

@router.get("/claims/{claim_id}/receipt")
def receipt(claim_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    claim=claim_auth(db,claim_id,user)
    if not claim.receipt_key:raise HTTPException(404)
    path=UPLOAD_DIR/"receipts"/Path(claim.receipt_key).name
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,media_type={"pdf":"application/pdf","png":"image/png","jpg":"image/jpeg"}[claim.receipt_type],
        headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@router.post("/claims/{claim_id}/review")
def review_claim(claim_id:int,body:ReviewClaimIn,user:Employee=Depends(require_finance),
                 db:Session=Depends(db_session)):
    row=db.execute(select(ExpenseClaim).where(ExpenseClaim.id==claim_id).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404)
    if row.employee_id==user.id:raise HTTPException(403,"Self-approval is not allowed.")
    if row.status!="pending":raise HTTPException(409)
    if body.approve and not row.receipt_key:raise HTTPException(422,"Upload a receipt before approval.")
    row.status="approved" if body.approve else "rejected";row.reviewed_by=user.id;row.review_note=body.note
    record(db,user.id,row.employee_id,"expense_"+row.status,body.note)
    db.commit();return {"status":row.status}
