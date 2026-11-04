"""Employee core (roadmap 1-10). Restricted HR data and workflow endpoints.

Tables are additive: existing employee and document records remain intact.
"""
import csv
import io
import os
import re
import secrets
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from pwdlib import PasswordHash

from .main import (
    Base, Employee, EmployeeProfile, Document, Attendance, Leave, db_session, current_user,
    EmployeeIn, EmployeeOut, passwords, as_employee_out
)

router = APIRouter(prefix="/core", tags=["Employee Core"])
ADMIN = ("super_admin", "admin", "hr")
ADMIN_ROLES = ("super_admin", "admin")
SENSITIVE = ("bank_account", "bank_ifsc", "pan", "aadhaar", "uan")
UNIT_KINDS = ("department", "designation", "grade", "branch", "cost_center")
STATES = ("probation", "confirmed", "transferred", "promoted", "exited")
MAX_FILE = 5 * 1024 * 1024
# Compatibility: old accounts use admin; super_admin is the new privileged role.


class OrgUnit(Base):
    __tablename__ = "org_units"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(35))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("kind", "code", name="uq_org_unit_kind_code"),)


class EmployeeCore(Base):
    __tablename__ = "employee_core"
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    hod_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    designation_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    personal_email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    emergency_name: Mapped[str] = mapped_column(String(120), default="")
    emergency_phone: Mapped[str] = mapped_column(String(30), default="")
    bank_account: Mapped[str] = mapped_column(Text, default="")
    bank_ifsc: Mapped[str] = mapped_column(Text, default="")
    pan: Mapped[str] = mapped_column(Text, default="")
    aadhaar: Mapped[str] = mapped_column(Text, default="")
    uan: Mapped[str] = mapped_column(Text, default="")
    lifecycle: Mapped[str] = mapped_column(String(30), default="probation")
    project_bonus_inr: Mapped[Decimal | None] = mapped_column(Numeric(12,2), nullable=True)


class ChangeRequest(Base):
    __tablename__ = "employee_change_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(50))
    proposed: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LifecycleEvent(Base):
    __tablename__ = "employee_lifecycle_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    event: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(500), default="")
    effective_date: Mapped[date] = mapped_column(Date)
    performed_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentMetadata(Base):
    __tablename__ = "employee_document_metadata"
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(40), default="other")
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)


class LeaveEntitlement(Base):
    __tablename__ = "employee_leave_entitlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    leave_type: Mapped[str] = mapped_column(String(40))
    allocated_days: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    __table_args__ = (UniqueConstraint("employee_id", "year", "leave_type", name="uq_employee_leave_entitlement"),)


class LeaveEntitlementIn(BaseModel):
    employee_id: int
    year: int = Field(ge=2020, le=2100)
    leave_type: Literal["Annual", "Sick", "Casual", "Unpaid"]
    allocated_days: Decimal = Field(ge=0, le=365)


class UnitIn(BaseModel):
    kind: Literal["department", "designation", "grade", "branch", "cost_center"]
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=1, max_length=35)


class MasterIn(BaseModel):
    project_bonus_inr: Decimal | None = Field(default=None, ge=0, le=100000000, decimal_places=2)
    manager_id: int | None = None
    hod_id: int | None = None
    department_id: int | None = None
    designation_id: int | None = None
    grade_id: int | None = None
    branch_id: int | None = None
    cost_center_id: int | None = None
    date_of_birth: date | None = None
    personal_email: EmailStr | None = None
    address: str = Field(default="", max_length=1000)
    emergency_name: str = Field(default="", max_length=120)
    emergency_phone: str = Field(default="", max_length=30)
    bank_account: str = Field(default="", max_length=30)
    bank_ifsc: str = Field(default="", max_length=11)
    pan: str = Field(default="", max_length=10)
    aadhaar: str = Field(default="", max_length=12)
    uan: str = Field(default="", max_length=12)

    @field_validator("pan")
    @classmethod
    def pan_format(cls, value: str) -> str:
        value = value.upper().strip()
        if value and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value):
            raise ValueError("PAN must have five letters, four digits, one letter.")
        return value

    @field_validator("aadhaar")
    @classmethod
    def aadhaar_format(cls, value: str) -> str:
        value = re.sub(r"\s", "", value)
        if value and not re.fullmatch(r"[2-9][0-9]{11}", value):
            raise ValueError("Aadhaar must be 12 digits, beginning with 2-9.")
        return value

    @field_validator("uan")
    @classmethod
    def uan_format(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]{12}", value):
            raise ValueError("UAN must be 12 digits.")
        return value

    @field_validator("bank_ifsc")
    @classmethod
    def ifsc_format(cls, value: str) -> str:
        value = value.upper().strip()
        if value and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value):
            raise ValueError("Enter a valid 11-character IFSC.")
        return value

    @field_validator("bank_account")
    @classmethod
    def account_format(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]{6,30}", value):
            raise ValueError("Bank account must contain 6-30 digits.")
        return value


class EmployeeCreateIn(BaseModel):
    account: EmployeeIn
    master: MasterIn = Field(default_factory=MasterIn)


class ChangeIn(BaseModel):
    field_name: Literal["personal_email", "address", "emergency_name", "emergency_phone", "date_of_birth", "bank_account", "bank_ifsc", "pan", "aadhaar", "uan"]
    value: str = Field(max_length=1000)


class DecisionIn(BaseModel):
    approve: bool


class LifecycleIn(BaseModel):
    event: Literal["probation", "confirmed", "transferred", "promoted", "exited"]
    note: str = Field(default="", max_length=500)
    effective_date: date = Field(default_factory=date.today)


def require_hr(user: Employee = Depends(current_user)):
    if user.role not in ADMIN:
        raise HTTPException(403, "HR or administrator permission required")
    return user


def require_admin(user: Employee = Depends(current_user)):
    if user.role not in ADMIN_ROLES:
        raise HTTPException(403, "Super Admin permission required")
    return user


def cipher() -> Fernet:
    key = os.environ.get("HRMS_PII_KEY", "")
    if not key:
        raise HTTPException(503, "PII encryption key is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "PII encryption key is invalid") from exc


def seal(value: str) -> str:
    return cipher().encrypt(value.encode()).decode() if value else ""


def unseal(value: str) -> str:
    if not value:
        return ""
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(503, "Unable to decrypt existing sensitive information") from exc


def employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    return employee


def can_view(user: Employee, employee_id: int, core: EmployeeCore | None = None) -> bool:
    if user.role in ADMIN or user.id == employee_id:
        return True
    return user.role == "manager" and core is not None and core.manager_id == user.id


def validate_relationships(db: Session, employee_id: int, data: MasterIn):
    for key in ("manager_id", "hod_id"):
        target = getattr(data, key)
        if target is not None:
            if target == employee_id:
                raise HTTPException(422, detail={"field": key, "message": "An employee cannot report to themselves."})
            manager = employee_or_404(db, target)
            if manager.status != "active":
                raise HTTPException(422, detail={"field": key, "message": "The selected manager is inactive."})
            if manager.role not in ("manager", "super_admin", "admin", "hr"):
                raise HTTPException(422, detail={"field": key, "message": "Choose a user with Manager, HR or Admin access."})
            # Follow reporting edges, preventing circular chains.
            seen = {employee_id}
            current = target
            while current is not None:
                if current in seen:
                    raise HTTPException(422, detail={"field": key, "message": "This assignment would create a circular reporting hierarchy."})
                seen.add(current)
                row = db.get(EmployeeCore, current)
                current = row.manager_id if row else None
    for field,kind in [("department_id","department"),("designation_id","designation"),("grade_id","grade"),("branch_id","branch"),("cost_center_id","cost_center")]:
        unit_id = getattr(data, field)
        if unit_id is not None:
            unit = db.get(OrgUnit, unit_id)
            if not unit or not unit.active or unit.kind != kind:
                raise HTTPException(422, detail={"field": field, "message": "Select a valid active " + kind.replace("_"," ") + "."})


def apply_master(db: Session, employee_id: int, data: MasterIn):
    validate_relationships(db, employee_id, data)
    row = db.get(EmployeeCore, employee_id)
    if row is None:
        row = EmployeeCore(employee_id=employee_id)
        db.add(row)
    for field,value in data.model_dump(exclude=set(SENSITIVE)).items():
        setattr(row, field, value or "" if field in ("personal_email",) else value)
    for field in SENSITIVE:
        value = getattr(data, field)
        if value:
            setattr(row, field, seal(value))
    return row


def master_dict(row: EmployeeCore | None, *, include_sensitive: bool):
    if not row:
        return {}
    fields = ("manager_id","hod_id","department_id","designation_id","grade_id","branch_id","cost_center_id","date_of_birth","personal_email","address","emergency_name","emergency_phone","lifecycle","project_bonus_inr")
    result = {field: getattr(row, field) for field in fields}
    result["project_bonus_inr"] = float(row.project_bonus_inr) if row.project_bonus_inr is not None else None
    for field in SENSITIVE:
        value = getattr(row, field)
        result[field] = unseal(value) if include_sensitive else ("••••" if value else "")
    return result


def employee_view(db: Session, employee: Employee, user: Employee, *, detailed: bool = True):
    core = db.get(EmployeeCore, employee.id)
    if not can_view(user, employee.id, core):
        raise HTTPException(403, "Employee record access denied")
    result = as_employee_out(db, employee).model_dump(mode="json")
    probation_end=employee.joining_date+timedelta(days=90)
    result["probation_end_date"]=probation_end.isoformat()
    result["probation_days_remaining"]=max(0,(probation_end-date.today()).days) if employee.status=="active" else 0
    result["effective_lifecycle"]=("confirmed" if (core is None or core.lifecycle=="probation") and
                                  employee.status=="active" and date.today()>=probation_end
                                  else core.lifecycle if core else "probation")
    if detailed:
        if user.role == "manager" and user.id != employee.id:
            result["master"] = {"manager_id": core.manager_id if core else None,
                                "hod_id": core.hod_id if core else None,
                                "lifecycle": core.lifecycle if core else None}
        else:
            result["master"] = master_dict(core, include_sensitive=user.role in ADMIN)
    return result


def approved_days(leaves: list[Leave], *, year: int, kind: str) -> float:
    from_date, to_date = date(year, 1, 1), date(year, 12, 31)
    total = 0
    for leave in leaves:
        if leave.leave_type != kind or leave.status != "approved":
            continue
        start, end = max(leave.start_date, from_date), min(leave.end_date, to_date)
        if end >= start:
            total += (end - start).days + 1
    return float(total)


@router.put("/leave-entitlements")
def set_leave_entitlement(body: LeaveEntitlementIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    employee_or_404(db, body.employee_id)
    row = db.scalar(select(LeaveEntitlement).where(
        LeaveEntitlement.employee_id == body.employee_id, LeaveEntitlement.year == body.year,
        LeaveEntitlement.leave_type == body.leave_type).with_for_update())
    if row is None:
        row = LeaveEntitlement(employee_id=body.employee_id, year=body.year, leave_type=body.leave_type, allocated_days=body.allocated_days)
        db.add(row)
    else:
        row.allocated_days = body.allocated_days
    db.commit()
    return {"employee_id":body.employee_id, "year":body.year, "leave_type":body.leave_type, "allocated_days":float(body.allocated_days)}


@router.get("/hr-overview")
def hr_overview(year: int = Query(default=date.today().year, ge=2020, le=2100), user: Employee = Depends(require_hr),
                db: Session = Depends(db_session)):
    employees = db.scalars(select(Employee).order_by(Employee.name)).all()
    entitlements = db.scalars(select(LeaveEntitlement).where(LeaveEntitlement.year == year)).all()
    all_leaves = db.scalars(select(Leave).where(Leave.start_date <= date(year,12,31), Leave.end_date >= date(year,1,1))).all()
    attendance = db.scalars(select(Attendance).where(Attendance.punch_out.is_(None))).all()
    pending_count = sum(1 for leave in all_leaves if leave.status == "pending")
    entitlements_by_employee: dict[int,list[LeaveEntitlement]] = {}
    leaves_by_employee: dict[int,list[Leave]] = {}
    for row in entitlements:
        entitlements_by_employee.setdefault(row.employee_id, []).append(row)
    for row in all_leaves:
        leaves_by_employee.setdefault(row.employee_id, []).append(row)
    open_shifts = {a.employee_id for a in attendance}
    rows = []
    for employee in employees:
        balance = [
            {"leave_type":e.leave_type, "allocated":float(e.allocated_days),
             "used":approved_days(leaves_by_employee.get(employee.id,[]), year=year, kind=e.leave_type),
             "remaining":float(e.allocated_days)-approved_days(leaves_by_employee.get(employee.id,[]), year=year, kind=e.leave_type)}
            for e in entitlements_by_employee.get(employee.id,[])
        ]
        rows.append({"id":employee.id, "name":employee.name, "department":employee.department,
                     "role":employee.role, "status":employee.status,
                     "currently_checked_in":employee.id in open_shifts,
                     "leave_balances":balance})
    return {"year":year, "headcount":len([e for e in employees if e.status == "active"]),
            "pending_leave_requests":pending_count, "currently_checked_in":len(open_shifts), "employees":rows}


@router.get("/roles")
def roles(user: Employee = Depends(current_user)):
    return {
        "roles": ["super_admin", "hr", "manager", "employee", "accountant"],
        "current": user.role,
        "permissions": {
            "super_admin": ["employees:*", "roles:*", "organization:*", "documents:*", "audit:read"],
            "hr": ["employees:create", "employees:read_all", "employees:update", "changes:approve", "documents:manage", "organization:manage"],
            "manager": ["team:read", "self:read", "self:change_request"],
            "employee": ["self:read", "self:change_request"],
            "accountant": ["employees:list_basic"]
        }
    }


@router.get("/units")
def org_units(kind: str | None = None, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    stmt = select(OrgUnit).where(OrgUnit.active.is_(True)).order_by(OrgUnit.kind, OrgUnit.name)
    if kind:
        if kind not in UNIT_KINDS:
            raise HTTPException(422, "Invalid organization category")
        stmt = stmt.where(OrgUnit.kind == kind)
    return [{"id":u.id, "kind":u.kind, "name":u.name, "code":u.code} for u in db.scalars(stmt)]


@router.post("/units", status_code=201)
def create_org_unit(body: UnitIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    name = " ".join(body.name.split())
    code = body.code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,34}", code):
        raise HTTPException(422, detail={"field":"code","message":"Use letters, numbers, hyphens or underscores for the unit code."})
    existing_name = db.scalar(select(OrgUnit.id).where(
        OrgUnit.kind == body.kind, func.lower(OrgUnit.name) == name.lower()))
    if existing_name:
        raise HTTPException(409, detail={"field":"name","message":"This organization unit already exists."})
    row = OrgUnit(kind=body.kind, name=name, code=code)
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An organization unit with that code already exists") from exc
    return {"id":row.id, "kind":row.kind, "name":row.name, "code":row.code}


class UnitUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=1, max_length=35)
    active: bool = True


@router.patch("/units/{unit_id}")
def edit_org_unit(unit_id: int, body: UnitUpdate, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    unit = db.get(OrgUnit, unit_id)
    if not unit:
        raise HTTPException(404, "Organization unit not found")
    unit.name = body.name.strip()
    unit.code = body.code.strip().upper()
    unit.active = body.active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Organization code already exists") from exc
    return {"id":unit.id, "name":unit.name, "code":unit.code, "active":unit.active}


@router.get("/employees")
def employee_directory(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if user.role in ADMIN:
        staff = db.scalars(select(Employee).order_by(Employee.id.desc())).all()
    elif user.role == "manager":
        ids = [r.employee_id for r in db.scalars(select(EmployeeCore).where(EmployeeCore.manager_id == user.id))]
        staff = db.scalars(select(Employee).where(Employee.id.in_(ids + [user.id])).order_by(Employee.name)).all()
    else:
        staff = [user]
    return [employee_view(db, e, user, detailed=False) for e in staff]


@router.get("/employees/{employee_id}")
def get_employee_core(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    return employee_view(db, employee_or_404(db, employee_id), user)


@router.post("/employees", status_code=201)
def create_full_employee(body: EmployeeCreateIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    from .main import EmployeeProfile, employee_code_value
    account = body.account
    if account.role not in ("super_admin","admin","hr","manager","employee","accountant"):
        raise HTTPException(422, "Unknown account role")
    if account.role in ("super_admin", "admin") and user.role not in ADMIN_ROLES:
        raise HTTPException(403, "Only Super Admin may create an administrator")
    if db.scalar(select(Employee.id).where(func.lower(Employee.email) == str(account.email).lower())):
        raise HTTPException(409, detail={"field":"email","message":"This email is already registered."})
    validate_relationships(db, -1, body.master)
    # A selected department ID is the source of truth for the employee's department.
    if body.master.department_id is not None:
        department = db.get(OrgUnit, body.master.department_id)
        account = account.model_copy(update={"department": department.name})
    profile_fields = {"work_location","employment_type","manager_name","emergency_contact"}
    employee = Employee(**account.model_dump(exclude={"password","employee_code"} | profile_fields), password_hash=passwords.hash(account.password))
    db.add(employee)
    try:
        db.flush()
        code = employee_code_value(db, account.employee_code)
        db.add(EmployeeProfile(employee_id=employee.id, employee_code=code, **account.model_dump(include=profile_fields)))
        apply_master(db, employee.id, body.master)
        db.add(LifecycleEvent(employee_id=employee.id, event="probation", note="Employee created", effective_date=account.joining_date, performed_by=user.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Employee creation conflicted with an existing record") from exc
    db.refresh(employee)
    return employee_view(db, employee, user)


@router.put("/employees/{employee_id}")
def update_master(employee_id: int, body: MasterIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    employee_or_404(db, employee_id)
    apply_master(db, employee_id, body)
    db.commit()
    return employee_view(db, employee_or_404(db, employee_id), user)


@router.get("/me")
def self_profile(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    return employee_view(db, user, user)


@router.post("/me/change-requests", status_code=201)
def request_profile_change(body: ChangeIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    value = body.value.strip()
    if body.field_name in SENSITIVE:
        # Validate with the normal master schema before encryption.
        MasterIn.model_validate({body.field_name: value})
        proposed = seal(value)
    else:
        if body.field_name == "date_of_birth":
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise HTTPException(422, "Date must be YYYY-MM-DD") from exc
        if body.field_name == "personal_email" and value:
            MasterIn.model_validate({"personal_email": value})
        proposed = value
    pending = db.scalar(select(ChangeRequest).where(ChangeRequest.employee_id == user.id, ChangeRequest.field_name == body.field_name, ChangeRequest.status == "pending"))
    if pending:
        raise HTTPException(409, "A request for this field is already awaiting HR review")
    row = ChangeRequest(employee_id=user.id, field_name=body.field_name, proposed=proposed)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id":row.id, "status":row.status}


@router.get("/changes")
def list_changes(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    stmt = select(ChangeRequest).order_by(ChangeRequest.id.desc())
    if user.role not in ADMIN:
        stmt = stmt.where(ChangeRequest.employee_id == user.id)
    rows = db.scalars(stmt.limit(200)).all()
    return [{"id":r.id,"employee_id":r.employee_id,"field":r.field_name,"status":r.status,"requested_at":r.requested_at,
             "value": ("Sensitive change" if r.field_name in SENSITIVE else r.proposed)} for r in rows]


@router.post("/changes/{change_id}/review")
def review_change(change_id: int, body: DecisionIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    row = db.scalar(select(ChangeRequest).where(ChangeRequest.id == change_id).with_for_update())
    if not row:
        raise HTTPException(404, "Change request not found")
    if row.status != "pending":
        raise HTTPException(409, "Request already reviewed")
    if row.employee_id == user.id:
        raise HTTPException(403, "You cannot approve your own profile change.")
    if body.approve:
        core = db.get(EmployeeCore, row.employee_id)
        if not core:
            core = EmployeeCore(employee_id=row.employee_id)
            db.add(core)
        value = row.proposed
        if row.field_name == "date_of_birth":
            value = date.fromisoformat(value)
        setattr(core, row.field_name, value)
    row.status = "approved" if body.approve else "rejected"
    row.reviewed_by = user.id
    row.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"id":row.id,"status":row.status}


@router.get("/org-chart")
def org_chart(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    # Public structure to authenticated employees; never include PII.
    staff = db.scalars(select(Employee).where(Employee.status == "active")).all()
    profiles = {p.employee_id:p for p in db.scalars(select(EmployeeProfile))}
    core = {p.employee_id:p for p in db.scalars(select(EmployeeCore))}
    return [{"id":e.id,"name":e.name,"code":profiles[e.id].employee_code if e.id in profiles else "",
             "designation":e.designation,"department":e.department,"manager_id":core[e.id].manager_id if e.id in core else None}
            for e in staff]


@router.get("/employees/{employee_id}/lifecycle")
def lifecycle_history(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    employee_or_404(db, employee_id)
    if user.role not in ADMIN and employee_id != user.id:
        raise HTTPException(403, "Access denied")
    rows = db.scalars(select(LifecycleEvent).where(LifecycleEvent.employee_id == employee_id).order_by(LifecycleEvent.id.desc()))
    return [{"event":r.event,"note":r.note,"date":r.effective_date,"by":r.performed_by} for r in rows]


@router.post("/employees/{employee_id}/lifecycle")
def change_lifecycle(employee_id: int, body: LifecycleIn, user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    employee = employee_or_404(db, employee_id)
    core = db.get(EmployeeCore, employee_id)
    if not core:
        core = EmployeeCore(employee_id=employee_id)
        db.add(core)
    core.lifecycle = body.event
    if body.event == "exited":
        employee.status = "inactive"  # deactivates access immediately
    db.add(LifecycleEvent(employee_id=employee_id, event=body.event, note=body.note, effective_date=body.effective_date, performed_by=user.id))
    db.commit()
    return {"employee_id":employee_id, "lifecycle":body.event}


class DeactivateEmployeeIn(BaseModel):
    reason: str = Field(min_length=10,max_length=500)


class TemporaryPasswordIn(BaseModel):
    reason: str = Field(min_length=10,max_length=500)


def protect_privileged_target(actor: Employee,target:Employee):
    if actor.id==target.id:
        raise HTTPException(403,"You cannot perform this operation on your own account.")
    if target.role in ("super_admin","admin") and actor.role not in ("super_admin","admin"):
        raise HTTPException(403,"Only administrators may manage administrator accounts.")
    if target.role=="super_admin" and actor.role!="super_admin":
        raise HTTPException(403,"Only a Super Admin may manage this account.")


@router.post("/employees/{employee_id}/deactivate")
def deactivate_employee(employee_id:int,body:DeactivateEmployeeIn,user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    target=employee_or_404(db,employee_id)
    protect_privileged_target(user,target)
    if target.status!="active":
        raise HTTPException(409,"Employee is already inactive.")
    target.status="inactive"
    db.add(LifecycleEvent(employee_id=employee_id,event="deactivated",note=body.reason.strip(),
                          effective_date=date.today(),performed_by=user.id))
    db.commit()
    return {"employee_id":employee_id,"status":"inactive","reason_recorded":True}


@router.post("/employees/{employee_id}/reset-password")
def reset_employee_password(employee_id:int,body:TemporaryPasswordIn,user:Employee=Depends(require_hr),db:Session=Depends(db_session)):
    target=employee_or_404(db,employee_id)
    protect_privileged_target(user,target)
    if target.status!="active":
        raise HTTPException(409,"Reactivate the employee before issuing new credentials.")
    import string
    chars=string.ascii_letters+string.digits+"!@#$%&*"
    temporary="".join(secrets.choice(chars) for _ in range(20))
    # Force representative character classes for the password policy.
    temporary="A9!a"+temporary
    target.password_hash=passwords.hash(temporary)
    db.add(LifecycleEvent(employee_id=employee_id,event="password_reset",
                          note="HR-issued temporary password: "+body.reason.strip(),
                          effective_date=date.today(),performed_by=user.id))
    db.commit()
    # No password in logs, DB or email; return once to authorized caller.
    return {"employee_id":employee_id,"temporary_password":temporary,"must_change_on_login":False,
            "message":"Share securely; existing sessions have been invalidated."}


def sync_probation_periods(db:Session)->int:
    due=db.execute(select(EmployeeCore,Employee).join(Employee,Employee.id==EmployeeCore.employee_id).where(
        Employee.status=="active",EmployeeCore.lifecycle=="probation",
        Employee.joining_date<=date.today()-timedelta(days=90))).all()
    count=0
    for core,employee in due:
        core.lifecycle="confirmed"
        db.add(LifecycleEvent(employee_id=employee.id,event="confirmed",
                              note="Automatic confirmation after 90 calendar days from DOJ",
                              effective_date=employee.joining_date+timedelta(days=90),
                              performed_by=employee.id))
        count+=1
    db.commit()
    return count


@router.post("/employees/{employee_id}/documents", status_code=201)
async def upload_document(employee_id: int, category: str = "other", expiry_date: date | None = None,
                          document: UploadFile = File(...), user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    from .main import UPLOAD_DIR
    employee_or_404(db, employee_id)
    if category not in ("offer_letter","id_proof","certificate","contract","other"):
        raise HTTPException(422, "Unknown document type")
    content = await document.read(MAX_FILE + 1)
    if len(content) > MAX_FILE:
        raise HTTPException(413, "Document exceeds 5 MB")
    signature = ".pdf" if content.startswith(b"%PDF-") else ".png" if content.startswith(bytes.fromhex("89504e470d0a1a0a")) else ".jpg" if content.startswith(bytes.fromhex("ffd8ff")) else ""
    if not signature:
        raise HTTPException(415, "Only PDF, PNG and JPEG files are accepted")
    from uuid import uuid4
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = uuid4().hex + signature
    path = UPLOAD_DIR / key
    with path.open("xb") as handle:
        handle.write(content)
    path.chmod(0o600)
    doc = Document(employee_id=employee_id, name=(document.filename or "Document")[:150], document_type=signature[1:], storage_key=key)
    db.add(doc)
    db.flush()
    db.add(DocumentMetadata(document_id=doc.id, category=category, expiry_date=expiry_date, uploaded_by=user.id))
    db.commit()
    return {"id":doc.id,"category":category,"expiry_date":expiry_date}


@router.get("/employees/{employee_id}/documents")
def documents(employee_id: int, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    employee_or_404(db, employee_id)
    if user.role not in ADMIN and employee_id != user.id:
        raise HTTPException(403, "Not permitted to view these documents")
    rows = db.execute(select(Document, DocumentMetadata).outerjoin(DocumentMetadata, DocumentMetadata.document_id == Document.id).where(Document.employee_id == employee_id)).all()
    return [{"id":d.id,"name":d.name,"type":d.document_type,"category":m.category if m else "other",
             "expiry_date":m.expiry_date if m else None} for d,m in rows]


@router.get("/document-alerts")
def document_alerts(days: int = Query(default=30, ge=0, le=365), user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    limit = date.today() + timedelta(days=days)
    rows = db.execute(select(Document, DocumentMetadata).join(DocumentMetadata, DocumentMetadata.document_id == Document.id).where(DocumentMetadata.expiry_date.is_not(None), DocumentMetadata.expiry_date <= limit)).all()
    return [{"document_id":d.id,"employee_id":d.employee_id,"name":d.name,"expiry_date":meta.expiry_date,"category":meta.category} for d,meta in rows]


IMPORT_COLUMNS = ("name","email","designation","department","role","joining_date","phone","manager_email")
def spreadsheet_safe(value):
    text_value = str(value if value is not None else "")
    return "'" + text_value if text_value.startswith(("=", "+", "-", "@", "\t", "\r")) else text_value


@router.get("/employees-export")
def export_employees(format: Literal["csv","xlsx"] = "csv", user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    staff = db.scalars(select(Employee).order_by(Employee.id)).all()
    profiles = {r.employee_id:r for r in db.scalars(select(EmployeeProfile))}
    managers = {r.employee_id:r.manager_id for r in db.scalars(select(EmployeeCore))}
    by_id = {e.id:e.email for e in staff}
    headers = ("employee_id",) + IMPORT_COLUMNS + ("status",)
    rows = [[profiles[e.id].employee_code if e.id in profiles else "", e.name, e.email, e.designation,e.department,e.role,
             e.joining_date.isoformat(),e.phone,by_id.get(managers.get(e.id),"") ,e.status] for e in staff]
    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(headers)
        writer.writerows([[spreadsheet_safe(v) for v in row] for row in rows])
        return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=employees.csv"})
    workbook = Workbook()
    sheet = workbook.active
    sheet.title="Employees"
    sheet.append(headers)
    for row in rows:
        sheet.append([spreadsheet_safe(v) for v in row])
    data=io.BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(data,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=employees.xlsx"})


@router.post("/employees-import")
async def import_employees(document: UploadFile = File(...), dry_run: bool = True,
                           user: Employee = Depends(require_hr), db: Session = Depends(db_session)):
    data = await document.read(2*1024*1024 + 1)
    if len(data)>2*1024*1024:
        raise HTTPException(413, "Maximum import size is 2 MB")
    filename=(document.filename or "").lower()
    if filename.endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
            rows=list(reader)
        except (UnicodeDecodeError,csv.Error) as exc:
            raise HTTPException(422, "Invalid UTF-8 CSV") from exc
    elif filename.endswith(".xlsx"):
        try:
            wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
            sheet=wb.active
            iterator=sheet.iter_rows(values_only=True)
            headers=[str(c or "").strip() for c in next(iterator)]
            rows=[dict(zip(headers,row)) for row in iterator]
        except Exception as exc:
            raise HTTPException(422, "Invalid XLSX workbook") from exc
    else:
        raise HTTPException(415, "Upload a .csv or .xlsx file")
    if len(rows)>500:
        raise HTTPException(422, "Import batches are limited to 500 employees")
    problems=[]
    parsed=[]
    pending_emails=set()
    for index,row in enumerate(rows,start=2):
        try:
            email=str(row.get("email") or "").strip().lower()
            if email in pending_emails or db.scalar(select(Employee.id).where(func.lower(Employee.email)==email)):
                raise ValueError("Duplicate or existing work email")
            pending_emails.add(email)
            manager_email=str(row.get("manager_email") or "").strip().lower()
            manager=db.scalar(select(Employee).where(func.lower(Employee.email)==manager_email)) if manager_email else None
            if manager_email and not manager:
                raise ValueError("Reporting manager email must already exist")
            password=secrets.token_urlsafe(24)
            prepared={**row, "password": password+"Aa1!", "role": row.get("role") or "employee"}
            if not prepared.get("joining_date"):
                prepared.pop("joining_date", None)
            for optional in ("phone","work_location","manager_name","emergency_contact","employment_type"):
                if prepared.get(optional) is None:
                    prepared.pop(optional, None)
            inp=EmployeeIn.model_validate(prepared)
            if inp.role not in ("employee","manager"):
                raise ValueError("Bulk import only supports Employee and Manager roles")
            parsed.append((inp, manager.id if manager else None))
        except Exception as exc:
            problems.append({"row":index,"error":str(exc)[:250]})
    if problems:
        return {"valid":False,"dry_run":dry_run,"row_count":len(rows),"errors":problems,"created":0}
    if dry_run:
        return {"valid":True,"dry_run":True,"row_count":len(rows),"errors":[],"created":0,
                "note":"Imported accounts receive inaccessible random passwords; users must activate via configured password reset email."}
    created=0
    try:
        for inp, manager_id in parsed:
            person=Employee(**inp.model_dump(exclude={"password","employee_code","manager_name","work_location","employment_type","emergency_contact"}),password_hash=passwords.hash(inp.password))
            db.add(person)
            db.flush()
            number=db.execute(text("SELECT nextval('hrms_employee_code_seq')")).scalar_one()
            db.add(EmployeeProfile(employee_id=person.id,employee_code=f"JG-{number:03d}",
                                   manager_name="",work_location="",employment_type="Full time",emergency_contact=""))
            db.add(EmployeeCore(employee_id=person.id,manager_id=manager_id,lifecycle="probation"))
            created+=1
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Import conflicted with existing employees; no rows were imported") from exc
    return {"valid":True,"dry_run":False,"row_count":len(rows),"errors":[],"created":created,
            "note":"Imported users must use password reset to activate access."}
