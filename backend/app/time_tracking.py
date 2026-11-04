"""Attendance and time workflows (roadmap 23–30), opt-in policies and audited approvals."""
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, Attendance, current_user, db_session
from .employee_core import EmployeeCore

router = APIRouter(prefix="/time",tags=["Attendance & Time"])
HR = ("super_admin","admin","hr")
CATEGORIES = ("regularization","overtime","wfh","on_duty","shift_swap")
NOW = lambda: datetime.now(timezone.utc)

class TimePolicy(Base):
    __tablename__="time_policies"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    location:Mapped[str]=mapped_column(String(100),unique=True,default="all")
    grace_minutes:Mapped[int]=mapped_column(Integer,default=15)
    half_day_under_hours:Mapped[Decimal]=mapped_column(Numeric(5,2),default=Decimal("4"))
    overtime_after_hours:Mapped[Decimal]=mapped_column(Numeric(5,2),default=Decimal("9"))
    auto_deduct:Mapped[bool]=mapped_column(Boolean,default=False)
    geo_required:Mapped[bool]=mapped_column(Boolean,default=False)
    office_lat:Mapped[Decimal|None]=mapped_column(Numeric(10,7),nullable=True)
    office_lon:Mapped[Decimal|None]=mapped_column(Numeric(10,7),nullable=True)
    radius_meters:Mapped[int]=mapped_column(Integer,default=250)

class Shift(Base):
    __tablename__="time_shifts"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    start_time:Mapped[str]=mapped_column(String(5))
    end_time:Mapped[str]=mapped_column(String(5))
    break_minutes:Mapped[int]=mapped_column(Integer,default=0)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Roster(Base):
    __tablename__="time_rosters"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    shift_id:Mapped[int]=mapped_column(ForeignKey("time_shifts.id"))
    work_date:Mapped[date]=mapped_column(Date,index=True)
    __table_args__=(UniqueConstraint("employee_id","work_date",name="uq_time_roster_day"),)

class TimeRequest(Base):
    __tablename__="time_requests"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    kind:Mapped[str]=mapped_column(String(30),index=True)
    work_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    reason:Mapped[str]=mapped_column(Text)
    hours:Mapped[Decimal|None]=mapped_column(Numeric(7,2),nullable=True)
    proposed_in:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    proposed_out:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    target_employee_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    status:Mapped[str]=mapped_column(String(24),default="pending",index=True)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=NOW)

class TimeAudit(Base):
    __tablename__="time_audits"
    id:Mapped[int]=mapped_column(primary_key=True)
    request_id:Mapped[int|None]=mapped_column(ForeignKey("time_requests.id"),nullable=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    actor_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    event:Mapped[str]=mapped_column(String(40))
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=NOW)

class Timesheet(Base):
    __tablename__="time_timesheets"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    work_date:Mapped[date]=mapped_column(Date)
    project_id:Mapped[int|None]=mapped_column(ForeignKey("projects.id"),nullable=True)
    task:Mapped[str]=mapped_column(String(180))
    hours:Mapped[Decimal]=mapped_column(Numeric(5,2))
    note:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(20),default="draft")

class BiometricPunch(Base):
    __tablename__="time_biometric_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    device_event_id:Mapped[str]=mapped_column(String(150),unique=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    direction:Mapped[str]=mapped_column(String(4))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=NOW)

class PolicyIn(BaseModel):
    location:str=Field(default="all",min_length=1,max_length=100)
    grace_minutes:int=Field(default=15,ge=0,le=180)
    half_day_under_hours:Decimal=Field(default=Decimal("4"),ge=0,le=24)
    overtime_after_hours:Decimal=Field(default=Decimal("9"),ge=1,le=24)
    auto_deduct:bool=False
    geo_required:bool=False
    office_lat:float|None=Field(default=None,ge=-90,le=90)
    office_lon:float|None=Field(default=None,ge=-180,le=180)
    radius_meters:int=Field(default=250,ge=50,le=10000)
    @model_validator(mode="after")
    def geo_coordinates(self):
        if self.geo_required and (self.office_lat is None or self.office_lon is None):
            raise ValueError("Set office coordinates before enforcing geofencing.")
        return self

class ShiftIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    start_time:time
    end_time:time
    break_minutes:int=Field(default=0,ge=0,le=240)

class RosterIn(BaseModel):
    employee_id:int
    shift_id:int
    work_date:date

class TimeRequestIn(BaseModel):
    kind:Literal["regularization","overtime","wfh","on_duty","shift_swap"]
    work_date:date
    end_date:date|None=None
    reason:str=Field(min_length=10,max_length=1000)
    hours:Decimal|None=Field(default=None,gt=0,le=24)
    proposed_in:datetime|None=None
    proposed_out:datetime|None=None
    target_employee_id:int|None=None
    @model_validator(mode="after")
    def consistent(self):
        if self.end_date and self.end_date<self.work_date: raise ValueError("End date must follow start date.")
        if self.kind=="overtime" and self.hours is None: raise ValueError("Enter overtime hours.")
        if self.kind=="regularization" and (not self.proposed_in or not self.proposed_out or self.proposed_out<=self.proposed_in):
            raise ValueError("Specify valid punch-in and punch-out times.")
        if self.kind=="shift_swap" and not self.target_employee_id: raise ValueError("Select the shift-swap colleague.")
        return self

class TimesheetIn(BaseModel):
    work_date:date
    task:str=Field(min_length=3,max_length=180)
    hours:Decimal=Field(gt=0,le=24)
    project_id:int|None=None
    note:str=Field(default="",max_length=1000)

class GeoPunchIn(BaseModel):
    lat:float|None=Field(default=None,ge=-90,le=90)
    lon:float|None=Field(default=None,ge=-180,le=180)
    accuracy_m:float|None=Field(default=None,ge=0,le=100000)
    consent:bool=False

class BiometricEventIn(BaseModel):
    device_event_id:str=Field(min_length=6,max_length=150)
    employee_id:int
    direction:Literal["in","out"]
    observed_at:datetime

def only_hr(user:Employee=Depends(current_user)):
    if user.role not in HR:raise HTTPException(403,"HR/Admin only")
    return user

def manager_for(db:Session,employee_id:int)->int|None:
    core=db.get(EmployeeCore,employee_id)
    return core.manager_id if core else None

def permitted(db:Session,user:Employee,owner:int)->bool:
    return user.role in HR or user.id==manager_for(db,owner)

def request_dict(row:TimeRequest):
    return {k:getattr(row,k) for k in ("id","employee_id","kind","work_date","end_date","reason","hours",
            "proposed_in","proposed_out","target_employee_id","status","reviewed_by","reviewed_at","created_at")}

def effective_policy(db:Session)->TimePolicy|None:
    return db.scalar(select(TimePolicy).where(TimePolicy.location=="all"))

def policy_dict(p:TimePolicy|None):
    return {"location":p.location if p else "all","grace_minutes":p.grace_minutes if p else 15,
            "half_day_under_hours":float(p.half_day_under_hours) if p else 4,
            "overtime_after_hours":float(p.overtime_after_hours) if p else 9,
            "auto_deduct":p.auto_deduct if p else False,
            "geo_required":p.geo_required if p else False,
            "office_lat":float(p.office_lat) if p and p.office_lat is not None else None,
            "office_lon":float(p.office_lon) if p and p.office_lon is not None else None,
            "radius_meters":p.radius_meters if p else 250}

@router.get("/policy")
def get_policy(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    p=policy_dict(effective_policy(db))
    if user.role not in HR:
        p.pop("office_lat",None);p.pop("office_lon",None)
    return p

@router.put("/policy")
def save_policy(body:PolicyIn,user:Employee=Depends(only_hr),db:Session=Depends(db_session)):
    p=db.scalar(select(TimePolicy).where(TimePolicy.location==body.location))
    if not p:
        p=TimePolicy(location=body.location);db.add(p)
    for key,value in body.model_dump().items():setattr(p,key,value)
    db.commit();return policy_dict(p)

@router.post("/punch")
def geo_punch(body:GeoPunchIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    from .main import punch
    p=effective_policy(db)
    if p and p.geo_required:
        if not body.consent or body.lat is None or body.lon is None or body.accuracy_m is None:
            raise HTTPException(422,detail={"field":"location","message":"Allow location access to punch in/out at this office."})
        if body.accuracy_m>min(p.radius_meters,150):
            raise HTTPException(422,detail={"field":"location","message":"GPS accuracy is too low. Retry outside or ask HR."})
        radius=6371000
        dlat=radians(float(p.office_lat)-body.lat)
        dlon=radians(float(p.office_lon)-body.lon)
        a=sin(dlat/2)**2+cos(radians(body.lat))*cos(radians(float(p.office_lat)))*sin(dlon/2)**2
        distance=radius*2*asin(min(1,sqrt(a)))
        if distance>p.radius_meters:
            raise HTTPException(403,detail={"field":"location","message":"Outside the permitted office radius."})
    # This route uses the same advisory-locked punch core as the existing UI.
    db.info["geo_verified"]=True
    try:
        row=punch(user=user,db=db)
    finally:
        db.info.pop("geo_verified",None)
    return {"id":row.id,"punch_in":row.punch_in,"punch_out":row.punch_out}

@router.post("/biometric/events")
def biometric_event(body:BiometricEventIn,x_device_token:str|None=Header(default=None),db:Session=Depends(db_session)):
    import hmac
    configured=os.getenv("HRMS_BIOMETRIC_SHARED_TOKEN","")
    if len(configured)<32 or not x_device_token or not hmac.compare_digest(configured,x_device_token):
        raise HTTPException(403,"Device integration is not configured or authorized.")
    existing=db.scalar(select(BiometricPunch).where(BiometricPunch.device_event_id==body.device_event_id))
    if existing:return {"accepted":True,"duplicate":True}
    person=db.get(Employee,body.employee_id)
    if not person or person.status!="active":raise HTTPException(422,"Active employee is required.")
    # Store and audit signed vendor events; do not blindly rewrite historical web punches.
    row=BiometricPunch(**body.model_dump())
    db.add(row);db.commit()
    return {"accepted":True,"duplicate":False,"requires_reconciliation":True}

@router.get("/shifts")
def shifts(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    return [{"id":s.id,"name":s.name,"start_time":s.start_time,"end_time":s.end_time,
             "break_minutes":s.break_minutes,"active":s.active}
            for s in db.scalars(select(Shift).order_by(Shift.name)).all()]

@router.post("/shifts",status_code=201)
def create_shift(body:ShiftIn,user:Employee=Depends(only_hr),db:Session=Depends(db_session)):
    row=Shift(name=body.name,start_time=body.start_time.strftime("%H:%M"),
              end_time=body.end_time.strftime("%H:%M"),break_minutes=body.break_minutes)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"name":row.name}

@router.put("/roster")
def assign_shift(body:RosterIn,user:Employee=Depends(only_hr),db:Session=Depends(db_session)):
    if not db.get(Shift,body.shift_id) or not db.get(Employee,body.employee_id):
        raise HTTPException(422,"Choose a valid employee and shift.")
    row=db.scalar(select(Roster).where(Roster.employee_id==body.employee_id,Roster.work_date==body.work_date))
    if not row:row=Roster(employee_id=body.employee_id,work_date=body.work_date,shift_id=body.shift_id);db.add(row)
    else:row.shift_id=body.shift_id
    db.commit();return {"employee_id":body.employee_id,"shift_id":body.shift_id,"work_date":body.work_date}

@router.get("/roster")
def roster(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    owner=employee_id or user.id
    if owner!=user.id and not permitted(db,user,owner):raise HTTPException(403,"Team access required")
    return [{"id":r.id,"employee_id":r.employee_id,"work_date":r.work_date,"shift_id":r.shift_id,
             "shift_name":db.get(Shift,r.shift_id).name}
            for r in db.scalars(select(Roster).where(Roster.employee_id==owner).order_by(Roster.work_date.desc())).all()]

@router.get("/daily")
def daily(employee_id:int|None=None,month:int=0,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not 0<=month<=12:raise HTTPException(422,"Month must be between 1 and 12.")
    owner=employee_id or user.id
    if owner!=user.id and not permitted(db,user,owner):raise HTTPException(403,"Team access required")
    punches=db.scalars(select(Attendance).where(Attendance.employee_id==owner).order_by(Attendance.punch_in.desc()).limit(1000)).all()
    policy=effective_policy(db)
    threshold=float(policy.half_day_under_hours) if policy else 4
    overtime_threshold=float(policy.overtime_after_hours) if policy else 9
    grace=policy.grace_minutes if policy else 15
    entries={}
    for punch in punches:
        if month and punch.punch_in.month!=month:continue
        key=punch.punch_in.date().isoformat()
        if key not in entries:entries[key]={"date":key,"sessions":0,"hours":0.0,"open":False,"first_punch":punch.punch_in}
        entries[key]["sessions"]+=1
        if punch.punch_out:entries[key]["hours"]+=max(0,(punch.punch_out-punch.punch_in).total_seconds()/3600)
        else:entries[key]["open"]=True
        if punch.punch_in<entries[key]["first_punch"]:entries[key]["first_punch"]=punch.punch_in
    roster_map={r.work_date.isoformat():db.get(Shift,r.shift_id) for r in
      db.scalars(select(Roster).where(Roster.employee_id==owner)).all()}
    for key,v in entries.items():
        shift=roster_map.get(key)
        v["late"]=False
        if shift:
            start=datetime.combine(date.fromisoformat(key),time.fromisoformat(shift.start_time),tzinfo=timezone.utc)
            v["late"]=v["first_punch"]>start+timedelta(minutes=grace)
        v["half_day"]=not v["open"] and v["hours"]<threshold
        v["overtime_hours"]=round(max(0,v["hours"]-overtime_threshold),2) if not v["open"] else 0
        v["hours"]=round(v["hours"],2)
        del v["first_punch"]
        v["classification_only"]=True
    return sorted(entries.values(),key=lambda a:a["date"],reverse=True)

@router.post("/requests",status_code=201)
def create_request(body:TimeRequestIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    manager=manager_for(db,user.id)
    if manager is None:raise HTTPException(422,detail={"field":"manager_id","message":"Your reporting manager must be assigned by HR."})
    if body.work_date>date.today()+timedelta(days=365):raise HTTPException(422,"Date is too far in the future.")
    if body.kind=="shift_swap" and body.target_employee_id==user.id:raise HTTPException(422,"Choose another employee.")
    if body.kind=="shift_swap" and not db.get(Employee,body.target_employee_id):raise HTTPException(422,"Choose an existing colleague.")
    row=TimeRequest(employee_id=user.id,**body.model_dump())
    if body.kind=="shift_swap":row.status="pending_colleague"
    db.add(row);db.flush()
    db.add(TimeAudit(request_id=row.id,employee_id=user.id,actor_id=user.id,event="submitted"))
    db.commit();db.refresh(row)
    return request_dict(row)

@router.get("/requests")
def list_requests(scope:Literal["mine","approvals","all"]="mine",
                  user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in HR:raise HTTPException(403,"HR access required")
    query=select(TimeRequest).order_by(TimeRequest.id.desc())
    if scope=="mine":
        query=query.where((TimeRequest.employee_id==user.id)|
                          ((TimeRequest.target_employee_id==user.id)&(TimeRequest.kind=="shift_swap")))
    elif scope=="approvals":
        if user.role not in HR:
            team=db.scalars(select(EmployeeCore.employee_id).where(EmployeeCore.manager_id==user.id)).all()
            query=query.where(TimeRequest.employee_id.in_(team))
        query=query.where(TimeRequest.status=="pending")
    return [request_dict(r) for r in db.scalars(query).all()]

@router.post("/requests/{request_id}/review")
def review_request(request_id:int,approve:bool,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(TimeRequest,request_id)
    if not row:raise HTTPException(404,"Request not found")
    if not permitted(db,user,row.employee_id) or user.id==row.employee_id:
        raise HTTPException(403,"Not an authorized approver")
    if row.status!="pending":raise HTTPException(409,"Request already reviewed.")
    if row.kind=="shift_swap" and approve:
        # The colleague first agrees explicitly; a manager cannot swap shifts unilaterally.
        first=db.scalar(select(Roster).where(Roster.employee_id==row.employee_id,Roster.work_date==row.work_date))
        second=db.scalar(select(Roster).where(Roster.employee_id==row.target_employee_id,Roster.work_date==row.work_date))
        if not first or not second:raise HTTPException(422,"Both colleagues must have shifts on the same day.")
        first.shift_id,second.shift_id=second.shift_id,first.shift_id
    if row.kind=="regularization" and approve:
        proposed_in=row.proposed_in
        proposed_out=row.proposed_out
        assert proposed_in and proposed_out
        if (proposed_out-proposed_in).total_seconds()>24*3600:
            raise HTTPException(422,"Corrected shift cannot exceed 24 hours.")
        collision=db.scalar(select(Attendance.id).where(Attendance.employee_id==row.employee_id,
                  Attendance.punch_in<proposed_out,
                  (Attendance.punch_out>proposed_in)|(Attendance.punch_out.is_(None))))
        if collision:
            raise HTTPException(409,"Correction overlaps an existing attendance session. Ask HR to review the original punch.")
        db.add(Attendance(employee_id=row.employee_id,punch_in=proposed_in,punch_out=proposed_out))
    row.status="approved" if approve else "rejected"
    row.reviewed_by=user.id;row.reviewed_at=NOW()
    db.add(TimeAudit(request_id=row.id,employee_id=row.employee_id,actor_id=user.id,event=row.status))
    # Approved regularizations are recorded as corrections, not silently inserted into existing punches.
    db.commit();return request_dict(row)

@router.post("/requests/{request_id}/colleague-response")
def respond_to_swap(request_id:int,accept:bool,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(TimeRequest,request_id)
    if not row:raise HTTPException(404,"Swap request not found")
    if row.kind!="shift_swap" or row.target_employee_id!=user.id:
        raise HTTPException(403,"Only the selected colleague can respond to this swap.")
    if row.status!="pending_colleague":raise HTTPException(409,"This request can no longer be answered.")
    row.status="pending" if accept else "rejected"
    db.add(TimeAudit(request_id=row.id,employee_id=row.employee_id,actor_id=user.id,
                     event="colleague_accepted" if accept else "colleague_declined"))
    db.commit();return request_dict(row)


@router.get("/audits/{request_id}")
def audits(request_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(TimeRequest,request_id)
    if not row:raise HTTPException(404,"Request not found")
    if user.id!=row.employee_id and not permitted(db,user,row.employee_id):raise HTTPException(403)
    return [{"event":a.event,"at":a.created_at,"actor_id":a.actor_id}
            for a in db.scalars(select(TimeAudit).where(TimeAudit.request_id==request_id)).all()]

@router.get("/timesheets")
def timesheets(scope:Literal["mine","all"]="mine",user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if scope=="all" and user.role not in HR:raise HTTPException(403)
    q=select(Timesheet).order_by(Timesheet.work_date.desc(),Timesheet.id.desc())
    if scope=="mine":q=q.where(Timesheet.employee_id==user.id)
    return [{"id":t.id,"employee_id":t.employee_id,"work_date":t.work_date,"project_id":t.project_id,
             "task":t.task,"hours":float(t.hours),"note":t.note,"status":t.status} for t in db.scalars(q).all()]

@router.post("/timesheets",status_code=201)
def create_timesheet(body:TimesheetIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    from .main import Project
    if body.project_id is not None:
        from .project_management import ProjectDetail
        detail=db.get(ProjectDetail,body.project_id)
        if not db.get(Project,body.project_id) or (
            user.role not in HR and (not detail or detail.sourced_by_id!=user.id)):
            raise HTTPException(422,detail={"field":"project_id","message":"Select one of your sourced projects."})
    used=db.scalar(select(func.coalesce(func.sum(Timesheet.hours),0)).where(
         Timesheet.employee_id==user.id,Timesheet.work_date==body.work_date)) or 0
    if Decimal(used)+body.hours>24:raise HTTPException(422,detail={"field":"hours","message":"Daily timesheets cannot exceed 24 hours."})
    row=Timesheet(employee_id=user.id,**body.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"work_date":row.work_date,"hours":float(row.hours),"status":row.status}

@router.post("/timesheets/{timesheet_id}/submit")
def submit_timesheet(timesheet_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(Timesheet,timesheet_id)
    if not row:raise HTTPException(404)
    if row.employee_id!=user.id:raise HTTPException(403)
    if row.status!="draft":raise HTTPException(409,"Already submitted")
    row.status="submitted";db.commit();return {"status":row.status}
