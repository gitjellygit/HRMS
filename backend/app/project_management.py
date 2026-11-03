"""Enterprise project records, rate details and generated project numbers."""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Project, Employee, db_session, current_user

router = APIRouter(prefix="/project-management", tags=["Project Management"])
HR_ROLES = {"super_admin", "admin", "hr"}


class ProjectDetail(Base):
    __tablename__ = "project_details"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    project_number: Mapped[str] = mapped_column(String(35), unique=True, index=True)
    candidate_name: Mapped[str] = mapped_column(String(150), default="")
    vendor_name: Mapped[str] = mapped_column(String(150), default="")
    prime_vendor_name: Mapped[str] = mapped_column(String(150), default="")
    engagement_type: Mapped[str] = mapped_column(String(25), default="c2c")
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    rate_unit: Mapped[str] = mapped_column(String(20), default="hour")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    client: str = Field(min_length=2, max_length=120)
    candidate_name: str = Field(default="", max_length=150)
    vendor_name: str = Field(default="", max_length=150)
    prime_vendor_name: str = Field(default="", max_length=150)
    engagement_type: Literal["c2c","w2","full_time","contract_1099","fixed_price"]
    rate: Decimal = Field(gt=0, le=100000000, decimal_places=2)
    currency: Literal["USD","INR","CAD","GBP","EUR","AED","SAR"] = "USD"
    rate_unit: Literal["hour","day","month","year","project"] = "hour"
    description: str = Field(default="", max_length=3000)

    @field_validator("name", "client")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("This field is required.")
        return value


def manage(user: Employee = Depends(current_user)) -> Employee:
    if user.role not in HR_ROLES:
        raise HTTPException(403, "Only administrators and HR can create projects")
    return user


def serialize(project: Project, detail: ProjectDetail | None) -> dict:
    return {"id":project.id, "project_number":detail.project_number if detail else None,
            "name":project.name, "client":project.client, "status":project.status,
            "description":project.description,
            "candidate_name":detail.candidate_name if detail else "",
            "vendor_name":detail.vendor_name if detail else "",
            "prime_vendor_name":detail.prime_vendor_name if detail else "",
            "engagement_type":detail.engagement_type if detail else None,
            "rate":float(detail.rate) if detail else None,
            "currency":detail.currency if detail else None,
            "rate_unit":detail.rate_unit if detail else None}


@router.get("/next-number")
def preview_number(user: Employee = Depends(manage), db: Session = Depends(db_session)):
    number, called = db.execute(text("SELECT last_value, is_called FROM hrms_project_number_seq")).one()
    return {"project_number":f"JG-P-{(number+1 if called else number):04d}", "provisional":True}


@router.get("/projects")
def list_projects(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    projects=db.scalars(select(Project).order_by(Project.id.desc())).all()
    details={d.project_id:d for d in db.scalars(select(ProjectDetail))}
    # Legacy project rows are retained and can be viewed without falsely generated IDs.
    return [serialize(p,details.get(p.id)) for p in projects]


@router.post("/projects",status_code=201)
def create_project(body: ProjectCreate,user: Employee = Depends(manage),db: Session = Depends(db_session)):
    project=Project(name=body.name,client=body.client,description=body.description,status="active")
    db.add(project)
    db.flush()
    # Database nextval guarantees uniqueness even if two users saw the same preview.
    number=db.execute(text("SELECT nextval('hrms_project_number_seq')")).scalar_one()
    detail=ProjectDetail(
        project_id=project.id,project_number=f"JG-P-{number:04d}",
        candidate_name=body.candidate_name.strip(),vendor_name=body.vendor_name.strip(),
        prime_vendor_name=body.prime_vendor_name.strip(),engagement_type=body.engagement_type,
        rate=body.rate,currency=body.currency,rate_unit=body.rate_unit
    )
    db.add(detail)
    db.commit()
    db.refresh(project)
    return serialize(project,detail)


@router.get("/projects/{project_id}")
def get_project(project_id: int,user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    project=db.get(Project,project_id)
    if not project:
        raise HTTPException(404,"Project not found")
    return serialize(project,db.get(ProjectDetail,project_id))
