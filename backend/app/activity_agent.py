"""Transparent employee activity-agent enrollment and heartbeat status (pilot)."""
import hashlib
import json
import os
import threading
import time
from collections import deque
import secrets
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Employee, current_user, db_session

router=APIRouter(prefix="/activity-agent",tags=["Employee Activity Agent"])
HR={"hr","admin","super_admin"}
_auto_registration_lock=threading.Lock()
_auto_registration_times=deque()  # process-local burst control; enforce edge rate limits at proxy, too

def utcnow():return datetime.now(timezone.utc)

class ActivityDevice(Base):
    __tablename__="activity_agent_devices"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),index=True,nullable=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True)
    device_label:Mapped[str]=mapped_column(String(120),default="Windows workstation")
    state:Mapped[str]=mapped_column(String(20),default="not_started")
    last_seen:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    stopped_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    exit_reason:Mapped[str]=mapped_column(Text,default="")
    active_seconds:Mapped[int]=mapped_column(Integer,default=0)
    idle_seconds:Mapped[int]=mapped_column(Integer,default=0)
    app_usage_json:Mapped[str]=mapped_column(Text,default="{}")
    revoked:Mapped[bool]=mapped_column(default=False)

class ActivityInvite(Base):
    __tablename__="activity_agent_invitations"
    id:Mapped[int]=mapped_column(primary_key=True)
    code_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"),nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    device_id:Mapped[int|None]=mapped_column(ForeignKey("activity_agent_devices.id"),nullable=True)

class RegisterIn(BaseModel):
    invitation_code:str=Field(min_length=20,max_length=150)
    device_label:str=Field(min_length=3,max_length=120)

class AutoRegisterIn(BaseModel):
    device_label:str=Field(min_length=3,max_length=120)

class AssignIn(BaseModel):
    employee_id:int

class EnrollIn(BaseModel):
    employee_id:int
    device_label:str=Field(default="Windows workstation",min_length=3,max_length=120)

class BeatIn(BaseModel):
    state:Literal["monitoring","stopped"]
    active_seconds:int=Field(ge=0,le=86400)
    idle_seconds:int=Field(ge=0,le=86400)
    exit_reason:str|None=Field(default=None,max_length=1000)
    apps:dict[str,int]=Field(default_factory=dict,max_length=30)

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

@router.post("/invitations",status_code=201)
def create_invitation(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    code=secrets.token_urlsafe(32)
    invite=ActivityInvite(code_hash=hashlib.sha256(code.encode()).hexdigest(),
                          created_by=user.id,expires_at=utcnow()+timedelta(days=7))
    db.add(invite);db.commit();db.refresh(invite)
    return {"invitation_id":invite.id,"invitation_code":code,
            "expires_at":invite.expires_at,
            "notice":"Provision the code only on an authorized company workstation."}

@router.post("/register-auto",status_code=201)
def register_automatic_pending(data:AutoRegisterIn,db:Session=Depends(db_session)):
    """Untrusted self-registration, pending ONLY. Disable except during controlled pilot.

    Public hostname is NOT device identity. HR must verify the actual asset before
    assignment. The returned token has no access to HRMS employee APIs.
    """
    if os.getenv("HRMS_ACTIVITY_AUTO_REGISTER_ENABLED","false").lower() not in {"1","true","yes"}:
        raise HTTPException(503,"Automatic device registration is not enabled by HRMS administrator.")
    with _auto_registration_lock:
        now=time.monotonic()
        while _auto_registration_times and now-_auto_registration_times[0]>3600:
            _auto_registration_times.popleft()
        if len(_auto_registration_times)>=10:
            raise HTTPException(429,"Device registration limit reached. Contact HR/IT.")
        # Cap pending records globally to prevent unlimited unapproved device rows.
        pending=db.scalar(select(func.count()).select_from(ActivityDevice).where(
            ActivityDevice.employee_id.is_(None),ActivityDevice.revoked.is_(False)))
        if pending>=50:
            raise HTTPException(429,"Pending device review queue is full. Contact HR/IT.")
        _auto_registration_times.append(now)
    token=secrets.token_urlsafe(40)
    device=ActivityDevice(employee_id=None,token_hash=hashlib.sha256(token.encode()).hexdigest(),
                          device_label=data.device_label,state="pending")
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"device_id":device.id,"token":token,"status":"pending",
            "message":"Pending HR assignment; no activity collection is authorized."}

@router.post("/register",status_code=201)
def register_pending(data:RegisterIn,db:Session=Depends(db_session)):
    hashed=hashlib.sha256(data.invitation_code.encode()).hexdigest()
    invite=db.scalar(select(ActivityInvite).where(ActivityInvite.code_hash==hashed).with_for_update())
    if not invite or invite.used_at is not None:
        raise HTTPException(401,"Invalid or already used device invitation.")
    expiry=invite.expires_at
    if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
    if expiry<=utcnow():raise HTTPException(401,"Device invitation expired. Request a new code from HR.")
    token=secrets.token_urlsafe(40)
    device=ActivityDevice(employee_id=None,token_hash=hashlib.sha256(token.encode()).hexdigest(),
                          device_label=data.device_label,state="pending")
    db.add(device);db.flush()
    invite.used_at=utcnow()
    invite.device_id=device.id
    db.commit()
    return {"device_id":device.id,"token":token,"status":"pending",
            "message":"Registration received. HR must assign this device before activity collection."}

def authenticated_device(authorization:str|None, db:Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Device token required.")
    token=authorization.removeprefix("Bearer ").strip()
    device=db.scalar(select(ActivityDevice).where(
        ActivityDevice.token_hash==hashlib.sha256(token.encode()).hexdigest(),
        ActivityDevice.revoked.is_(False)))
    if not device:raise HTTPException(401,"Invalid or revoked device token.")
    return device

@router.get("/status")
def device_status(authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
    device=authenticated_device(authorization,db)
    if device.employee_id is None:
        device.last_seen=utcnow()
        db.commit()
        return {"status":"pending","assigned":False}
    return {"status":"assigned","assigned":True}

@router.post("/devices/{device_id}/assign")
def assign_device(device_id:int,data:AssignIn,user:Employee=Depends(current_user),
                  db:Session=Depends(db_session)):
    require_hr(user)
    device=db.get(ActivityDevice,device_id)
    if not device or device.revoked:raise HTTPException(404,"Pending device not found.")
    if device.employee_id is not None:raise HTTPException(409,"Already assigned. Revoke and re-enroll to transfer.")
    employee=db.get(Employee,data.employee_id)
    if not employee or employee.status!="active":raise HTTPException(422,"Select an active employee.")
    device.employee_id=employee.id
    device.state="not_started"
    device.last_seen=None
    db.commit()
    return {"assigned":True,"device_id":device.id,"employee_id":employee.id}

@router.post("/heartbeat")
def heartbeat(data:BeatIn,authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
    device=authenticated_device(authorization,db)
    if device.employee_id is None:raise HTTPException(403,"Device pending employee assignment.")
    if data.state=="stopped" and (not data.exit_reason or len(data.exit_reason.strip())<10):
        raise HTTPException(422,"An exit reason of at least 10 characters is required.")
    device.state=data.state
    device.active_seconds=data.active_seconds
    device.idle_seconds=data.idle_seconds
    if any(not name or len(name)>60 or seconds<0 or seconds>86400 for name,seconds in data.apps.items()):
        raise HTTPException(422,"Invalid application usage summary.")
    device.app_usage_json=json.dumps(data.apps)
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
        status="revoked" if d.revoked else ("pending" if d.employee_id is None else ("monitoring" if online else ("stopped" if d.state=="stopped" else "offline")))
        result.append({"id":d.id,"employee_id":d.employee_id,"employee_name":employees.get(d.employee_id,"Unassigned device"),"device_label":d.device_label,
                       "status":status,"last_seen":seen,
                       "active_seconds":d.active_seconds,"idle_seconds":d.idle_seconds,"apps":json.loads(d.app_usage_json or "{}"),"exit_reason":d.exit_reason if d.state=="stopped" else "","revoked":d.revoked})
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
