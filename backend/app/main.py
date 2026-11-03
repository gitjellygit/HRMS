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
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, func, select
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

class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False

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
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12)
    role: str = "employee"
    designation: str = ""
    department: str = ""
    phone: str = ""
    employee_code: str = ''
    work_location: str = ''
    employment_type: str = 'Full time'
    manager_name: str = ''
    emergency_contact: str = ''
    joining_date: date = Field(default_factory=date.today)

class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
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
    return user

def require(*roles):
    def dependency(user: Employee = Depends(current_user)):
        if user.role not in roles:
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
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])

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
    lifetime = timedelta(days=30) if body.remember else timedelta(hours=8)
    token = jwt.encode({"sub": str(user.id), "pv": hashlib.sha256((SECRET + user.password_hash).encode()).hexdigest(), "exp": datetime.now(timezone.utc) + lifetime}, SECRET, algorithm="HS256")
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE, samesite='lax', max_age=int(lifetime.total_seconds()) if body.remember else None, path='/')
    return {"user": EmployeeOut.model_validate(user)}

@app.get("/me", response_model=EmployeeOut)
def me(user: Employee = Depends(current_user)):
    return user

@app.get("/dashboard")
def dashboard(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    total = db.scalar(select(func.count()).select_from(Employee).where(Employee.status == "active")) if user.role in ("admin", "hr", "accountant") else None
    pending = db.scalar(select(func.count()).select_from(Leave).where(Leave.status == "pending")) if user.role in ("admin", "hr") else None
    active_projects = db.scalar(select(func.count()).select_from(Project).where(Project.status == "active"))
    mine = db.scalar(select(func.count()).select_from(Leave).where(Leave.employee_id == user.id, Leave.status == "pending"))
    return {"employees": total, "pending_leaves": pending, "active_projects": active_projects, "my_pending_leaves": mine}

@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(user: Employee = Depends(require("admin", "hr", "accountant")), db: Session = Depends(db_session)):
    return db.scalars(select(Employee).order_by(Employee.name)).all()

@app.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeIn, user: Employee = Depends(require("admin", "hr")), db: Session = Depends(db_session)):
    if body.role not in ("admin", "hr", "employee", "accountant"):
        raise HTTPException(422, "Invalid role")
    if db.scalar(select(Employee).where(Employee.email == str(body.email))):
        raise HTTPException(409, "Email already exists")
    profile_fields = {'employee_code','work_location','employment_type','manager_name','emergency_contact'}
    employee = Employee(**body.model_dump(exclude={"password"} | profile_fields), password_hash=passwords.hash(body.password))
    db.add(employee)
    db.flush()
    db.add(EmployeeProfile(employee_id=employee.id, **body.model_dump(include=profile_fields)))
    db.commit()
    db.refresh(employee)
    return employee

@app.post("/attendance/punch", response_model=AttendanceOut)
def punch(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
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
    if target != user.id and user.role not in ("admin", "hr"):
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
    return db.scalars(select(Project).order_by(Project.id.desc())).all()

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
    if user.role not in ("admin", "hr"):
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
    item.used_at = now
    db.commit()
    return {"ok": True}

@app.get("/employees/{employee_id}/profile", response_model=ProfileIn)
def employee_profile(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if employee_id != user.id and user.role not in ('admin','hr'):
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
