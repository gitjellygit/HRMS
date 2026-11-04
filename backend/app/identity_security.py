"""Opt-in TOTP multifactor authentication for password logins.
No SSO provider is configured: integrations report that honestly.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime,timezone
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import Boolean,ForeignKey,Integer,String,select
from sqlalchemy.orm import Mapped,Session,mapped_column
from .main import Base,Employee,current_user,db_session,passwords
from .employee_core import seal,unseal

router=APIRouter(prefix="/security",tags=["Identity & security"])

class TOTPAccount(Base):
    __tablename__="employee_totp"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    secret_encrypted:Mapped[str]=mapped_column(String(500))
    enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    last_counter:Mapped[int]=mapped_column(Integer,default=-1)

class SetupIn(BaseModel):
    current_password:str=Field(min_length=1)
class VerifyIn(BaseModel):
    code:str=Field(min_length=6,max_length=8)
class DisableIn(BaseModel):
    current_password:str
    code:str=Field(min_length=6,max_length=8)

def totp_counter(secret:str,counter:int)->str:
    raw=base64.b32decode(secret.upper()+"="*((8-len(secret)%8)%8),casefold=True)
    digest=hmac.new(raw,struct.pack(">Q",counter),hashlib.sha1).digest()
    offset=digest[-1]&0xf
    value=(struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%1000000
    return f"{value:06d}"

def verify_totp(secret:str,code:str,last_used:int=-1)->int|None:
    if not code.isdigit() or len(code)!=6:return None
    now_count=int(time.time()//30)
    for counter in (now_count-1,now_count,now_count+1):
        if counter<=last_used:continue
        if hmac.compare_digest(totp_counter(secret,counter),code):return counter
    return None

def login_mfa(db:Session,user:Employee,code:str|None)->None:
    row=db.get(TOTPAccount,user.id)
    if not row or not row.enabled:return
    if not code:raise HTTPException(401,"Authenticator code required")
    try:secret=unseal(row.secret_encrypted)
    except Exception:raise HTTPException(503,"Authenticator configuration error.")
    counter=verify_totp(secret,code,row.last_counter)
    if counter is None:raise HTTPException(401,"Invalid or reused authenticator code")
    row.last_counter=counter
    db.commit()

@router.get("/2fa")
def two_factor_status(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(TOTPAccount,user.id)
    return {"enabled":bool(row and row.enabled),"pending_setup":bool(row and not row.enabled)}

@router.post("/2fa/setup")
def start_two_factor(body:SetupIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not passwords.verify(body.current_password,user.password_hash):raise HTTPException(401,"Current password incorrect")
    row=db.get(TOTPAccount,user.id)
    if row and row.enabled:raise HTTPException(409,"2FA is already active. Disable it before re-enrolling.")
    secret=base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    if not row:row=TOTPAccount(employee_id=user.id,secret_encrypted=seal(secret));db.add(row)
    else:row.secret_encrypted=seal(secret);row.last_counter=-1
    row.enabled=False;db.commit()
    url=f"otpauth://totp/{quote('JellyGit HRMS:'+user.email)}?secret={secret}&issuer={quote('JellyGit HRMS')}&algorithm=SHA1&digits=6&period=30"
    return {"manual_secret":secret,"otpauth_url":url,
            "note":"Store this setup secret privately. Verify a code from your authenticator to activate."}

@router.post("/2fa/verify")
def enable_two_factor(body:VerifyIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(TOTPAccount,user.id)
    if not row:raise HTTPException(404,"Start setup first")
    if row.enabled:raise HTTPException(409,"Already enabled")
    counter=verify_totp(unseal(row.secret_encrypted),body.code)
    if counter is None:raise HTTPException(422,"Code is invalid or expired")
    row.last_counter=counter;row.enabled=True;db.commit()
    return {"enabled":True}

@router.post("/2fa/disable")
def disable_two_factor(body:DisableIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not passwords.verify(body.current_password,user.password_hash):
        raise HTTPException(401,"Current password incorrect")
    row=db.get(TOTPAccount,user.id)
    if not row or not row.enabled:raise HTTPException(404,"2FA is not enabled")
    counter=verify_totp(unseal(row.secret_encrypted),body.code,row.last_counter)
    if counter is None:raise HTTPException(401,"Authenticator code invalid")
    db.delete(row);db.commit()
    return {"enabled":False}
