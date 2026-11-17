"""Leave Management 11-22: policy-backed request and approval workflow.

Uses separate leave_* tables while preserving the MVP's legacy /leaves API.
All approval and balance decisions are made server-side.
"""
import csv
import io
import json
import os
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, and_, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, db_session, current_user
from .employee_core import EmployeeCore, OrgUnit, ADMIN, LeaveEntitlement

router = APIRouter(prefix="/leave", tags=["Leave Management"])
KINDS = ("casual", "sick", "earned", "maternity", "paternity", "comp_off", "loss_of_pay")
DAY_UNITS = {"full": Decimal("1"), "half": Decimal("0.5"), "short": Decimal("0.25")}
STAGES = ("manager", "hr", "admin")
FINAL = ("approved", "rejected", "cancelled")


class LeavePolicy(Base):
    __tablename__ = "leave_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    leave_type: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    annual_days: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    monthly_accrual: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    late_year_monthly_accrual: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"),server_default="0")
    monthly_schedule: Mapped[str | None] = mapped_column(Text, nullable=True)  # 12 policy-year months
    year_type: Mapped[str] = mapped_column(String(12), default="financial", server_default="financial")
    carry_forward_limit: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    encashment_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    probation_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_chain: Mapped[str] = mapped_column(String(100), default="manager,hr")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class LeavePolicyVersion(Base):
    """Immutable policy terms in force from effective_from (inclusive)."""
    __tablename__="leave_policy_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    leave_type: Mapped[str] = mapped_column(String(30), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint("leave_type","effective_from",name="uq_leave_policy_version_effective"),)

class LeaveRequest(Base):
    __tablename__ = "leave_requests_v2"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    day_part: Mapped[str] = mapped_column(String(12), default="full")
    days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    chain: Mapped[str] = mapped_column(String(100))
    manager_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalEvent(Base):
    __tablename__ = "leave_approval_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests_v2.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    action: Mapped[str] = mapped_column(String(30))
    stage: Mapped[str] = mapped_column(String(25), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApprovalDelegation(Base):
    __tablename__ = "leave_approval_delegations"
    id: Mapped[int] = mapped_column(primary_key=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    delegate_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Holiday(Base):
    __tablename__ = "leave_holidays"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(100), default="all")
    holiday_date: Mapped[date] = mapped_column(Date, index=True)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("location","holiday_date","name",name="uq_leave_holiday"),)


class LeaveNotice(Base):
    __tablename__ = "leave_notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("leave_requests_v2.id"), nullable=True)
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeaveEmailDelivery(Base):
    """Transactionally queued leave email; in-app notification remains immediate."""
    __tablename__="leave_email_outbox"
    id:Mapped[int]=mapped_column(primary_key=True)
    recipient_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    request_id:Mapped[int|None]=mapped_column(ForeignKey("leave_requests_v2.id"),nullable=True)
    subject:Mapped[str]=mapped_column(String(160))
    message:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(24),default="queued",index=True)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    last_error:Mapped[str]=mapped_column(String(500),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),
        default=lambda:datetime.now(timezone.utc))
    sent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class Encashment(Base):
    __tablename__ = "leave_encashment_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))
    year: Mapped[int] = mapped_column(Integer)
    days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)


class PolicyIn(BaseModel):
    leave_type: Literal["casual","sick","earned","maternity","paternity","comp_off","loss_of_pay"]
    annual_days: Decimal = Field(default=0,ge=0,le=365)
    monthly_accrual: Decimal = Field(default=0,ge=0,le=31)
    late_year_monthly_accrual: Decimal = Field(default=0,ge=0,le=31)
    monthly_schedule: list[Decimal] | None = Field(default=None,min_length=12,max_length=12)
    year_type: Literal["financial","calendar"] = "financial"
    effective_from: date = Field(default_factory=date.today)
    change_reason: str = Field(default="",max_length=500)
    carry_forward_limit: Decimal = Field(default=0,ge=0,le=365)
    encashment_allowed: bool = False
    probation_allowed: bool = True
    approval_chain: list[Literal["manager","hr","admin"]] = Field(default_factory=lambda:["manager","hr"])
    active: bool = True

    @model_validator(mode="after")
    def valid_chain(self):
        if not self.approval_chain or len(self.approval_chain)>3 or len(set(self.approval_chain))!=len(self.approval_chain):
            raise ValueError("Approval stages must be unique and limited to manager, HR and admin.")
        if self.effective_from < date.today():
            raise ValueError("Policy effective date must be today or a future date.")
        if self.monthly_schedule is not None:
            if any(not value.is_finite() or value < 0 or value > 31 for value in self.monthly_schedule):
                raise ValueError("Each month must contain a leave credit between 0 and 31 days.")
            if sum(self.monthly_schedule) > 365:
                raise ValueError("Total annual leave credits cannot exceed 365.")
            if self.annual_days or self.monthly_accrual or self.late_year_monthly_accrual:
                raise ValueError("Custom monthly schedule cannot be combined with annual or tiered accrual.")
        return self


class LeaveIn(BaseModel):
    leave_type: Literal["casual","sick","earned","maternity","paternity","comp_off","loss_of_pay"]
    start_date: date
    end_date: date
    day_part: Literal["full","half","short"] = "full"
    reason: str = Field(min_length=3,max_length=1000)

    @model_validator(mode="after")
    def date_range(self):
        if self.end_date<self.start_date:
            raise ValueError("End date cannot be before start date.")
        if self.day_part!="full" and self.start_date!=self.end_date:
            raise ValueError("Half-day and short leave must be for a single date.")
        if (self.end_date-self.start_date).days>365:
            raise ValueError("A request must not exceed 366 calendar days.")
        return self


class ActionIn(BaseModel):
    action: Literal["approve","reject","cancel_approve","cancel_reject"]
    note: str = Field(default="",max_length=500)


class DelegationIn(BaseModel):
    delegate_id: int
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_date<self.start_date:
            raise ValueError("Delegation end date cannot precede its start date.")
        return self


class HolidayIn(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    holiday_date: date
    location: str = Field(default="all",min_length=1,max_length=100)
    optional: bool = False


class EncashmentIn(BaseModel):
    leave_type: Literal["earned","comp_off"]
    year: int = Field(ge=2020,le=2100)
    days: Decimal = Field(gt=0,le=365)


class EntitlementIn(BaseModel):
    employee_id: int
    year: int = Field(ge=2020,le=2100)
    leave_type: Literal["casual","sick","earned","maternity","paternity","comp_off","loss_of_pay"]
    allocated_days: Decimal = Field(ge=0,le=365)


def hr_only(user: Employee = Depends(current_user)):
    if user.role not in ADMIN:
        raise HTTPException(403,"HR permission required")
    return user


def policy_admin(user: Employee = Depends(current_user)):
    if user.role not in ("super_admin","admin"):
        raise HTTPException(403,"Admin approval required; HR must submit a governance request")
    return user


def employee(db: Session,id: int):
    record=db.get(Employee,id)
    if not record or record.status!="active":
        raise HTTPException(404,"Active employee not found")
    return record


def policy(db: Session,kind: str) -> LeavePolicy:
    row=db.scalar(select(LeavePolicy).where(LeavePolicy.leave_type==kind,LeavePolicy.active.is_(True)))
    if not row:
        raise HTTPException(422,"Leave type is not configured or is inactive; contact HR.")
    return row


def chain_for(policy_row: LeavePolicy, manager_id: int | None) -> list[str]:
    stages=[x for x in policy_row.approval_chain.split(",") if x]
    if "manager" in stages and manager_id is None:
        raise HTTPException(422,"Reporting manager must be assigned before this leave can be submitted.")
    return stages


def org_manager(db: Session, employee_id: int) -> int | None:
    row=db.get(EmployeeCore,employee_id)
    return row.manager_id if row else None


def notify(db: Session, recipient_id: int, message: str, request_id: int | None = None):
    """In-app and email outbox entries share the leave workflow transaction."""
    from .notification_center import add_inbox
    add_inbox(db,recipient_id,"approval",
              "Leave request update" if request_id is None else f"Leave request #{request_id}",
              message[:500],"leaves")
    db.add(LeaveNotice(recipient_id=recipient_id,request_id=request_id,message=message[:500]))
    db.add(LeaveEmailDelivery(recipient_id=recipient_id,request_id=request_id,
        subject="JellyGit HRMS: leave update",message=message[:500],status="queued"))


def email_notice(email: str, subject: str, message: str):
    """Transport used only by the outbox worker, never by an API request."""
    host=os.getenv("SMTP_HOST")
    sender=os.getenv("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured.")
    note=EmailMessage()
    note["From"]=sender
    note["To"]=email
    note["Subject"]=subject
    note.set_content(message)
    with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","587")),timeout=5) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            smtp.login(os.getenv("SMTP_USER"),os.getenv("SMTP_PASSWORD",""))
        smtp.send_message(note)


def deliver_queued_emails(db:Session,limit:int=25)->dict:
    """Explicit worker invocation; serializes queued sends and records failures."""
    delivered=failed=0
    rows=db.scalars(select(LeaveEmailDelivery).where(
        LeaveEmailDelivery.status.in_(("queued","retry"))).order_by(
        LeaveEmailDelivery.id).limit(min(max(limit,1),100)).with_for_update(skip_locked=True)).all()
    for item in rows:
        employee=db.get(Employee,item.recipient_id)
        item.attempts+=1
        try:
            if not employee or not employee.email:raise RuntimeError("Recipient email not available.")
            email_notice(employee.email,item.subject,item.message)
            item.status="sent";item.sent_at=datetime.now(timezone.utc);item.last_error=""
            delivered+=1
        except (OSError,smtplib.SMTPException,RuntimeError) as exc:
            item.last_error=str(exc)[:500]
            item.status="failed" if item.attempts>=5 else "retry"
            failed+=1
    db.commit()
    return {"delivered":delivered,"failed":failed,"processed":len(rows)}


@router.get("/email-outbox")
def email_outbox(user:Employee=Depends(hr_only),db:Session=Depends(db_session)):
    rows=db.scalars(select(LeaveEmailDelivery).order_by(
        LeaveEmailDelivery.id.desc()).limit(100)).all()
    return [{"id":item.id,"recipient_id":item.recipient_id,"request_id":item.request_id,
             "status":item.status,"attempts":item.attempts,"error":item.last_error,
             "created_at":item.created_at,"sent_at":item.sent_at} for item in rows]


@router.post("/email-outbox/{delivery_id}/retry")
def retry_delivery(delivery_id:int,user:Employee=Depends(hr_only),db:Session=Depends(db_session)):
    item=db.scalar(select(LeaveEmailDelivery).where(
        LeaveEmailDelivery.id==delivery_id).with_for_update())
    if not item:raise HTTPException(404,"Email delivery not found")
    if item.status=="sent":raise HTTPException(409,"This email has already been delivered.")
    item.status="queued";item.attempts=0;item.last_error=""
    db.commit()
    return {"id":item.id,"status":"queued"}



def dates_between(start: date,end: date):
    for offset in range((end-start).days+1):
        yield start+timedelta(days=offset)


def working_days(db: Session,start: date,end: date,location: str,part: str) -> Decimal:
    # Default business rule: Sat/Sun and mandatory location-specific public holidays excluded.
    holiday_dates=set(db.scalars(select(Holiday.holiday_date).where(
        Holiday.holiday_date.between(start,end),Holiday.optional.is_(False),
        Holiday.location.in_(["all",location]))).all())
    working=sum(1 for d in dates_between(start,end) if d.weekday()<5 and d not in holiday_dates)
    return Decimal(working) if part=="full" else DAY_UNITS[part] if working else Decimal("0")


def user_location(db: Session, user_id: int) -> str:
    from .main import EmployeeProfile
    row=db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id==user_id))
    return row.work_location.strip() if row and row.work_location else "all"


def leave_days(db: Session, row: LeaveRequest)->Decimal:
    return Decimal(row.days)


def fy_start_year(value: date) -> int:
    return value.year if value.month>=4 else value.year-1


def fy_bounds(year: int) -> tuple[date,date]:
    return date(year,4,1),date(year+1,3,31)


def policy_start_year(value:date,year_type:str="financial")->int:
    return value.year if year_type=="calendar" else fy_start_year(value)


def policy_bounds(year:int,year_type:str="financial")->tuple[date,date]:
    return (date(year,1,1),date(year,12,31)) if year_type=="calendar" else fy_bounds(year)


def policy_snapshot(row:LeavePolicy)->dict:
    return {"annual_days":str(row.annual_days or 0),"monthly_accrual":str(row.monthly_accrual or 0),
            "late_year_monthly_accrual":str(row.late_year_monthly_accrual or 0),
            "monthly_schedule":json.loads(row.monthly_schedule) if row.monthly_schedule else None,
            "carry_forward_limit":str(row.carry_forward_limit or 0),"year_type":row.year_type or "financial",
            "active":bool(row.active),"approval_chain":row.approval_chain or "manager,hr",
            "probation_allowed":bool(row.probation_allowed),"encashment_allowed":bool(row.encashment_allowed)}


def policy_versions(db:Session,row:LeavePolicy)->list[tuple[date,dict]]:
    versions=db.scalars(select(LeavePolicyVersion).where(
        LeavePolicyVersion.leave_type==row.leave_type).order_by(LeavePolicyVersion.effective_from)).all()
    if not versions:
        # Legacy policies existed before versioning; their terms were effective for older years.
        return [(date(2000,1,1),policy_snapshot(row))]
    return [(version.effective_from,json.loads(version.snapshot_json)) for version in versions]


def terms_at(versions:list[tuple[date,dict]],on:date)->dict|None:
    result=None
    for effective,terms in versions:
        if effective>on:break
        result=terms
    return result


def apply_leave_policy(db:Session,body:PolicyIn,actor_id:int|None=None,reason:str="")->LeavePolicy:
    row=db.scalar(select(LeavePolicy).where(LeavePolicy.leave_type==body.leave_type).with_for_update())
    is_new=row is None
    if is_new:
        row=LeavePolicy(leave_type=body.leave_type)
        db.add(row)
        db.flush()
    existing=db.scalars(select(LeavePolicyVersion).where(
        LeavePolicyVersion.leave_type==body.leave_type).order_by(LeavePolicyVersion.effective_from.desc())).all()
    if not is_new and (row.year_type or "financial")!=body.year_type:
        raise HTTPException(422,"The leave year type cannot change after policy creation. Create a separate leave type and migrate balances through an audited allocation.")
    if existing and body.effective_from<=existing[0].effective_from:
        raise HTTPException(422,"Policy effective date must be later than the most recent published version.")
    if not is_new and not existing:
        # Preserve legacy entitlements and prior-year carry forwards unchanged.
        db.add(LeavePolicyVersion(leave_type=body.leave_type,effective_from=date(2000,1,1),
            snapshot_json=json.dumps(policy_snapshot(row)),actor_id=actor_id,reason="Legacy policy baseline"))
    values=body.model_dump(exclude={"leave_type","approval_chain","monthly_schedule","effective_from","change_reason"})
    row.monthly_schedule=json.dumps([float(v) for v in body.monthly_schedule]) if body.monthly_schedule is not None else None
    for key,value in values.items():setattr(row,key,value)
    row.approval_chain=",".join(body.approval_chain)
    db.add(LeavePolicyVersion(leave_type=body.leave_type,effective_from=body.effective_from,
        snapshot_json=json.dumps(policy_snapshot(row)),actor_id=actor_id,
        reason=(reason or body.change_reason or "Approved policy configuration").strip()))
    db.flush()
    return row


def prorated_entitlement(annual:Decimal,joined:date,year:int,year_type:str="financial")->Decimal:
    start,end=policy_bounds(year,year_type)
    eligible_from=max(start,joined)
    if eligible_from>end:return Decimal("0")
    return ((annual*Decimal((end-eligible_from).days+1)/Decimal((end-start).days+1)*2)
            .quantize(Decimal("1"),rounding=ROUND_HALF_UP))/2


def used_days(db:Session,employee_id:int,year:int,kind:str,year_type:str="financial")->Decimal:
    start,end=policy_bounds(year,year_type)
    value=db.scalar(select(func.coalesce(func.sum(LeaveRequest.days),0)).where(
        LeaveRequest.employee_id==employee_id,LeaveRequest.leave_type==kind,
        LeaveRequest.start_date.between(start,end),
        LeaveRequest.status.in_(["approved","pending"])))
    return Decimal(value or 0)


def tiered_monthly_entitlement(joined:date,fy:int,through:date,first_rate:Decimal,late_rate:Decimal,
                               schedule:list[Decimal]|None=None,year_type:str="financial")->Decimal:
    start,end=policy_bounds(fy,year_type)
    through=min(through,end)
    if through<max(start,joined):return Decimal("0")
    credited=Decimal("0")
    cursor=date(max(start,joined).year,max(start,joined).month,1)
    until=date(through.year,through.month,1)
    first_month=4 if year_type=="financial" else 1
    while cursor<=until:
        period_month=((cursor.month-first_month)%12)+1
        monthly=Decimal(str(schedule[period_month-1])) if schedule is not None else (
            Decimal(late_rate) if period_month>=9 and late_rate>0 else Decimal(first_rate))
        month_after=date(cursor.year+1,1,1) if cursor.month==12 else date(cursor.year,cursor.month+1,1)
        month_end=month_after-timedelta(days=1)
        eligible=(month_end-max(cursor,joined,start)).days+1
        monthly*=Decimal(eligible)/Decimal((month_end-cursor).days+1)
        credited+=monthly
        cursor=month_after
    return (credited*2).quantize(Decimal("1"),rounding=ROUND_HALF_UP)/Decimal(2)


def base_entitlement(db:Session,employee_id:int,year:int,kind:str,config:LeavePolicy)->Decimal:
    staff=employee(db,employee_id)
    basis=config.year_type or "financial"
    start,end=policy_bounds(year,basis)
    ent=db.scalar(select(LeaveEntitlement).where(LeaveEntitlement.employee_id==employee_id,
                LeaveEntitlement.year==year,LeaveEntitlement.leave_type==kind))
    if ent is not None:return Decimal(ent.allocated_days)
    versions=policy_versions(db,config)
    today=date.today()
    through=min(end,today)
    if through<max(start,staff.joining_date):return Decimal("0")
    cursor=max(start,staff.joining_date)
    credited=Decimal("0")
    period_days=Decimal((end-start).days+1)
    # Each past date is evaluated using its own policy version, not today's terms.
    # Monthly credits use a full month once that month starts, with prorating
    # for joining dates and within-month policy changes.
    months_seen=set()
    while cursor<=through:
        terms=terms_at(versions,cursor)
        if terms and terms.get("active",True):
            schedule=terms.get("monthly_schedule")
            first=Decimal(str(terms.get("monthly_accrual",0)))
            late=Decimal(str(terms.get("late_year_monthly_accrual",0)))
            if schedule is not None or first:
                period_month=((cursor.month-(4 if basis=="financial" else 1))%12)
                rate=Decimal(str(schedule[period_month])) if schedule is not None else (
                    late if period_month>=8 and late>0 else first)
                month_after=(date(cursor.year+1,1,1) if cursor.month==12
                             else date(cursor.year,cursor.month+1,1))
                month_days=Decimal((month_after-date(cursor.year,cursor.month,1)).days)
                credited+=rate/month_days
                months_seen.add((cursor.year,cursor.month))
            else:
                credited+=Decimal(str(terms.get("annual_days",0)))/period_days
        cursor+=timedelta(days=1)
    # The present month is credited in full up front, matching legacy behavior.
    if through==today and through<end and (through.year,through.month) in months_seen:
        month_after=(date(through.year+1,1,1) if through.month==12
                     else date(through.year,through.month+1,1))
        extra_until=min(month_after-timedelta(days=1),end)
        cursor=today+timedelta(days=1)
        while cursor<=extra_until:
            terms=terms_at(versions,cursor)
            if terms and terms.get("active",True):
                schedule=terms.get("monthly_schedule")
                first=Decimal(str(terms.get("monthly_accrual",0)))
                late=Decimal(str(terms.get("late_year_monthly_accrual",0)))
                if schedule is not None or first:
                    period_month=((cursor.month-(4 if basis=="financial" else 1))%12)
                    rate=Decimal(str(schedule[period_month])) if schedule is not None else (
                        late if period_month>=8 and late>0 else first)
                    credited+=rate/Decimal((month_after-date(cursor.year,cursor.month,1)).days)
            cursor+=timedelta(days=1)
    # Annual policies grant the prorated entitlement for the whole policy year.
    # Only monthly accrual is restricted to months reached by today's date.
    cursor=through+timedelta(days=1)
    while cursor<=end:
        terms=terms_at(versions,cursor)
        if terms and terms.get("active",True):
            schedule=terms.get("monthly_schedule")
            if schedule is None and Decimal(str(terms.get("monthly_accrual",0)))==0 and cursor>=staff.joining_date:
                credited+=Decimal(str(terms.get("annual_days",0)))/period_days
        cursor+=timedelta(days=1)
    return (credited*2).quantize(Decimal("1"),rounding=ROUND_HALF_UP)/Decimal(2)


def balance(db: Session, employee_id: int, year: int,kind: str) -> dict:
    config=policy(db,kind)
    allocated=base_entitlement(db,employee_id,year,kind,config)
    carry=Decimal("0")
    if config.carry_forward_limit:
        prior=base_entitlement(db,employee_id,year-1,kind,config)
        prior_used=used_days(db,employee_id,year-1,kind,config.year_type)
        prior_encashed=Decimal(db.scalar(select(func.coalesce(func.sum(Encashment.days),0)).where(
            Encashment.employee_id==employee_id,Encashment.year==year-1,
            Encashment.leave_type==kind,Encashment.status=="approved")) or 0)
        carry=min(max(prior-prior_used-prior_encashed,Decimal("0")),Decimal(config.carry_forward_limit))
    used=used_days(db,employee_id,year,kind,config.year_type)
    encashed=Decimal(db.scalar(select(func.coalesce(func.sum(Encashment.days),0)).where(
        Encashment.employee_id==employee_id,Encashment.year==year,
        Encashment.leave_type==kind,Encashment.status=="approved")) or 0)
    reserved=Decimal(db.scalar(select(func.coalesce(func.sum(Encashment.days),0)).where(
        Encashment.employee_id==employee_id,Encashment.year==year,
        Encashment.leave_type==kind,Encashment.status=="pending")) or 0)
    return {"leave_type":kind,"year":year,"year_type":config.year_type,"fy_label":(f"CY {year}" if config.year_type=="calendar" else f"FY {year}-{str(year+1)[-2:]}"),
            "allocated":float(allocated),"carried":float(carry),
            "used":float(used),"encashed":float(encashed),"reserved_encashment":float(reserved),
            "remaining":float(allocated+carry-used-encashed-reserved)}



def record_view(row: LeaveRequest)->dict:
    stages=[s for s in row.chain.split(",") if s]
    return {"id":row.id,"employee_id":row.employee_id,"leave_type":row.leave_type,
            "start_date":row.start_date,"end_date":row.end_date,"day_part":row.day_part,
            "days":float(row.days),"reason":row.reason,"status":row.status,
            "current_stage":stages[row.current_stage] if row.current_stage<len(stages) and row.status=="pending" else None,
            "cancellation_requested":row.cancellation_requested,
            "created_at":row.created_at}


def active_delegate(db: Session,manager_id: int,date_now: date)->set[int]:
    return set(db.scalars(select(ApprovalDelegation.delegate_id).where(
        ApprovalDelegation.manager_id==manager_id,ApprovalDelegation.active.is_(True),
        ApprovalDelegation.start_date<=date_now,ApprovalDelegation.end_date>=date_now)).all())


def can_approve(db: Session,user: Employee,row: LeaveRequest,stage: str)->bool:
    if row.employee_id==user.id:
        return False
    if stage=="manager":
        if user.role in ADMIN:
            # HR/admin escalation is recorded with a compulsory override note.
            return True
        if row.manager_snapshot_id is None:
            return False
        manager=db.get(Employee,row.manager_snapshot_id)
        if not manager or manager.status!="active":
            return False
        return user.id==row.manager_snapshot_id or user.id in active_delegate(db,row.manager_snapshot_id,date.today())
    if stage=="hr":
        return user.role in ADMIN
    if stage=="admin":
        return user.role in ("super_admin","admin")
    return False


def upcoming_approvers(db: Session,row: LeaveRequest)->list[int]:
    stages=[s for s in row.chain.split(",") if s]
    if row.current_stage>=len(stages):
        return []
    stage=stages[row.current_stage]
    if stage=="manager":
        manager=db.get(Employee,row.manager_snapshot_id) if row.manager_snapshot_id else None
        if not manager or manager.status!="active":
            return list(db.scalars(select(Employee.id).where(
                Employee.status=="active",Employee.role.in_(ADMIN))).all())
        return [row.manager_snapshot_id]+list(active_delegate(db,row.manager_snapshot_id,date.today()))
    roles=ADMIN if stage=="hr" else ("super_admin","admin")
    return list(db.scalars(select(Employee.id).where(Employee.status=="active",Employee.role.in_(roles))).all())


@router.get("/hr-overview")
def financial_year_hr_overview(fy: int | None=Query(default=None,ge=2020,le=2100),
                               user: Employee=Depends(hr_only),db: Session=Depends(db_session)):
    from .main import Attendance
    from .employee_core import EmployeeCore
    fy=fy if fy is not None else fy_start_year(date.today())
    staff=db.scalars(select(Employee).where(Employee.status=="active").order_by(Employee.name)).all()
    kinds=db.scalars(select(LeavePolicy.leave_type).where(LeavePolicy.active.is_(True))).all()
    ongoing=set(db.scalars(select(Attendance.employee_id).where(Attendance.punch_out.is_(None))).all())
    pending=db.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status=="pending"))
    result=[]
    for person in staff:
        core=db.get(EmployeeCore,person.id)
        result.append({"id":person.id,"name":person.name,"manager_id":core.manager_id if core else None,"department":person.department,
                       "role":person.role,"status":person.status,"joining_date":person.joining_date,
                       "currently_checked_in":person.id in ongoing,
                       "leave_balances":[balance(db,person.id,fy,kind) for kind in kinds]})
    return {"fy":fy,"fy_label":f"FY {fy}-{str(fy+1)[-2:]}",
            "headcount":sum(1 for x in staff if x.status=="active"),
            "currently_checked_in":len(ongoing),
            "pending_leave_requests":pending or 0,
            "unassigned_managers":sum(1 for person in result if person["status"]=="active"
                and person["role"] not in ("super_admin","admin") and not person["manager_id"]),
            "employees":result}


@router.get("/policies")
def policies(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    rows=db.scalars(select(LeavePolicy).order_by(LeavePolicy.leave_type)).all()
    return [{"leave_type":p.leave_type,"annual_days":float(p.annual_days),"monthly_accrual":float(p.monthly_accrual),"late_year_monthly_accrual":float(p.late_year_monthly_accrual),"monthly_schedule":json.loads(p.monthly_schedule) if p.monthly_schedule else None,"year_type":p.year_type,"effective_from":(db.scalar(select(func.max(LeavePolicyVersion.effective_from)).where(LeavePolicyVersion.leave_type==p.leave_type)) or date.today()),
             "carry_forward_limit":float(p.carry_forward_limit),"encashment_allowed":p.encashment_allowed,
             "probation_allowed":p.probation_allowed,"approval_chain":p.approval_chain.split(",") if p.approval_chain else [],
             "active":p.active} for p in rows]


@router.put("/policies")
def save_policy(body: PolicyIn,user: Employee = Depends(policy_admin),db: Session = Depends(db_session)):
    apply_leave_policy(db,body,user.id)
    db.commit()
    return {"ok":True,"leave_type":body.leave_type}


@router.put("/allocations")
def allocate(body: EntitlementIn,user: Employee = Depends(policy_admin),db: Session = Depends(db_session)):
    employee(db,body.employee_id)
    policy(db,body.leave_type)
    row=db.scalar(select(LeaveEntitlement).where(
        LeaveEntitlement.employee_id==body.employee_id,LeaveEntitlement.year==body.year,
        LeaveEntitlement.leave_type==body.leave_type).with_for_update())
    if row is None:
        row=LeaveEntitlement(employee_id=body.employee_id,year=body.year,leave_type=body.leave_type)
        db.add(row)
    row.allocated_days=body.allocated_days
    db.commit()
    return balance(db,body.employee_id,body.year,body.leave_type)


@router.get("/balances")
def balances(employee_id: int | None = None,year: int | None=Query(default=None,ge=2020,le=2100),
             user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    target=employee_id or user.id
    if target!=user.id and user.role not in ADMIN:
        raise HTTPException(403,"Only HR can view another employee's balances")
    configs=db.scalars(select(LeavePolicy).where(LeavePolicy.active.is_(True)).order_by(LeavePolicy.leave_type)).all()
    return [balance(db,target,year if year is not None else policy_start_year(date.today(),p.year_type),p.leave_type) for p in configs]


@router.post("/requests",status_code=201)
def request_leave(body: LeaveIn,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    config=policy(db,body.leave_type)
    basis=config.year_type or "financial"
    if policy_start_year(body.start_date,basis)!=policy_start_year(body.end_date,basis):
        raise HTTPException(422,"Split leave requests crossing the configured leave-year boundary.")
    core=db.get(EmployeeCore,user.id)
    if core and core.lifecycle=="probation" and not config.probation_allowed:
        raise HTTPException(422,"Leave type is restricted during probation")
    manager_id=core.manager_id if core else None
    stages=chain_for(config,manager_id)
    location=user_location(db,user.id)
    days=working_days(db,body.start_date,body.end_date,location,body.day_part)
    if days<=0:
        raise HTTPException(422,"Selected dates contain no working leave days")
    # Serialize submission for each employee/year before both overlap and balance checks.
    db.execute(select(func.pg_advisory_xact_lock(user.id,policy_start_year(body.start_date,basis))))
    overlap=db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.employee_id==user.id,LeaveRequest.status.in_(["pending","approved"]),
        LeaveRequest.start_date<=body.end_date,LeaveRequest.end_date>=body.start_date))
    if overlap:
        raise HTTPException(409,"An existing leave request overlaps these dates")
    if body.leave_type!="loss_of_pay":
        available=balance(db,user.id,policy_start_year(body.start_date,basis),body.leave_type)
        if available["remaining"]<float(days):
            raise HTTPException(422,"Insufficient leave balance for this request")
    row=LeaveRequest(employee_id=user.id,leave_type=body.leave_type,start_date=body.start_date,
                     end_date=body.end_date,day_part=body.day_part,days=days,reason=body.reason,
                     chain=",".join(stages),manager_snapshot_id=manager_id,
                     status="pending" if stages else "approved")
    db.add(row)
    db.flush()
    db.add(ApprovalEvent(request_id=row.id,actor_id=user.id,action="submitted",stage=""))
    for approver in upcoming_approvers(db,row):
        notify(db,approver,f"{user.name} requested {float(days)} day(s) of {body.leave_type} leave.",row.id)
    notify(db,user.id,f"Leave request #{row.id} submitted.",row.id)
    db.commit()
    db.refresh(row)
    # Email has been durably queued for all upcoming approvers and the requester.
    # Run the separate worker to deliver messages; a failed SMTP never delays leave submission.
    return record_view(row)


@router.get("/requests")
def requests(scope: Literal["mine","team","approvals","all"]="mine",
             user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    query=select(LeaveRequest).order_by(LeaveRequest.id.desc())
    if scope=="mine":
        query=query.where(LeaveRequest.employee_id==user.id)
    elif scope=="team":
        reports=db.scalars(select(EmployeeCore.employee_id).where(EmployeeCore.manager_id==user.id)).all()
        if user.role not in ADMIN and user.role!="manager":
            raise HTTPException(403,"Manager or HR access required")
        query=query.where(LeaveRequest.employee_id.in_(reports))
    elif scope=="all":
        if user.role not in ADMIN:
            raise HTTPException(403,"HR access required")
    else:
        if user.role in ADMIN:
            pass
        else:
            query=query.where(or_(LeaveRequest.manager_snapshot_id==user.id,
                                  LeaveRequest.manager_snapshot_id.in_(
                                      select(ApprovalDelegation.manager_id).where(
                                          ApprovalDelegation.delegate_id==user.id,ApprovalDelegation.active.is_(True),
                                          ApprovalDelegation.start_date<=date.today(),
                                          ApprovalDelegation.end_date>=date.today()))))
    # Approval filtering depends on stage and delegates; do it before capping
    # the list so older pending decisions are never hidden by recent history.
    rows=db.scalars(query if scope=="approvals" else query.limit(500)).all()
    if scope=="approvals":
        rows=[r for r in rows if
              (r.status=="approved" and r.cancellation_requested and user.role in ADMIN and r.employee_id!=user.id)
              or (r.status=="pending" and not r.cancellation_requested
                  and r.current_stage<len([stage for stage in r.chain.split(",") if stage])
                  and can_approve(db,user,r,[stage for stage in r.chain.split(",") if stage][r.current_stage]))]
    return [record_view(row) for row in rows[:500]]


@router.post("/requests/{request_id}/review")
def review(request_id: int,body: ActionIn,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    row=db.scalar(select(LeaveRequest).where(LeaveRequest.id==request_id).with_for_update())
    if not row:
        raise HTTPException(404,"Leave request not found")
    stages=[s for s in row.chain.split(",") if s]
    if body.action in ("cancel_approve","cancel_reject"):
        if not row.cancellation_requested or row.status!="approved":
            raise HTTPException(409,"No approved cancellation is awaiting review")
        if user.role not in ADMIN or user.id==row.employee_id:
            raise HTTPException(403,"Only a different HR administrator may review cancellation")
        row.cancellation_requested=False
        if body.action=="cancel_approve":
            row.status="cancelled"
            row.cancelled_at=datetime.now(timezone.utc)
        action=body.action
        stage="hr"
    else:
        if row.status!="pending" or row.current_stage>=len(stages):
            raise HTTPException(409,"Request is not waiting for approval")
        stage=stages[row.current_stage]
        if not can_approve(db,user,row,stage):
            raise HTTPException(403,"You are not the current approver")
        if stage=="manager" and user.role in ADMIN and (
            row.manager_snapshot_id!=user.id and user.id not in (
                active_delegate(db,row.manager_snapshot_id,date.today())
                if row.manager_snapshot_id else set())):
            if len(body.note.strip())<10:
                raise HTTPException(422,detail={"field":"note",
                    "message":"Explain this HR override in at least 10 characters."})
            audit_action="override_"+body.action
        else:
            audit_action=body.action
        if body.action=="reject":
            row.status="rejected"
        else:
            row.current_stage+=1
            if row.current_stage>=len(stages):
                row.status="approved"
        action=audit_action
    row.updated_at=datetime.now(timezone.utc)
    db.add(ApprovalEvent(request_id=row.id,actor_id=user.id,action=action,stage=stage,note=body.note))
    result_notice=("Your leave cancellation request was declined; original leave remains approved."
        if action=="cancel_reject" else f"Your {row.leave_type} leave request #{row.id} is {row.status}.")
    notify(db,row.employee_id,result_notice,row.id)
    if row.status=="pending":
        for target in upcoming_approvers(db,row):
            notify(db,target,f"Leave request #{row.id} needs your approval.",row.id)
    db.commit()
    # The transaction already queued an email and durable in-app notice.
    return record_view(row)


@router.post("/requests/{request_id}/withdraw")
def withdraw(request_id: int,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    row=db.scalar(select(LeaveRequest).where(LeaveRequest.id==request_id).with_for_update())
    if not row:
        raise HTTPException(404,"Leave request not found")
    if row.employee_id!=user.id:
        raise HTTPException(403,"Only the requester can withdraw a leave request")
    if row.status=="pending":
        row.status="cancelled"
        row.cancelled_at=datetime.now(timezone.utc)
        action="withdrawn"
    elif row.status=="approved" and not row.cancellation_requested:
        row.cancellation_requested=True
        action="cancellation_requested"
        for target in db.scalars(select(Employee.id).where(Employee.status=="active",Employee.role.in_(ADMIN))):
            if target!=user.id:
                notify(db,target,f"Cancellation of approved leave #{row.id} needs HR approval.",row.id)
    else:
        raise HTTPException(409,"Leave is not eligible for withdrawal or cancellation")
    row.updated_at=datetime.now(timezone.utc)
    db.add(ApprovalEvent(request_id=row.id,actor_id=user.id,action=action))
    notify(db,user.id,f"Leave request #{row.id}: {action.replace('_',' ')}.",row.id)
    db.commit()
    return record_view(row)


@router.get("/requests/{request_id}/history")
def history(request_id: int,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    row=db.get(LeaveRequest,request_id)
    if not row:
        raise HTTPException(404,"Leave request not found")
    allowed = row.employee_id==user.id or user.role in ADMIN or row.manager_snapshot_id==user.id
    if not allowed and row.manager_snapshot_id is not None:
        allowed = user.id in active_delegate(db,row.manager_snapshot_id,date.today())
    if not allowed:
        raise HTTPException(403,"Not permitted")
    events=db.scalars(select(ApprovalEvent).where(ApprovalEvent.request_id==request_id).order_by(ApprovalEvent.id)).all()
    return [{"action":e.action,"stage":e.stage,"actor_id":e.actor_id,"at":e.at,"note":e.note} for e in events]


@router.get("/holidays")
def holidays(year: int | None=Query(default=None,ge=2020,le=2100),location: str="all",
             user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    year=year if year is not None else date.today().year
    rows=db.scalars(select(Holiday).where(Holiday.holiday_date.between(date(year,1,1),date(year,12,31)),
        Holiday.location.in_(["all",location])).order_by(Holiday.holiday_date)).all()
    return [{"id":h.id,"name":h.name,"date":h.holiday_date,"location":h.location,"optional":h.optional} for h in rows]


@router.post("/holidays",status_code=201)
def add_holiday(body: HolidayIn,user: Employee = Depends(hr_only),db: Session = Depends(db_session)):
    row=Holiday(**body.model_dump())
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(409,"Holiday already exists") from exc
    db.refresh(row)
    return {"id":row.id,"name":row.name,"date":row.holiday_date}


@router.get("/calendar")
def team_calendar(month: int | None=Query(default=None,ge=1,le=12),
                  year: int | None=Query(default=None,ge=2020,le=2100),
                  user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    month=month if month is not None else date.today().month
    year=year if year is not None else date.today().year
    if user.role in ADMIN:
        ids=db.scalars(select(Employee.id).where(Employee.status=="active")).all()
    elif user.role=="manager":
        ids=db.scalars(select(EmployeeCore.employee_id).where(EmployeeCore.manager_id==user.id)).all()+[user.id]
    else:
        ids=[user.id]
    first=date(year,month,1)
    last=(date(year+1,1,1)-timedelta(days=1)) if month==12 else (date(year,month+1,1)-timedelta(days=1))
    leaves=db.scalars(select(LeaveRequest).where(LeaveRequest.employee_id.in_(ids),
        LeaveRequest.status=="approved",LeaveRequest.start_date<=last,
        LeaveRequest.end_date>=first)).all()
    staff={e.id:e.name for e in db.scalars(select(Employee).where(Employee.id.in_(ids)))}
    return [{"employee_id":r.employee_id,"employee_name":staff.get(r.employee_id,"Employee"),
             "start_date":r.start_date,"end_date":r.end_date,"leave_type":r.leave_type,"day_part":r.day_part} for r in leaves]


@router.post("/delegations",status_code=201)
def delegate(body: DelegationIn,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    if user.role not in ("manager","admin","super_admin","hr"):
        raise HTTPException(403,"Only approvers may delegate")
    if body.delegate_id==user.id:
        raise HTTPException(422,"Cannot delegate to yourself")
    target=employee(db,body.delegate_id)
    if target.role not in ("manager","hr","admin","super_admin"):
        raise HTTPException(422,"Delegate needs a manager or HR role")
    if (body.end_date-body.start_date).days>90:
        raise HTTPException(422,"Delegations must be 90 days or less")
    row=ApprovalDelegation(manager_id=user.id,delegate_id=body.delegate_id,
                           start_date=body.start_date,end_date=body.end_date)
    db.add(row)
    notify(db,target.id,f"{user.name} delegated leave approvals to you until {body.end_date}.")
    db.commit()
    return {"id":row.id,"delegate_id":body.delegate_id,"start_date":body.start_date,"end_date":body.end_date}


@router.get("/delegations")
def delegations(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    rows=db.scalars(select(ApprovalDelegation).where(
        or_(ApprovalDelegation.manager_id==user.id,ApprovalDelegation.delegate_id==user.id)).order_by(ApprovalDelegation.id.desc())).all()
    return [{"id":r.id,"manager_id":r.manager_id,"delegate_id":r.delegate_id,
             "start_date":r.start_date,"end_date":r.end_date,"active":r.active} for r in rows]


@router.delete("/delegations/{delegation_id}")
def revoke_delegation(delegation_id: int,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    row=db.get(ApprovalDelegation,delegation_id)
    if not row:
        raise HTTPException(404,"Delegation not found")
    if row.manager_id!=user.id and user.role not in ADMIN:
        raise HTTPException(403,"Cannot revoke another manager's delegation")
    row.active=False
    db.commit()
    return {"ok":True}


@router.get("/notifications")
def notifications(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    rows=db.scalars(select(LeaveNotice).where(LeaveNotice.recipient_id==user.id).order_by(LeaveNotice.id.desc()).limit(100)).all()
    return [{"id":n.id,"request_id":n.request_id,"message":n.message,"created_at":n.created_at,"read":n.read_at is not None} for n in rows]


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: int,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    row=db.get(LeaveNotice,notification_id)
    if not row or row.recipient_id!=user.id:
        raise HTTPException(404,"Notification not found")
    row.read_at=datetime.now(timezone.utc)
    db.commit()
    return {"ok":True}


@router.post("/encashment",status_code=201)
def request_encashment(body: EncashmentIn,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    config=policy(db,body.leave_type)
    if not config.encashment_allowed:
        raise HTTPException(422,"Encashment is disabled for this leave type")
    available=balance(db,user.id,body.year,body.leave_type)
    if available["remaining"]<float(body.days):
        raise HTTPException(422,"Insufficient available balance for encashment")
    row=Encashment(employee_id=user.id,leave_type=body.leave_type,year=body.year,days=body.days)
    db.add(row)
    db.commit()
    return {"id":row.id,"status":row.status}


@router.get("/encashment")
def list_encashments(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    query=select(Encashment).order_by(Encashment.id.desc())
    if user.role not in ADMIN:
        query=query.where(Encashment.employee_id==user.id)
    rows=db.scalars(query.limit(200)).all()
    return [{"id":r.id,"employee_id":r.employee_id,"year":r.year,"leave_type":r.leave_type,
             "days":float(r.days),"status":r.status} for r in rows]


@router.post("/encashment/{encashment_id}/review")
def review_encashment(encashment_id: int,approve: bool,user: Employee = Depends(hr_only),db: Session = Depends(db_session)):
    row=db.scalar(select(Encashment).where(Encashment.id==encashment_id).with_for_update())
    if not row or row.status!="pending":
        raise HTTPException(409,"Encashment request is unavailable")
    if row.employee_id==user.id:
        raise HTTPException(403,"Cannot approve your own encashment")
    available=balance(db,row.employee_id,row.year,row.leave_type)
    if approve and available["remaining"]<0:
        raise HTTPException(422,"Leave balance became negative while encashment was pending")
    row.status="approved" if approve else "rejected"
    row.reviewed_by=user.id
    notify(db,row.employee_id,f"Leave encashment #{row.id} {row.status}.")
    db.commit()
    return {"id":row.id,"status":row.status,"days":float(row.days)}


@router.get("/reports")
def reports(year: int | None=Query(default=None,ge=2020,le=2100),
            department: str | None=None,month: int | None=Query(default=None,ge=1,le=12),
            format: Literal["json","csv"]="json",
            user: Employee = Depends(hr_only),db: Session = Depends(db_session)):
    year=year if year is not None else fy_start_year(date.today())
    # Mixed CY/FY policies are filtered using each leave type's actual period.
    configured=db.scalars(select(LeavePolicy)).all()
    ranges={p.leave_type:policy_bounds(year,p.year_type or "financial") for p in configured}
    stmt=select(LeaveRequest,Employee).join(Employee,LeaveRequest.employee_id==Employee.id)
    if department:
        stmt=stmt.where(Employee.department==department)
    if month:
        stmt=stmt.where(func.extract("month",LeaveRequest.start_date)==month)
    items=[(r,e) for r,e in db.execute(stmt.order_by(LeaveRequest.start_date.desc())).all()
           if r.leave_type in ranges and ranges[r.leave_type][0]<=r.start_date<=ranges[r.leave_type][1]]
    rows=[{"employee_id":e.id,"employee":e.name,"department":e.department,
           "type":r.leave_type,"start":str(r.start_date),"end":str(r.end_date),
           "days":float(r.days),"status":r.status} for r,e in items]
    if format=="json":
        return {"year":year,"month":month,"requests":len(rows),
                "approved_days":sum(r["days"] for r in rows if r["status"]=="approved"),
                "by_type":{kind:sum(r["days"] for r in rows if r["type"]==kind and r["status"]=="approved") for kind in KINDS},
                "rows":rows}
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=["employee_id","employee","department","type","start","end","days","status"])
    writer.writeheader()
    for row in rows:
        # Avoid spreadsheet formula injection on user-controlled strings.
        writer.writerow({k:("'"+str(v) if isinstance(v,str) and v.startswith(("=","+","-","@")) else v) for k,v in row.items()})
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=leave-report.csv"})
