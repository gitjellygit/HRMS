"""Salary structure, controlled monthly payroll, payslip PDF and reimbursable claims.

No tax/slab defaults: HR must configure reviewed organization rules. Payroll is a
draft calculation until approved; never transfers money or files statutory returns.
"""
import io
import os
import json
from types import SimpleNamespace
import calendar
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select, func
from sqlalchemy.orm import Session, Mapped, mapped_column
from .main import Base, Employee, Attendance, Bonus, db_session, current_user, UPLOAD_DIR
from .leave_management import LeaveRequest

router=APIRouter(prefix="/payroll",tags=["Payroll & Expenses"])
HR=("admin","super_admin","hr")
FIN=HR+("accountant",)
MONEY=Decimal("0.01")
def money(v):return Decimal(v).quantize(MONEY,rounding=ROUND_HALF_UP)
def now():return datetime.now(timezone.utc)
def role(user,allow=FIN):
    if user.role not in allow:raise HTTPException(403,"Payroll access restricted.")
    return user
def own_or_fin(user,owner):
    if user.id!=owner and user.role not in FIN:raise HTTPException(403,"Not authorized to view this payroll record.")

class SalaryStructure(Base):
    __tablename__="pay_salary_structures"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    basic:Mapped[Decimal]=mapped_column(Numeric(12,2))
    hra:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    allowances:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    other_deductions:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    effective_from:Mapped[date]=mapped_column(Date)
    reviewed_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class StatutorySettings(Base):
    __tablename__="pay_statutory_settings"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    pf_employee_monthly:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    esi_employee_monthly:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    professional_tax_monthly:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    tds_monthly:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    gratuity_employer_provision:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    effective_from:Mapped[date]=mapped_column(Date)
    reviewed_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))

class PayrollConfigVersion(Base):
    """Immutable salary/statutory history, including effective dates.

    The legacy single-row tables remain projections of the latest submitted
    configuration for API compatibility; calculations use historical versions.
    """
    __tablename__="pay_config_versions"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    kind:Mapped[str]=mapped_column(String(20),index=True)
    effective_from:Mapped[date]=mapped_column(Date)
    payload:Mapped[str]=mapped_column(Text)
    changed_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    changed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class PayrollRun(Base):
    __tablename__="pay_runs"
    id:Mapped[int]=mapped_column(primary_key=True)
    period:Mapped[str]=mapped_column(String(7),unique=True,index=True)
    status:Mapped[str]=mapped_column(String(20),default="draft")
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PayrollLine(Base):
    __tablename__="pay_run_lines"
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("pay_runs.id"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    gross:Mapped[Decimal]=mapped_column(Numeric(12,2))
    lop_days:Mapped[Decimal]=mapped_column(Numeric(7,2))
    lop_amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    pf:Mapped[Decimal]=mapped_column(Numeric(12,2))
    esi:Mapped[Decimal]=mapped_column(Numeric(12,2))
    pt:Mapped[Decimal]=mapped_column(Numeric(12,2))
    tds:Mapped[Decimal]=mapped_column(Numeric(12,2))
    other_deductions:Mapped[Decimal]=mapped_column(Numeric(12,2))
    net:Mapped[Decimal]=mapped_column(Numeric(12,2))
    attendance_sessions:Mapped[int]=mapped_column(Integer,default=0)
    exceptions:Mapped[str]=mapped_column(Text,default="")
    __table_args__=(UniqueConstraint("run_id","employee_id",name="uq_pay_line_employee_period"),)

class PayrollReviewAudit(Base):
    __tablename__="pay_review_audit"
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("pay_runs.id"))
    line_id:Mapped[int]=mapped_column(ForeignKey("pay_run_lines.id"))
    reviewer_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    action:Mapped[str]=mapped_column(String(40))
    reason:Mapped[str]=mapped_column(Text)
    reviewed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ResolveExceptionIn(BaseModel):
    reason:str=Field(min_length=20,max_length=2000)


class ExpenseClaim(Base):
    __tablename__="pay_expense_claims"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    title:Mapped[str]=mapped_column(String(150))
    category:Mapped[str]=mapped_column(String(35))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    incurred_on:Mapped[date]=mapped_column(Date)
    note:Mapped[str]=mapped_column(Text,default="")
    receipt_key:Mapped[str|None]=mapped_column(String(80),nullable=True)
    receipt_type:Mapped[str|None]=mapped_column(String(30),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default="pending",index=True)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class SalaryIn(BaseModel):
    employee_id:int
    basic:Decimal=Field(ge=0,le=100000000)
    hra:Decimal=Field(default=0,ge=0,le=100000000)
    allowances:Decimal=Field(default=0,ge=0,le=100000000)
    other_deductions:Decimal=Field(default=0,ge=0,le=100000000)
    effective_from:date

class StatutoryIn(BaseModel):
    employee_id:int
    pf_employee_monthly:Decimal=Field(default=0,ge=0,le=10000000)
    esi_employee_monthly:Decimal=Field(default=0,ge=0,le=10000000)
    professional_tax_monthly:Decimal=Field(default=0,ge=0,le=10000000)
    tds_monthly:Decimal=Field(default=0,ge=0,le=10000000)
    gratuity_employer_provision:Decimal=Field(default=0,ge=0,le=10000000)
    effective_from:date

class ExpenseIn(BaseModel):
    title:str=Field(min_length=4,max_length=150)
    category:Literal["travel","food","equipment","internet","other"]
    amount:Decimal=Field(gt=0,le=1000000)
    incurred_on:date
    note:str=Field(default="",max_length=2000)

class ReviewIn(BaseModel):
    approve:bool
    note:str=Field(default="",max_length=500)

class RunIn(BaseModel):
    period:str=Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
def ym_bounds(period):
    year,month=(int(x) for x in period.split("-"))
    return date(year,month,1),date(year,month,calendar.monthrange(year,month)[1])

def salary_view(s):
    return {k:getattr(s,k) for k in ("employee_id","basic","hra","allowances","other_deductions","effective_from")}

def setting_view(s):
    return {k:getattr(s,k) for k in ("employee_id","pf_employee_monthly","esi_employee_monthly",
                "professional_tax_monthly","tds_monthly","gratuity_employer_provision","effective_from")}

def line_view(s):
    return {k:getattr(s,k) for k in ("id","run_id","employee_id","gross","lop_days","lop_amount",
         "pf","esi","pt","tds","other_deductions","net","attendance_sessions","exceptions")}

SALARY_FIELDS=("basic","hra","allowances","other_deductions")
STATUTORY_FIELDS=("pf_employee_monthly","esi_employee_monthly",
                  "professional_tax_monthly","tds_monthly","gratuity_employer_provision")

def append_config_version(db:Session,employee_id:int,kind:str,model,actor_id:int):
    fields=SALARY_FIELDS if kind=="salary" else STATUTORY_FIELDS
    payload={field:str(getattr(model,field)) for field in fields}
    db.add(PayrollConfigVersion(employee_id=employee_id,kind=kind,
            effective_from=model.effective_from,payload=json.dumps(payload),
            changed_by=actor_id))

def historical_config(db:Session,employee_id:int,kind:str,as_of:date,legacy):
    """Select historical terms effective in payroll month, not latest edit."""
    version=db.scalar(select(PayrollConfigVersion).where(
        PayrollConfigVersion.employee_id==employee_id,
        PayrollConfigVersion.kind==kind,
        PayrollConfigVersion.effective_from<=as_of).order_by(
        PayrollConfigVersion.effective_from.desc(),PayrollConfigVersion.id.desc()))
    if version:
        values={key:Decimal(value) for key,value in json.loads(version.payload).items()}
        return SimpleNamespace(effective_from=version.effective_from,**values)
    # Pre-migration accounts may have only a single legacy effective row.
    if legacy and legacy.effective_from<=as_of:
        return legacy
    return None


def apply_salary_structure(db:Session,body:SalaryIn,reviewer_id:int):
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Employee does not exist.")
    if body.other_deductions>body.basic+body.hra+body.allowances:
        raise HTTPException(422,"Deductions exceed gross pay.")
    row=db.get(SalaryStructure,body.employee_id)
    if row and not db.scalar(select(PayrollConfigVersion.id).where(
            PayrollConfigVersion.employee_id==body.employee_id,
            PayrollConfigVersion.kind=="salary").limit(1)):
        append_config_version(db,body.employee_id,"salary",row,row.reviewed_by)
    if not row:row=SalaryStructure(employee_id=body.employee_id);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    row.reviewed_by=reviewer_id
    append_config_version(db,body.employee_id,"salary",row,reviewer_id)
    return salary_view(row)


@router.put("/structures")
def upsert_structure(body:SalaryIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    raise HTTPException(403,detail={"field":"approval","message":
        "Salary changes require independent approval. Submit a salary_structure request through /governance/requests."})

@router.get("/config-history")
def config_history(employee_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    own_or_fin(user,employee_id)
    records=db.scalars(select(PayrollConfigVersion).where(
        PayrollConfigVersion.employee_id==employee_id).order_by(
        PayrollConfigVersion.effective_from.desc(),PayrollConfigVersion.id.desc())).all()
    return [{"id":r.id,"employee_id":r.employee_id,"kind":r.kind,
             "effective_from":r.effective_from,"values":json.loads(r.payload),
             "changed_by":r.changed_by,"changed_at":r.changed_at} for r in records]


@router.get("/structures")
def structures(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if employee_id:own_or_fin(user,employee_id)
    elif user.role not in FIN:employee_id=user.id
    q=select(SalaryStructure)
    if employee_id:q=q.where(SalaryStructure.employee_id==employee_id)
    return [salary_view(s) for s in db.scalars(q).all()]

def apply_statutory_settings(db:Session,body:StatutoryIn,reviewer_id:int):
    if not db.get(Employee,body.employee_id):raise HTTPException(422,"Employee not found.")
    row=db.get(StatutorySettings,body.employee_id)
    if row and not db.scalar(select(PayrollConfigVersion.id).where(
            PayrollConfigVersion.employee_id==body.employee_id,
            PayrollConfigVersion.kind=="statutory").limit(1)):
        append_config_version(db,body.employee_id,"statutory",row,row.reviewed_by)
    if not row:row=StatutorySettings(employee_id=body.employee_id);db.add(row)
    for k,v in body.model_dump().items():setattr(row,k,v)
    row.reviewed_by=reviewer_id
    append_config_version(db,body.employee_id,"statutory",row,reviewer_id)
    return setting_view(row)


@router.put("/statutory")
def configure_statutory(body:StatutoryIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    raise HTTPException(403,detail={"field":"approval","message":
        "Statutory changes require independent approval. Submit a statutory_settings request through /governance/requests."})

@router.get("/statutory")
def statutory(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if employee_id:own_or_fin(user,employee_id)
    elif user.role not in FIN:employee_id=user.id
    q=select(StatutorySettings)
    if employee_id:q=q.where(StatutorySettings.employee_id==employee_id)
    return [setting_view(s) for s in db.scalars(q).all()]

def calculate(db,employee,period):
    start,end=ym_bounds(period)
    salary=historical_config(db,employee.id,"salary",end,db.get(SalaryStructure,employee.id))
    settings=historical_config(db,employee.id,"statutory",end,db.get(StatutorySettings,employee.id))
    if salary is None:raise ValueError("Salary structure missing/effective later")
    if settings is None:raise ValueError("Reviewed statutory configuration missing")
    from .payroll_components import effective_components
    components=effective_components(db,employee.id,end)
    extra_earnings=sum((Decimal(x.amount) for x in components if x.kind=="earning"),Decimal(0))
    extra_deductions=sum((Decimal(x.amount) for x in components if x.kind=="deduction"),Decimal(0))
    # Monthly salary is prorated by calendar days of employment; LOP only by
    # approved working-day leave units (including fractional single-day leave).
    days=Decimal((end-start).days+1)
    last_day=end
    if employee.status!="active":
        from .employee_core import LifecycleEvent
        exited=db.scalar(select(func.max(LifecycleEvent.effective_date)).where(
            LifecycleEvent.employee_id==employee.id,
            LifecycleEvent.event.in_(("exited","deactivated"))))
        if exited is None or exited<start:
            raise ValueError("Employee not employed during this payroll period")
        last_day=min(end,exited)
    first_day=max(start,employee.joining_date)
    service_days=max(0,(last_day-first_day).days+1)
    if service_days==0:
        raise ValueError("Employee not employed during this payroll period")
    monthly_gross=salary.basic+salary.hra+salary.allowances+extra_earnings
    gross=money(monthly_gross*Decimal(service_days)/days)
    leave=db.scalars(select(LeaveRequest).where(LeaveRequest.employee_id==employee.id,
        LeaveRequest.leave_type=="loss_of_pay",LeaveRequest.status=="approved",
        LeaveRequest.start_date<=end,LeaveRequest.end_date>=start)).all()
    from .leave_management import working_days, user_location
    location=user_location(db,employee.id)
    lop=Decimal("0")
    for row in leave:
        overlap_start=max(row.start_date,first_day)
        overlap_end=min(row.end_date,last_day)
        if overlap_start<=overlap_end:
            lop+=working_days(db,overlap_start,overlap_end,location,row.day_part)
    lop=min(lop,Decimal(service_days))
    loss=money(monthly_gross*lop/days)
    count=db.scalar(select(func.count()).select_from(Attendance).where(
        Attendance.employee_id==employee.id,Attendance.punch_in>=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc),
        Attendance.punch_in<datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc),
        Attendance.punch_out.is_not(None))) or 0
    exceptions="No completed punches recorded; verify attendance" if not count else ""
    deductions=money(loss+settings.pf_employee_monthly+settings.esi_employee_monthly+
        settings.professional_tax_monthly+settings.tds_monthly+salary.other_deductions+extra_deductions)
    if deductions>gross:raise ValueError("Deductions exceed gross salary")
    return dict(employee_id=employee.id,gross=gross,lop_days=lop,lop_amount=loss,pf=settings.pf_employee_monthly,
        esi=settings.esi_employee_monthly,pt=settings.professional_tax_monthly,tds=settings.tds_monthly,
        other_deductions=money(salary.other_deductions+extra_deductions),net=money(gross-deductions),
        attendance_sessions=count,exceptions=exceptions)

def calculate_or_exception(db,employee,period):
    """Keep the draft reviewable even when one employee lacks payroll setup.

    Exception lines have zero payable values and block approval until the
    configuration is corrected and the draft is recalculated.
    """
    try:
        return calculate(db,employee,period)
    except ValueError as exc:
        result=dict(employee_id=employee.id,exceptions="Payroll setup: "+str(exc))
        for field in ("gross","lop_days","lop_amount","pf","esi","pt","tds","other_deductions","net"):
            result[field]=Decimal("0")
        result["attendance_sessions"]=0
        return result


@router.post("/runs",status_code=201)
def create_run(body:RunIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user)
    if db.scalar(select(PayrollRun.id).where(PayrollRun.period==body.period)):
        raise HTTPException(409,"This payroll period already has a run; no duplicate calculations allowed.")
    start,end=ym_bounds(body.period)
    # Include employees who exited during this month for their final salary.
    from .employee_core import LifecycleEvent
    exited_this_month=select(LifecycleEvent.employee_id).where(
        LifecycleEvent.event.in_(("exited","deactivated")),
        LifecycleEvent.effective_date.between(start,end))
    eligible=db.scalars(select(Employee).where(
        Employee.joining_date<=end,
        (Employee.status=="active") | Employee.id.in_(exited_this_month))).all()
    rows=[]
    for emp in eligible:
        rows.append(calculate_or_exception(db,emp,body.period))
    if not rows:raise HTTPException(422,"No eligible employees in period.")
    run=PayrollRun(period=body.period,created_by=user.id)
    db.add(run);db.flush()
    from .payroll_components import effective_components, PayslipComponent
    for row in rows:
        line=PayrollLine(run_id=run.id,**row)
        db.add(line);db.flush()
        for component in effective_components(db,row["employee_id"],end):
            db.add(PayslipComponent(line_id=line.id,code=component.code,title=component.title,
                  kind=component.kind,amount=component.amount))
    db.commit();db.refresh(run)
    return {"id":run.id,"period":run.period,"status":run.status,"employees":len(rows)}

@router.post("/runs/{run_id}/recalculate")
def recalculate_draft(run_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    """Refresh a draft after salary, statutory or attendance corrections.

    Never recalculate an approved/published run, and never remove an existing
    employee or monetary audit record. Existing component snapshots are
    refreshed atomically.
    """
    role(user,HR)
    run=db.scalar(select(PayrollRun).where(PayrollRun.id==run_id).with_for_update())
    if run is None:raise HTTPException(404,"Payroll run not found")
    if run.status!="draft":raise HTTPException(409,"Only a draft payroll can be recalculated")
    from .payroll_components import effective_components, PayslipComponent
    _,end=ym_bounds(run.period)
    lines=db.scalars(select(PayrollLine).where(PayrollLine.run_id==run_id).with_for_update()).all()
    if not lines:raise HTTPException(409,"Draft has no employee lines to recalculate")
    exceptions=0
    for line in lines:
        employee=db.get(Employee,line.employee_id)
        if employee is None:
            raise HTTPException(409,"A payroll employee was removed; contact an administrator")
        previous="gross="+str(line.gross)+"; net="+str(line.net)+"; exception="+str(line.exceptions)
        result=calculate_or_exception(db,employee,run.period)
        for field,value in result.items():setattr(line,field,value)
        if line.exceptions:exceptions+=1
        existing=db.scalars(select(PayslipComponent).where(PayslipComponent.line_id==line.id)).all()
        for component in existing:db.delete(component)
        db.flush()
        if not line.exceptions.startswith("Payroll setup:"):
            for component in effective_components(db,employee.id,end):
                db.add(PayslipComponent(line_id=line.id,code=component.code,
                    title=component.title,kind=component.kind,amount=component.amount))
        db.add(PayrollReviewAudit(run_id=run.id,line_id=line.id,reviewer_id=user.id,
            action="draft_recalculated",
            reason=previous+"; recalculated gross="+str(line.gross)+"; net="+str(line.net)))
    db.commit()
    return {"id":run.id,"period":run.period,"status":"draft",
            "recalculated":len(lines),"unresolved_exceptions":exceptions}


@router.get("/runs")
def get_runs(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user)
    return [{"id":r.id,"period":r.period,"status":r.status,"created_at":r.created_at,
             "created_by":r.created_by,"approved_at":r.approved_at} for r in db.scalars(select(PayrollRun).order_by(PayrollRun.period.desc())).all()]

@router.get("/runs/{run_id}")
def view_run(run_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user)
    run=db.get(PayrollRun,run_id)
    if not run:raise HTTPException(404)
    rows=db.scalars(select(PayrollLine).where(PayrollLine.run_id==run_id)).all()
    return {"id":run.id,"period":run.period,"status":run.status,"created_by":run.created_by,"lines":[line_view(r) for r in rows],
            "gross_total":sum((r.gross for r in rows),Decimal(0)),
            "net_total":sum((r.net for r in rows),Decimal(0)),
            "exceptions":sum(bool(r.exceptions) for r in rows)}

@router.post("/runs/{run_id}/lines/{line_id}/resolve-exception")
def resolve_payroll_exception(run_id:int,line_id:int,body:ResolveExceptionIn,
                              user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user,HR)
    run=db.get(PayrollRun,run_id)
    row=db.get(PayrollLine,line_id)
    if not run or not row or row.run_id!=run_id:raise HTTPException(404)
    if run.status!="draft":raise HTTPException(409,"Only draft payroll can be corrected.")
    if not row.exceptions:raise HTTPException(409,"No unresolved exception.")
    reason=body.reason.strip()
    db.add(PayrollReviewAudit(run_id=run_id,line_id=line_id,reviewer_id=user.id,
                              action="attendance_exception_resolved",
                              reason="Original exception: "+row.exceptions+". Review: "+reason))
    row.exceptions=""
    db.commit()
    return {"id":row.id,"exceptions":"","audit_recorded":True}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user,HR)
    run=db.get(PayrollRun,run_id)
    if not run:raise HTTPException(404)
    if run.status!="draft":raise HTTPException(409,"Only draft payroll may be approved.")
    if run.created_by==user.id:raise HTTPException(403,"Payroll requires a second-person approver.")
    exception=db.scalar(select(PayrollLine.id).where(PayrollLine.run_id==run_id,PayrollLine.exceptions!=""))
    if exception:raise HTTPException(409,"Resolve attendance exceptions before approving payroll.")
    run.status="approved";run.approved_by=user.id;run.approved_at=now()
    db.commit();return {"id":run.id,"status":run.status}

@router.post("/runs/{run_id}/publish")
def publish_run(run_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user,HR)
    run=db.get(PayrollRun,run_id)
    if not run:raise HTTPException(404)
    if run.status!="approved":raise HTTPException(409,"Approve payroll before publishing.")
    run.status="published";db.commit()
    return {"id":run.id,"status":"published","money_transferred":False}

@router.get("/my-payslips")
def my_payslips(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(PayrollLine,PayrollRun).join(PayrollRun,PayrollRun.id==PayrollLine.run_id).where(
        PayrollLine.employee_id==user.id,PayrollRun.status=="published").order_by(PayrollRun.period.desc())
    return [{"run_id":run.id,"line_id":line.id,"period":run.period,"net":line.net,"gross":line.gross} for line,run in db.execute(q).all()]

@router.get("/payslips/{line_id}.pdf")
def pdf_payslip(line_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    from reportlab.pdfgen import canvas
    row=db.get(PayrollLine,line_id)
    if not row:raise HTTPException(404)
    own_or_fin(user,row.employee_id)
    run=db.get(PayrollRun,row.run_id)
    if run.status!="published":raise HTTPException(404,"Payslip is not yet published.")
    employee=db.get(Employee,row.employee_id)
    buf=io.BytesIO()
    pdf=canvas.Canvas(buf,pagesize=(595,842),pageCompression=1)
    pdf.setTitle("Confidential payslip - "+run.period)
    pdf.setFont("Helvetica-Bold",17);pdf.drawString(46,787,"JellyGit | Salary statement")
    pdf.setFont("Helvetica",10)
    pdf.drawString(46,759,"Employee: "+employee.name)
    pdf.drawString(46,740,"Period: "+run.period+"    |    Employee ID: "+str(employee.id))
    pdf.line(46,721,549,721)
    from .payroll_components import PayslipComponent
    components=db.scalars(select(PayslipComponent).where(PayslipComponent.line_id==row.id).order_by(PayslipComponent.kind,PayslipComponent.title)).all()
    labels=[("Gross monthly earnings",row.gross),("Approved loss of pay",row.lop_amount),
        ("Employee PF",row.pf),("Employee ESI",row.esi),("Professional tax",row.pt),
        ("TDS",row.tds),("Other deductions (including configured items)",row.other_deductions)]
    labels.extend((("Additional "+("earning" if x.kind=="earning" else "deduction")+": "+x.title,x.amount) for x in components))
    y=693
    for name,amount in labels:
        if y<180:
            pdf.showPage();pdf.setFont("Helvetica",10);y=760
        pdf.drawString(46,y,name);pdf.drawRightString(540,y,"INR "+format(amount,",.2f"));y-=31
    if y<165:pdf.showPage();pdf.setFont("Helvetica",10);y=760
    pdf.line(46,y,549,y);y-=28
    pdf.setFont("Helvetica-Bold",14);pdf.drawString(46,y,"Net pay")
    pdf.drawRightString(540,y,"INR "+format(row.net,",.2f"))
    pdf.setFont("Helvetica",9)
    pdf.drawString(46,125,"Confidential payroll record. Reviewed statutory settings are employer-provided.")
    pdf.drawString(46,109,"This statement does not certify payment or statutory remittance.")
    pdf.showPage();pdf.save();buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",headers={
        "Content-Disposition":f'attachment; filename="payslip-{run.period}.pdf"',
        "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@router.post("/expenses",status_code=201)
def create_expense(body:ExpenseIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if body.incurred_on>date.today()+timedelta(days=1):raise HTTPException(422,"Expense date is in the future.")
    row=ExpenseClaim(employee_id=user.id,**body.model_dump())
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

def expense_view(row):
    return {k:getattr(row,k) for k in ("id","employee_id","title","category","amount","incurred_on",
        "note","status","reviewed_by","reviewed_at")} | {"has_receipt":bool(row.receipt_key)}

@router.get("/expenses")
def list_expenses(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all":role(user)
    q=select(ExpenseClaim).order_by(ExpenseClaim.id.desc())
    if scope=="mine":q=q.where(ExpenseClaim.employee_id==user.id)
    return [expense_view(x) for x in db.scalars(q).all()]

@router.post("/expenses/{claim_id}/receipt")
async def upload_receipt(claim_id:int,receipt:UploadFile=File(...),user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(ExpenseClaim,claim_id)
    if not row:raise HTTPException(404)
    if row.employee_id!=user.id or row.status!="pending":raise HTTPException(403)
    data=await receipt.read(5*1024*1024+1)
    if len(data)>5*1024*1024:raise HTTPException(413,"Receipt limit is 5 MB.")
    if data.startswith(b"%PDF-"):extension=".pdf";mime="application/pdf"
    elif data.startswith(bytes.fromhex("ffd8ff")):extension=".jpg";mime="image/jpeg"
    elif data.startswith(bytes.fromhex("89504e470d0a1a0a")):extension=".png";mime="image/png"
    else:raise HTTPException(415,"Upload PDF, JPEG or PNG receipt.")
    folder=Path(UPLOAD_DIR)/"expense-receipts";folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    key=uuid4().hex+extension
    dest=folder/key
    with dest.open("xb") as f:f.write(data)
    dest.chmod(0o600)
    old=row.receipt_key;row.receipt_key=key;row.receipt_type=mime;db.commit()
    if old:(folder/Path(old).name).unlink(missing_ok=True)
    return {"receipt_uploaded":True}

@router.get("/expenses/{claim_id}/receipt")
def view_receipt(claim_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(ExpenseClaim,claim_id)
    if not row:raise HTTPException(404)
    own_or_fin(user,row.employee_id)
    if not row.receipt_key:raise HTTPException(404,"Receipt not uploaded.")
    path=Path(UPLOAD_DIR)/"expense-receipts"/Path(row.receipt_key).name
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,media_type=row.receipt_type,headers={"Cache-Control":"private, no-store"})

@router.post("/expenses/{claim_id}/review")
def review_expense(claim_id:int,body:ReviewIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    role(user)
    row=db.get(ExpenseClaim,claim_id)
    if not row:raise HTTPException(404)
    if row.employee_id==user.id:raise HTTPException(403,"You cannot approve your own expense.")
    if row.status!="pending":raise HTTPException(409,"Claim already reviewed.")
    if body.approve and not row.receipt_key:raise HTTPException(422,"Receipt required for approval.")
    row.status="approved" if body.approve else "rejected"
    row.reviewed_by=user.id;row.reviewed_at=now()
    db.commit();return expense_view(row)
