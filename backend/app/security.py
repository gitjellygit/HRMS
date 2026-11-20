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

class LoginFailure(Base):
    """Persistent account-level lockout across application workers."""
    __tablename__="sec_login_failures"
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),primary_key=True)
    failed_count:Mapped[int]=mapped_column(Integer,default=0)
    locked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    locked_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


MAX_LOGIN_FAILURES=5
LOGIN_LOCK_MINUTES=30


def login_blocked(db:Session, user:Employee)->bool:
    row=db.get(LoginFailure,user.id)
    if row and row.locked_until and row.locked_until>now():
        return True
    return False


def login_failed(db:Session,user:Employee):
    """Call only after a credential failure, not inside an uncommitted transaction."""
    from sqlalchemy import func, select
    from sqlalchemy import text
    from datetime import timedelta
    # Serialize even the first failure, when there is no row yet.
    db.execute(select(func.pg_advisory_xact_lock(93271,user.id)))
    row=db.get(LoginFailure,user.id)
    if row is None:
        row=LoginFailure(employee_id=user.id,failed_count=0)
        db.add(row)
    current=now()
    if row.locked_until and row.locked_until>current:
        db.commit()
        return True
    if row.locked_until and row.locked_until<=current:
        row.failed_count=0
        row.locked_at=None
        row.locked_until=None
    row.failed_count+=1
    if row.failed_count>=MAX_LOGIN_FAILURES:
        row.locked_at=current
        row.locked_until=current+timedelta(minutes=LOGIN_LOCK_MINUTES)
        from .notification_center import add_inbox
        admins=db.scalars(select(Employee).where(
            Employee.status=="active",Employee.role.in_(("super_admin","admin","hr")))).all()
        for admin in admins:
            add_inbox(db,admin.id,"security","Account temporarily locked",
                      f"Account {user.email} was locked after {MAX_LOGIN_FAILURES} unsuccessful sign-in attempts. "
                      f"Lock expires in {LOGIN_LOCK_MINUTES} minutes or can be cleared by an administrator.",
                      "people")
    blocked=bool(row.locked_until and row.locked_until>current)
    db.commit()
    return blocked


def login_succeeded(db:Session,user:Employee):
    row=db.get(LoginFailure,user.id)
    if row and (row.failed_count or row.locked_until):
        row.failed_count=0
        row.locked_at=None
        row.locked_until=None
        db.commit()


@router.get("/login-lockouts")
def list_login_lockouts(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("super_admin","admin","hr"):
        raise HTTPException(403,"HR or Admin only")
    rows=db.scalars(select(LoginFailure).where(LoginFailure.locked_until>now())).all()
    staff={e.id:e.email for e in db.scalars(select(Employee).where(
        Employee.id.in_([r.employee_id for r in rows]))).all()}
    return [{"employee_id":r.employee_id,"email":staff.get(r.employee_id,""),
             "failed_attempts":r.failed_count,"locked_until":r.locked_until} for r in rows]


@router.post("/login-lockouts/{employee_id}/unlock")
def unlock_login(employee_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("super_admin","admin","hr"):
        raise HTTPException(403,"HR or Admin only")
    target=db.get(Employee,employee_id)
    if target is None:raise HTTPException(404,"Employee not found")
    from .employee_core import protect_privileged_target, LifecycleEvent
    protect_privileged_target(user,target)
    row=db.get(LoginFailure,employee_id)
    if row is None or row.locked_until is None or row.locked_until<=now():
        raise HTTPException(409,"Account does not have an active login lock")
    row.failed_count=0
    row.locked_at=None
    row.locked_until=None
    db.add(LifecycleEvent(employee_id=employee_id,event="login_unlocked",
                          note="Login unlocked by HR/Admin after failed attempts",
                          effective_date=now().date(),performed_by=user.id))
    from .notification_center import add_inbox
    add_inbox(db,employee_id,"security","Account unlocked",
              "HR has cleared the failed-login lock for your account.","profile")
    db.commit()
    return {"employee_id":employee_id,"unlocked":True}


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
