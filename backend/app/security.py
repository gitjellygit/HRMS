"""Optional authenticator-app 2FA with encrypted TOTP secrets and replay protection."""
from datetime import datetime, timezone, timedelta
import os
import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from .main import Base, Employee, current_user, db_session, passwords
from .employee_core import seal, unseal

router=APIRouter(prefix="/security",tags=["Account Security"])
def now():return datetime.now(timezone.utc)

class MFAFactor(Base):
    __tablename__="sec_mfa_factors"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    encrypted_secret:Mapped[str]=mapped_column(String(300))
    enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    last_counter:Mapped[int]=mapped_column(Integer,default=-1)

class PasswordIn(BaseModel):
    current_password:str=Field(min_length=1,max_length=256)

class OTPIn(BaseModel):
    code:str=Field(pattern=r"^[0-9]{6}$")

class DisableIn(OTPIn):
    current_password:str=Field(min_length=1,max_length=256)

def check_otp(secret:str,code:str,last_counter:int)->int|None:
    totp=pyotp.TOTP(secret)
    tick=int(now().timestamp())//30
    for candidate in (tick-1,tick,tick+1):
        if candidate>last_counter and totp.at(candidate*30)==code:
            return candidate
    return None

def require_login_mfa(db:Session,employee_id:int,code:str|None):
    row=db.execute(select(MFAFactor).where(MFAFactor.employee_id==employee_id).with_for_update()).scalar_one_or_none()
    if not row or not row.enabled:return
    if not code or len(code)!=6:raise HTTPException(401,"Authenticator code required.")
    counter=check_otp(unseal(row.encrypted_secret),code,row.last_counter)
    if counter is None:raise HTTPException(401,"Invalid or previously used authenticator code.")
    row.last_counter=counter
    db.commit()

@router.get("/mfa")
def status(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(MFAFactor,user.id)
    return {"enabled":bool(row and row.enabled),"pending":bool(row and not row.enabled and
        row.expires_at and row.expires_at>now())}

@router.post("/mfa/setup")
def setup(body:PasswordIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not passwords.verify(body.current_password,user.password_hash):
        raise HTTPException(401,"Current password is incorrect.")
    existing=db.get(MFAFactor,user.id)
    if existing and existing.enabled:raise HTTPException(409,"Authenticator already enabled.")
    if not os.getenv("HRMS_PII_KEY"):raise HTTPException(503,"Secure PII encryption key is required for 2FA enrollment.")
    secret=pyotp.random_base32()
    row=existing or MFAFactor(employee_id=user.id)
    row.encrypted_secret=seal(secret)
    row.enabled=False
    row.expires_at=now()+timedelta(minutes=10)
    row.last_counter=-1
    db.add(row);db.commit()
    return {"secret":secret,"otpauth_uri":pyotp.TOTP(secret).provisioning_uri(
        name=user.email,issuer_name="JellyGit HRMS"),
        "expires_in_seconds":600,
        "message":"Save this setup secret in your authenticator. It will not be displayed again."}

@router.post("/mfa/enable")
def enable(body:OTPIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.execute(select(MFAFactor).where(MFAFactor.employee_id==user.id).with_for_update()).scalar_one_or_none()
    if not row or row.enabled or not row.expires_at or row.expires_at<now():
        raise HTTPException(409,"Start a new 2FA enrollment.")
    counter=check_otp(unseal(row.encrypted_secret),body.code,-1)
    if counter is None:raise HTTPException(422,"Authenticator code is not valid.")
    row.enabled=True;row.last_counter=counter;row.expires_at=None
    db.commit();return {"enabled":True}

@router.post("/mfa/disable")
def disable(body:DisableIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not passwords.verify(body.current_password,user.password_hash):
        raise HTTPException(401,"Current password is incorrect.")
    row=db.execute(select(MFAFactor).where(MFAFactor.employee_id==user.id).with_for_update()).scalar_one_or_none()
    if not row or not row.enabled:raise HTTPException(404,"2FA is not enabled.")
    counter=check_otp(unseal(row.encrypted_secret),body.code,row.last_counter)
    if counter is None:raise HTTPException(422,"Authenticator code is invalid or already used.")
    db.delete(row);db.commit()
    return {"enabled":False}
