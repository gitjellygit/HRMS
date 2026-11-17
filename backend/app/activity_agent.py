"""Transparent employee activity-agent enrollment and heartbeat status (pilot)."""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, current_user, db_session

router=APIRouter(prefix="/activity-agent",tags=["Employee Activity Agent"])
HR={"hr","admin","super_admin"}

def utcnow():return datetime.now(timezone.utc)

class ActivityDevice(Base):
    __tablename__="activity_agent_devices"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True)
    device_label:Mapped[str]=mapped_column(String(120),default="Windows workstation")
    state:Mapped[str]=mapped_column(String(20),default="not_started")
    last_seen:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    stopped_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    exit_reason:Mapped[str]=mapped_column(Text,default="")
    active_seconds:Mapped[int]=mapped_column(Integer,default=0)
    idle_seconds:Mapped[int]=mapped_column(Integer,default=0)
    revoked:Mapped[bool]=mapped_column(default=False)

class EnrollIn(BaseModel):
    employee_id:int
    device_label:str=Field(default="Windows workstation",min_length=3,max_length=120)

class BeatIn(BaseModel):
    state:Literal["monitoring","stopped"]
    active_seconds:int=Field(ge=0,le=86400)
    idle_seconds:int=Field(ge=0,le=86400)
    exit_reason:str|None=Field(default=None,max_length=1000)

def require_hr(user):
    if user.role not in HR:raise HTTPException(403,"HR access required.")

@router.post("/devices",status_code=201)
def enroll(data:EnrollIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    employee=db.get(Employee,data.employee_id)
    if not employee or employee.status!="active":raise HTTPException(422,"Choose an active employee.")
    token=secrets.token_urlsafe(40)
    device=ActivityDevice(employee_id=data.employee_id,token_hash=hashlib.sha256(token.encode()).hexdigest(),device_label=data.device_label)
    db.add(device);db.commit();db.refresh(device)
    return {"device_id":device.id,"token":token,"employee_id":device.employee_id,"warning":"Token is displayed once. Give it only to the enrolled employee device."}

@router.post("/heartbeat")
def heartbeat(data:BeatIn,authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
    if not authorization or not authorization.startswith("Bearer "):raise HTTPException(401,"Device token required.")
    token=authorization.removeprefix("Bearer ").strip()
    device=db.scalar(select(ActivityDevice).where(ActivityDevice.token_hash==hashlib.sha256(token.encode()).hexdigest(),ActivityDevice.revoked.is_(False)))
    if not device:raise HTTPException(401,"Invalid or revoked device token.")
    if data.state=="stopped" and (not data.exit_reason or len(data.exit_reason.strip())<10):
        raise HTTPException(422,"An exit reason of at least 10 characters is required.")
    device.state=data.state
    device.active_seconds=data.active_seconds
    device.idle_seconds=data.idle_seconds
    device.last_seen=utcnow()
    if data.state=="stopped":
        device.stopped_at=utcnow()
        device.exit_reason=data.exit_reason.strip()
    else:
        device.stopped_at=None
        device.exit_reason=""
    db.commit()
    return {"ok":True}

@router.get("/devices")
def list_devices(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    devices=db.scalars(select(ActivityDevice).order_by(ActivityDevice.employee_id,ActivityDevice.id)).all()
    now=utcnow()
    employees={e.id:e.name for e in db.scalars(select(Employee)).all()}
    result=[]
    for d in devices:
        seen=d.last_seen
        if seen is not None and seen.tzinfo is None:seen=seen.replace(tzinfo=timezone.utc)
        online=bool(d.state=="monitoring" and seen and now-seen<timedelta(seconds=100) and not d.revoked)
        result.append({"id":d.id,"employee_id":d.employee_id,"employee_name":employees.get(d.employee_id,f"Employee #{d.employee_id}"),"device_label":d.device_label,
                       "status":"monitoring" if online else ("stopped" if d.state=="stopped" else "offline"),"last_seen":seen,
                       "active_seconds":d.active_seconds,"idle_seconds":d.idle_seconds,"exit_reason":d.exit_reason if d.state=="stopped" else "","revoked":d.revoked})
    return result

@router.post("/devices/{device_id}/revoke")
def revoke(device_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    d=db.get(ActivityDevice,device_id)
    if not d:raise HTTPException(404,"Device not found.")
    d.revoked=True
    d.state="stopped"
    db.commit()
    return {"revoked":True}
