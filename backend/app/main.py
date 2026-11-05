"""Small-team HRMS API. Keep all HR/admin checks server-side."""
import enum
import os
import secrets
import hashlib
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4
import re
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, status, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://hrms:hrms@localhost:5432/hrms")
SECRET = os.environ.get("JWT_SECRET", "")
if len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
COOKIE_NAME = 'hrms_session'
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', '/app/uploads'))

class Base(DeclarativeBase):
    pass

class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="employee")
    designation: Mapped[str] = mapped_column(String(100), default="")
    department: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    joining_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(20), default="active")
    must_change_password: Mapped[bool] = mapped_column(default=False)

class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    punch_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    punch_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Leave(Base):
    __tablename__ = "leaves"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    client: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(30), default="active")
    description: Mapped[str] = mapped_column(Text, default="")

class Assignment(Base):
    __tablename__ = "project_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)

class Bonus(Base):
    __tablename__ = "bonuses"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    period: Mapped[str] = mapped_column(String(7))
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")

class Appraisal(Base):
    __tablename__ = "appraisals"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    period: Mapped[str] = mapped_column(String(50))
    rating: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text, default="")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    document_type: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(255))
    # Metadata only for MVP. File upload/download requires protected object storage.


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(40), default="")
    work_location: Mapped[str] = mapped_column(String(100), default="")
    employment_type: Mapped[str] = mapped_column(String(40), default="Full time")
    manager_name: Mapped[str] = mapped_column(String(120), default="")
    emergency_contact: Mapped[str] = mapped_column(String(100), default="")
    availability: Mapped[str] = mapped_column(String(25), default="available")
    photo_key: Mapped[str] = mapped_column(String(80), default="")

class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False
    otp: str | None = Field(default=None,pattern=r"^[0-9]{6}$")

class ResetRequestIn(BaseModel):
    email: EmailStr

class ResetConfirmIn(BaseModel):
    token: str
    password: str = Field(min_length=12, max_length=256)

class ProfileIn(BaseModel):
    employee_code: str = Field(default='', max_length=40)
    work_location: str = Field(default='', max_length=100)
    employment_type: str = Field(default='Full time', max_length=40)
    manager_name: str = Field(default='', max_length=120)
    emergency_contact: str = Field(default='', max_length=100)

class EmployeeIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str = "employee"
    designation: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    phone: str = Field(default="", max_length=30)
    employee_code: str = Field(default="", max_length=40)
    work_location: str = ""
    employment_type: str = "Full time"
    manager_name: str = ""
    emergency_contact: str = ""
    joining_date: date = Field(default_factory=date.today)

    @field_validator("name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned.split()) < 2 or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", cleaned):
            raise ValueError("Enter first and last name using letters.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value) or not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("Use an uppercase letter, lowercase letter, number and special character.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = re.sub(r"[\s()-]", "", value)
        if cleaned and not re.fullmatch(r"(?:\+91|91)?[6-9][0-9]{9}", cleaned):
            raise ValueError("Enter an Indian mobile number (10 digits starting 6–9, optional +91).")
        return ("+91" + cleaned[-10:]) if cleaned else ""

class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str = ""
    name: str
    email: EmailStr
    role: str
    designation: str
    department: str
    phone: str
    joining_date: date
    status: str

class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    punch_in: datetime
    punch_out: datetime | None

class LeaveIn(BaseModel):
    leave_type: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    reason: str = ""

class LeaveOut(LeaveIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    status: str

class StatusIn(BaseModel):
    status: str

class ProjectIn(BaseModel):
    name: str = Field(min_length=1)
    client: str = ""
    description: str = ""

class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str

class AssignmentIn(BaseModel):
    project_id: int
    employee_id: int

class BonusIn(BaseModel):
    employee_id: int
    amount: Decimal = Field(gt=0)
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    reason: str = ""

class BonusOut(BonusIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str

class AppraisalIn(BaseModel):
    employee_id: int
    period: str
    rating: int = Field(ge=1, le=5)
    feedback: str = ""

class AppraisalOut(AppraisalIn):
    model_config = ConfigDict(from_attributes=True)
    id: int

def db_session():
    with SessionLocal() as session:
        yield session

def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_session)):
    try:
        token = credentials.credentials if credentials else request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(status_code=401, detail='Not signed in')
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(Employee, user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="Account unavailable")
    if payload.get("pv") != hashlib.sha256((SECRET + user.password_hash).encode()).hexdigest():
        raise HTTPException(status_code=401, detail="Session expired")
    if user.must_change_password and request.url.path not in ("/me","/auth/change-password","/auth/logout","/auth/my-status"):
        raise HTTPException(status_code=403, detail="Password change required before using HRMS.")
    return user

def require(*roles):
    def dependency(user: Employee = Depends(current_user)):
        if user.role not in roles and not (user.role == "super_admin" and ("admin" in roles or "hr" in roles)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency

def employee_exists(db: Session, employee_id: int):
    user = db.get(Employee, employee_id)
    if not user:
        raise HTTPException(404, "Employee not found")
    return user

app = FastAPI(title="JellyGit HRMS", version="0.1.0")
origins = [x.strip() for x in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])

@app.middleware('http')
async def same_origin_writes(request: Request, call_next):
    if request.method in ('POST','PATCH','PUT','DELETE') and request.cookies.get(COOKIE_NAME):
        origin = request.headers.get('origin')
        if origin not in origins:
            return Response(status_code=403, content='Forbidden origin')
    return await call_next(request)

@app.on_event("startup")
def initialize():
    Base.metadata.create_all(engine)  # replace with Alembic migrations before production
    # Separate sequence excludes the initial administrator and is safe for concurrent creates.
    with engine.begin() as connection:
        connection.execute(text("CREATE SEQUENCE IF NOT EXISTS hrms_employee_code_seq START WITH 1"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_hrms_employee_code ON employee_profiles (employee_code) WHERE employee_code <> ''"))
        existing_codes = connection.execute(text("SELECT employee_code FROM employee_profiles WHERE employee_code LIKE 'JG-%'")).scalars().all()
        existing = max((int(code[3:]) for code in existing_codes if code[3:].isdigit()), default=0)
        last, called = connection.execute(text("SELECT last_value, is_called FROM hrms_employee_code_seq")).one()
        if existing > (last if called else last - 1):
            connection.execute(text("SELECT setval('hrms_employee_code_seq', :number, true)"), {"number": existing})
    with engine.begin() as connection:
        connection.execute(text("CREATE SEQUENCE IF NOT EXISTS hrms_project_number_seq START WITH 1"))
        used_numbers = connection.execute(text("SELECT project_number FROM project_details")).scalars().all()
        highest = max((int(code[5:]) for code in used_numbers
                       if code.startswith("JG-P-") and code[5:].isdigit()), default=0)
        last, called = connection.execute(text("SELECT last_value, is_called FROM hrms_project_number_seq")).one()
        if highest > (last if called else last-1):
            connection.execute(text("SELECT setval('hrms_project_number_seq', :number, true)"), {"number":highest})
    # Additive local schema upgrade for existing project_details installations.
    # A proper Alembic migration is required before production release.
    with engine.begin() as connection:
        for field,ddl in [
            ("sourced_by_id","INTEGER REFERENCES employees(id)"),
            ("start_date","DATE"),
            ("bonus_amount_inr","NUMERIC(12,2) NOT NULL DEFAULT 0")]:
            connection.execute(text(f"ALTER TABLE project_details ADD COLUMN IF NOT EXISTS {field} {ddl}"))
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE employee_core ADD COLUMN IF NOT EXISTS project_bonus_inr NUMERIC(12,2)"))
        connection.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false"))
        connection.execute(text("ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS availability VARCHAR(25) NOT NULL DEFAULT 'available'"))
        connection.execute(text("ALTER TABLE employee_profiles ADD COLUMN IF NOT EXISTS photo_key VARCHAR(80) NOT NULL DEFAULT ''"))
    email = os.environ.get("ADMIN_EMAIL")
    passwd = os.environ.get("ADMIN_PASSWORD")
    if email and passwd and len(passwd) >= 12:
        with SessionLocal() as db:
            if not db.scalar(select(Employee).where(Employee.email == email)):
                db.add(Employee(name="HRMS Admin", email=email, password_hash=passwords.hash(passwd), role="admin", designation="Administrator"))
                db.commit()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(db_session)):
    user = db.scalar(select(Employee).where(Employee.email == str(body.email)))
    if not user or user.status != "active" or not passwords.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    from .security import require_login_mfa
    require_login_mfa(db,user.id,body.otp)
    lifetime = timedelta(days=30) if body.remember else timedelta(hours=8)
    token = jwt.encode({"sub": str(user.id), "pv": hashlib.sha256((SECRET + user.password_hash).encode()).hexdigest(), "exp": datetime.now(timezone.utc) + lifetime}, SECRET, algorithm="HS256")
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE, samesite='lax', max_age=int(lifetime.total_seconds()) if body.remember else None, path='/')
    return {"user": {**EmployeeOut.model_validate(user).model_dump(mode="json"),"must_change_password":user.must_change_password}}

@app.get("/me")
def me(user: Employee = Depends(current_user)):
    return {**EmployeeOut.model_validate(user).model_dump(mode="json"),"must_change_password":user.must_change_password}

class AvailabilityIn(BaseModel):
    status: Literal["available","busy","away","do_not_disturb"]


def own_profile(db:Session,user:Employee)->EmployeeProfile:
    row=db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id==user.id))
    if not row:
        row=EmployeeProfile(employee_id=user.id)
        db.add(row);db.flush()
    return row


@app.get("/me/presence")
def get_presence(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id==user.id))
    return {"status":row.availability if row else "available","has_photo":bool(row and row.photo_key)}


@app.put("/me/presence")
def update_presence(body:AvailabilityIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=own_profile(db,user)
    row.availability=body.status
    db.commit()
    return {"status":row.availability}


@app.post("/me/photo")
async def upload_my_photo(photo:UploadFile=File(...),user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    content=await photo.read(2*1024*1024+1)
    if len(content)>2*1024*1024:
        raise HTTPException(413,"Profile photo must be smaller than 2 MB.")
    png=content.startswith(bytes.fromhex("89504e470d0a1a0a"))
    jpeg=content.startswith(bytes.fromhex("ffd8ff"))
    if not png and not jpeg:
        raise HTTPException(415,"Only PNG and JPEG profile photos are supported.")
    ext=".png" if png else ".jpg"
    folder=UPLOAD_DIR/"avatars"
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    key=uuid4().hex+ext
    filepath=folder/key
    with filepath.open("xb") as handle:
        handle.write(content)
    filepath.chmod(0o600)
    row=own_profile(db,user)
    old=row.photo_key
    row.photo_key=key
    db.commit()
    if old:
        (folder/Path(old).name).unlink(missing_ok=True)
    return {"has_photo":True}


@app.get("/me/photo")
def my_photo(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id==user.id))
    if not row or not row.photo_key:
        raise HTTPException(404,"No profile photo")
    path=UPLOAD_DIR/"avatars"/Path(row.photo_key).name
    if not path.is_file():
        raise HTTPException(404,"Profile photo is unavailable")
    return FileResponse(path,media_type="image/png" if path.suffix==".png" else "image/jpeg",
                        headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})


@app.get("/dashboard")
def dashboard(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    from .project_management import ProjectDetail
    privileged = user.role in ("super_admin","admin","hr")
    total = db.scalar(select(func.count()).select_from(Employee).where(Employee.status=="active")) if privileged else None
    pending = db.scalar(select(func.count()).select_from(Leave).where(Leave.status=="pending")) if privileged else None
    query=select(func.count()).select_from(Project).where(Project.status=="active")
    if not privileged:
        query=query.join(ProjectDetail,ProjectDetail.project_id==Project.id).where(ProjectDetail.sourced_by_id==user.id)
    active_projects=db.scalar(query)
    mine=db.scalar(select(func.count()).select_from(Leave).where(Leave.employee_id==user.id,Leave.status=="pending"))
    return {"employees":total,"pending_leaves":pending,"active_projects":active_projects,"my_pending_leaves":mine}



def as_employee_out(db: Session, employee: Employee) -> EmployeeOut:
    profile = db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id == employee.id))
    return EmployeeOut.model_validate(employee).model_copy(update={"employee_code": profile.employee_code if profile else ""})

def employee_code_value(db: Session, supplied: str = "") -> str:
    db.execute(select(func.pg_advisory_xact_lock(74001, 1)))
    code = supplied.strip().upper()
    if code:
        if not re.fullmatch(r"JG-[0-9]{3,9}", code):
            raise HTTPException(422, detail={"field":"employee_code","message":"Use JG-001 format (3–9 digits)."})
        if db.scalar(select(EmployeeProfile.employee_id).where(EmployeeProfile.employee_code == code)):
            raise HTTPException(409, detail={"field":"employee_code","message":"This employee ID is already in use."})
        number = int(code[3:])
        last, called = db.execute(text("SELECT last_value, is_called FROM hrms_employee_code_seq")).one()
        if number > (last if called else last-1):
            db.execute(text("SELECT setval('hrms_employee_code_seq', :n, true)"),{"n":number})
        return code
    number = db.execute(text("SELECT nextval('hrms_employee_code_seq')")).scalar_one()
    return f"JG-{number:03d}"


@app.post("/employees/generate-code")
def allocate_employee_code(user: Employee = Depends(require("admin","hr")),db: Session = Depends(db_session)):
    code = employee_code_value(db)
    db.commit()
    return {"employee_code":code,"provisional":True}


@app.get("/employees/next-code")
def preview_employee_code(user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    last, used = db.execute(text("SELECT last_value, is_called FROM hrms_employee_code_seq")).one()
    return {"employee_code": f"JG-{(last + 1 if used else last):03d}", "provisional": True}

@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(user: Employee = Depends(require("admin", "hr", "accountant")), db: Session = Depends(db_session)):
    employees = db.scalars(select(Employee).order_by(Employee.id.desc())).all()
    codes = dict(db.execute(select(EmployeeProfile.employee_id, EmployeeProfile.employee_code)).all())
    return [EmployeeOut.model_validate(employee).model_copy(update={"employee_code": codes.get(employee.id, "")}) for employee in employees]

@app.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    if body.role not in ("super_admin", "admin", "hr", "manager", "employee", "accountant"):
        raise HTTPException(422, detail=[{"loc":["body","role"],"msg":"Select a valid access role.","type":"value_error"}])
    if body.role in ("admin", "super_admin") and user.role not in ("super_admin", "admin"):
        raise HTTPException(403, "Only Super Admin can create administrators")
    if db.scalar(select(Employee.id).where(func.lower(Employee.email) == str(body.email).lower())):
        raise HTTPException(409, detail={"field":"email","message":"This work email is already registered."})
    profile_fields = {'work_location','employment_type','manager_name','emergency_contact'}
    employee = Employee(**body.model_dump(exclude={"password","employee_code"} | profile_fields), password_hash=passwords.hash(body.password))
    db.add(employee)
    try:
        db.flush()
        code = employee_code_value(db, body.employee_code)
        db.add(EmployeeProfile(employee_id=employee.id, employee_code=code, **body.model_dump(include=profile_fields)))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail={"field":"email","message":"An employee with these details already exists."}) from exc
    db.refresh(employee)
    return as_employee_out(db, employee)

@app.get("/attendance/status")
def attendance_status(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    open_shift=db.scalar(select(Attendance).where(
        Attendance.employee_id==user.id,Attendance.punch_out.is_(None)
    ).order_by(Attendance.id.desc()))
    return {"checked_in":open_shift is not None,
            "punch_in":open_shift.punch_in if open_shift else None,
            "next_action":"punch_out" if open_shift else "punch_in"}

@app.post("/attendance/punch", response_model=AttendanceOut)
def punch(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    # Calls from /time/punch can pass an approved verified geographic location.
    # The legacy route must not bypass an enabled office geofence.
    from .time_tracking import TimePolicy
    active_policy=db.scalar(select(TimePolicy).where(TimePolicy.location=="all"))
    if active_policy and active_policy.geo_required and not db.info.get("geo_verified"):
        raise HTTPException(403,detail={"field":"location","message":"Use the verified GPS attendance button."})
    # One active punch state per user, even with simultaneous clicks/browser tabs.
    db.execute(select(func.pg_advisory_xact_lock(93001,user.id)))
    open_shift = db.scalar(select(Attendance).where(Attendance.employee_id == user.id, Attendance.punch_out.is_(None)).order_by(Attendance.id.desc()))
    if open_shift:
        open_shift.punch_out = datetime.now(timezone.utc)
        record = open_shift
    else:
        record = Attendance(employee_id=user.id, punch_in=datetime.now(timezone.utc))
        db.add(record)
    db.commit()
    db.refresh(record)
    return record

@app.get("/attendance", response_model=list[AttendanceOut])
def attendance(employee_id: int | None = None, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    target = employee_id if employee_id is not None else user.id
    if target != user.id and user.role not in ("super_admin", "admin", "hr"):
        raise HTTPException(403, "Insufficient permissions")
    return db.scalars(select(Attendance).where(Attendance.employee_id == target).order_by(Attendance.id.desc()).limit(100)).all()

@app.post("/leaves", response_model=LeaveOut, status_code=201)
def apply_leave(body: LeaveIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if body.end_date < body.start_date:
        raise HTTPException(422, "End date must not precede start date")
    leave = Leave(employee_id=user.id, **body.model_dump())
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

@app.get("/leaves", response_model=list[LeaveOut])
def leaves(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    query = select(Leave).order_by(Leave.id.desc())
    if user.role not in ("admin", "hr"):
        query = query.where(Leave.employee_id == user.id)
    return db.scalars(query.limit(200)).all()

@app.patch("/leaves/{leave_id}", response_model=LeaveOut)
def review_leave(leave_id: int, body: StatusIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    if body.status not in ("approved", "rejected"):
        raise HTTPException(422, "Invalid status")
    leave = db.get(Leave, leave_id)
    if not leave:
        raise HTTPException(404, "Leave not found")
    leave.status = body.status
    db.commit()
    db.refresh(leave)
    return leave

@app.get("/projects", response_model=list[ProjectOut])
def projects(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    from .project_management import ProjectDetail
    query=select(Project).order_by(Project.id.desc())
    if user.role not in ("super_admin","admin","hr"):
        query=query.join(ProjectDetail,ProjectDetail.project_id==Project.id).where(ProjectDetail.sourced_by_id==user.id)
    return db.scalars(query).all()

@app.post("/projects", response_model=ProjectOut, status_code=201)
def add_project(body: ProjectIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    record = Project(**body.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@app.post("/projects/assign", status_code=201)
def assign(body: AssignmentIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    employee_exists(db, body.employee_id)
    if not db.get(Project, body.project_id):
        raise HTTPException(404, "Project not found")
    exists = db.scalar(select(Assignment).where(Assignment.project_id == body.project_id, Assignment.employee_id == body.employee_id))
    if exists:
        raise HTTPException(409, "Already assigned")
    db.add(Assignment(**body.model_dump()))
    db.commit()
    return {"ok": True}

@app.get("/projects/{project_id}/team", response_model=list[EmployeeOut])
def project_team(project_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    from .project_management import ProjectDetail
    detail=db.get(ProjectDetail,project_id)
    if user.role not in ("super_admin","admin","hr") and (not detail or detail.sourced_by_id!=user.id):
        raise HTTPException(404,"Project not found")
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    return db.scalars(select(Employee).join(Assignment, Assignment.employee_id == Employee.id).where(Assignment.project_id == project_id)).all()

@app.get("/bonuses", response_model=list[BonusOut])
def bonuses(user: Employee = Depends(require("admin", "hr", "accountant")), db: Session = Depends(db_session)):
    return db.scalars(select(Bonus).order_by(Bonus.id.desc())).all()

@app.post("/bonuses", response_model=BonusOut, status_code=201)
def add_bonus(body: BonusIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    employee_exists(db, body.employee_id)
    row = Bonus(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.patch("/bonuses/{bonus_id}", response_model=BonusOut)
def change_bonus(bonus_id: int, body: StatusIn, user: Employee = Depends(require("admin", "accountant")), db: Session = Depends(db_session)):
    if body.status not in ("approved", "paid"):
        raise HTTPException(422, "Invalid status")
    row = db.get(Bonus, bonus_id)
    if not row:
        raise HTTPException(404, "Bonus not found")
    if body.status == "paid" and row.status != "approved":
        raise HTTPException(409, "Bonus must be approved first")
    if row.status == "paid":
        raise HTTPException(409, "Already paid")
    row.status = body.status
    db.commit()
    db.refresh(row)
    return row

@app.get("/appraisals", response_model=list[AppraisalOut])
def appraisals(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    query = select(Appraisal).order_by(Appraisal.id.desc())
    if user.role not in ("super_admin", "admin", "hr"):
        query = query.where(Appraisal.employee_id == user.id)
    return db.scalars(query).all()

@app.post("/appraisals", response_model=AppraisalOut, status_code=201)
def add_appraisal(body: AppraisalIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    employee_exists(db, body.employee_id)
    row = Appraisal(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class SelfPasswordChange(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=12,max_length=128)


def validate_new_password(value: str):
    if not all((re.search(r"[A-Z]",value),re.search(r"[a-z]",value),
                re.search(r"[0-9]",value),re.search(r"[^A-Za-z0-9]",value))):
        raise HTTPException(422,"Use uppercase, lowercase, number and special character.")


@app.post("/auth/change-password")
def change_my_password(body: SelfPasswordChange,response:Response,
                       user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if not user.must_change_password and (
        not body.current_password or not passwords.verify(body.current_password,user.password_hash)):
        raise HTTPException(401,"Current password is incorrect")
    validate_new_password(body.new_password)
    if passwords.verify(body.new_password,user.password_hash):
        raise HTTPException(422,"Choose a new password different from your previous one.")
    user.password_hash=passwords.hash(body.new_password)
    user.must_change_password=False
    db.commit()
    response.delete_cookie(COOKIE_NAME,path="/",secure=COOKIE_SECURE,httponly=True,samesite="lax")
    return {"message":"Password successfully changed. Please sign in again with your new password."}


@app.get("/auth/my-status")
def my_auth_status(user:Employee=Depends(current_user)):
    return {"must_change_password":user.must_change_password}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path='/', secure=COOKIE_SECURE, httponly=True, samesite='lax')
    return {"ok": True}

def send_reset_mail(destination: str, link: str):
    host = os.getenv('SMTP_HOST')
    username = os.getenv('SMTP_USER')
    sender = os.getenv('SMTP_FROM')
    if not host or not sender:
        raise HTTPException(503, "Password reset email is not configured")
    message = EmailMessage()
    message['Subject'] = 'Reset your JellyGit HRMS password'
    message['From'] = sender
    message['To'] = destination
    message.set_content(f"Someone requested a password reset for your JellyGit HRMS account.\n\nOpen this link within 30 minutes:\n{link}\n\nIf this wasn't you, ignore this email.")
    try:
        port = int(os.getenv('SMTP_PORT', '587'))
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if username:
                smtp.login(username, os.getenv('SMTP_PASSWORD', ''))
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(503, 'Unable to send reset email; check SMTP configuration') from exc

@app.post("/auth/forgot-password")
def forgot_password(body: ResetRequestIn, db: Session = Depends(db_session)):
    # Same response for registered and unregistered email addresses.
    user = db.scalar(select(Employee).where(Employee.email == str(body.email), Employee.status == 'active'))
    if user:
        recent = db.scalar(select(PasswordReset).where(PasswordReset.employee_id == user.id).order_by(PasswordReset.id.desc()))
        if recent and recent.expires_at > datetime.now(timezone.utc) + timedelta(minutes=25):
            return {"message": "If the email is registered, a password reset link has been sent."}
        token = secrets.token_urlsafe(32)
        record = PasswordReset(employee_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
        db.add(record)
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
        send_reset_mail(user.email, base_url + '/?reset=' + token)
        db.commit()
    return {"message": "If the email is registered, a password reset link has been sent."}

@app.post("/auth/reset-password")
def reset_password(body: ResetConfirmIn, db: Session = Depends(db_session)):
    digest = hashlib.sha256(body.token.encode()).hexdigest()
    item = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == digest).with_for_update())
    now = datetime.now(timezone.utc)
    if not item or item.used_at is not None or item.expires_at < now:
        raise HTTPException(400, 'Invalid or expired reset link')
    user = employee_exists(db, item.employee_id)
    if user.status != 'active':
        raise HTTPException(400, 'Invalid or expired reset link')
    user.password_hash = passwords.hash(body.password)
    for reset in db.scalars(select(PasswordReset).where(PasswordReset.employee_id == user.id, PasswordReset.used_at.is_(None))).all():
        reset.used_at = now
    db.commit()
    return {"ok": True}

@app.get("/employees/{employee_id}/profile", response_model=ProfileIn)
def employee_profile(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if employee_id != user.id and user.role not in ('super_admin','admin','hr'):
        raise HTTPException(403, 'Insufficient permissions')
    employee_exists(db, employee_id)
    row = db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id == employee_id))
    return ProfileIn.model_validate(row, from_attributes=True) if row else ProfileIn()

@app.patch("/employees/{employee_id}/profile", response_model=ProfileIn)
def edit_employee_profile(employee_id: int, body: ProfileIn, user: Employee = Depends(require('admin','hr')), db: Session = Depends(db_session)):
    employee_exists(db, employee_id)
    row = db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id == employee_id))
    if not row:
        row = EmployeeProfile(employee_id=employee_id)
        db.add(row)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return body

@app.post("/employees/{employee_id}/documents", status_code=201)
async def upload_document(employee_id: int, document: UploadFile = File(...),
                          user: Employee = Depends(require('admin','hr')), db: Session = Depends(db_session)):
    employee_exists(db, employee_id)
    raw = await document.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Maximum file size is 5 MB')
    allowed = raw.startswith(b'%PDF-') or raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff')
    if not allowed:
        raise HTTPException(415, 'Only PDF, PNG and JPEG files are supported')
    suffix = '.pdf' if raw.startswith(b'%PDF-') else '.png' if raw.startswith(b'\x89PNG') else '.jpg'
    key = uuid4().hex + suffix
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = UPLOAD_DIR / key
    with path.open('xb') as fp:
        fp.write(raw)
    path.chmod(0o600)
    row = Document(employee_id=employee_id, name=(document.filename or 'Document')[:150], document_type=suffix[1:], storage_key=key)
    db.add(row)
    db.commit()
    return {"id":row.id, "name":row.name}

@app.get("/employees/{employee_id}/documents")
def list_documents(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if employee_id != user.id and user.role not in ('admin','hr'):
        raise HTTPException(403, 'Insufficient permissions')
    employee_exists(db, employee_id)
    return [{"id":d.id,"name":d.name,"type":d.document_type} for d in db.scalars(select(Document).where(Document.employee_id == employee_id)).all()]

@app.get("/documents/{document_id}")
def download_document(document_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    from fastapi.responses import FileResponse
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, 'Document not found')
    if doc.employee_id != user.id and user.role not in ('admin','hr'):
        raise HTTPException(403, 'Insufficient permissions')
    path = UPLOAD_DIR / doc.storage_key
    if not path.is_file():
        raise HTTPException(404, 'Stored document not found')
    return FileResponse(path, media_type={'pdf':'application/pdf','png':'image/png','jpg':'image/jpeg'}.get(doc.document_type,'application/octet-stream'),
                        filename=doc.name, content_disposition_type='attachment')

# Register additive employee-core tables and routes before application startup.
from .employee_core import router as employee_core_router  # noqa: E402
app.include_router(employee_core_router)

# New leave workflows are separate from the legacy /leaves endpoints.
from .leave_management import router as leave_management_router  # noqa: E402
app.include_router(leave_management_router)

# Keep the richer project API separate from the original /projects endpoints.
from .project_management import router as project_management_router  # noqa: E402
app.include_router(project_management_router)


# Milestone reconciliation runs on startup and hourly while the API is running.
# Unique project award records and database advisory locks prevent duplicate awards
# across multiple API instances. Move this to a dedicated worker before production.
import asyncio
import logging

_bonus_sync_task = None

async def _bonus_reconciler():
    from .project_management import sync_matured_bonuses
    while True:
        try:
            await asyncio.to_thread(_bonus_sync_once, sync_matured_bonuses)
        except Exception:
            logging.getLogger(__name__).exception("Project bonus reconciliation failed")
        await asyncio.sleep(3600)

def _bonus_sync_once(sync_function):
    with SessionLocal() as session:
        return sync_function(session)

@app.on_event("startup")
async def start_bonus_reconciler():
    global _bonus_sync_task
    if os.getenv("PROJECT_BONUS_AUTO_SYNC", "true").lower()=="true":
        _bonus_sync_task=asyncio.create_task(_bonus_reconciler())

@app.on_event("shutdown")
async def stop_bonus_reconciler():
    global _bonus_sync_task
    if _bonus_sync_task:
        _bonus_sync_task.cancel()
        try:
            await _bonus_sync_task
        except asyncio.CancelledError:
            pass
        _bonus_sync_task=None

from .time_tracking import router as time_tracking_router  # noqa: E402
app.include_router(time_tracking_router)

from .bonus_policy import router as bonus_policy_router  # noqa: E402
app.include_router(bonus_policy_router)

# Reconcile 90-day probation on startup and hourly. Safe across app replicas:
# rows are locked during transitions, with a single lifecycle event per change.
_probation_task = None

def _sync_probation_once():
    from .employee_core import sync_probation_periods
    with SessionLocal() as session:
        return sync_probation_periods(session)

async def _probation_reconciler():
    while True:
        try:
            await asyncio.to_thread(_sync_probation_once)
        except Exception:
            logging.getLogger(__name__).exception("Probation reconciliation failed")
        await asyncio.sleep(3600)

@app.on_event("startup")
async def start_probation_sync():
    global _probation_task
    _probation_task = asyncio.create_task(_probation_reconciler())

@app.on_event("shutdown")
async def stop_probation_sync():
    global _probation_task
    if _probation_task:
        _probation_task.cancel()
        try:
            await _probation_task
        except asyncio.CancelledError:
            pass
        _probation_task = None

# New salary/expense tables are registered before application startup.
from .payroll import router as payroll_router  # noqa: E402
app.include_router(payroll_router)

from .people_operations import router as people_operations_router  # noqa: E402
app.include_router(people_operations_router)

from .security import router as security_router  # noqa: E402
app.include_router(security_router)

from .performance_growth import router as performance_growth_router  # noqa: E402
app.include_router(performance_growth_router)

from .performance_extensions import router as performance_extensions_router  # noqa: E402
app.include_router(performance_extensions_router)

from .people_ops_extensions import router as people_ops_extensions_router  # noqa: E402
app.include_router(people_ops_extensions_router)

from .project_finance import router as project_finance_router  # noqa: E402
app.include_router(project_finance_router)

from .governance import router as governance_router  # noqa: E402
app.include_router(governance_router)

from .billing_reviews import router as billing_reviews_router  # noqa: E402
app.include_router(billing_reviews_router)
