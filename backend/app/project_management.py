"""Enterprise project records, rate details and generated project numbers."""
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint, Date, Integer, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Project, Employee, Bonus, db_session, current_user

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
    sourced_by_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bonus_amount_inr: Mapped[Decimal] = mapped_column(Numeric(12,2), default=Decimal("0"))


class ProjectBonusAward(Base):
    __tablename__ = "project_bonus_awards"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"),primary_key=True)
    bonus_id: Mapped[int] = mapped_column(ForeignKey("bonuses.id"),unique=True)
    awarded_by_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))


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
    sourced_by_id: int = Field(gt=0)
    start_date: date
    bonus_amount_inr: Decimal = Field(gt=0, le=100000000, decimal_places=2)

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


def bonus_eligibility(detail: ProjectDetail | None) -> tuple[str, date | None]:
    if not detail or not detail.start_date or detail.sourced_by_id is None or not detail.bonus_amount_inr:
        return "not_configured", None
    eligible_on = detail.start_date + timedelta(days=30)
    return ("eligible" if date.today() >= eligible_on else "waiting"), eligible_on


def serialize(project: Project, detail: ProjectDetail | None, awards: set[int] | None = None) -> dict:
    state, eligible_on = bonus_eligibility(detail)
    if awards is not None and project.id in awards:
        state = "awarded"

    return {"id":project.id, "project_number":detail.project_number if detail else None,
            "name":project.name, "client":project.client, "status":project.status,
            "description":project.description,
            "candidate_name":detail.candidate_name if detail else "",
            "vendor_name":detail.vendor_name if detail else "",
            "prime_vendor_name":detail.prime_vendor_name if detail else "",
            "engagement_type":detail.engagement_type if detail else None,
            "rate":float(detail.rate) if detail else None,
            "currency":detail.currency if detail else None,
            "rate_unit":detail.rate_unit if detail else None,
            "sourced_by_id":detail.sourced_by_id if detail else None,
            "start_date":detail.start_date if detail else None,
            "bonus_amount_inr":float(detail.bonus_amount_inr) if detail else None,
            "bonus_eligible_on":eligible_on,"bonus_status":state}


@router.get("/next-number")
def preview_number(user: Employee = Depends(manage), db: Session = Depends(db_session)):
    number, called = db.execute(text("SELECT last_value, is_called FROM hrms_project_number_seq")).one()
    return {"project_number":f"JG-P-{(number+1 if called else number):04d}", "provisional":True}


@router.get("/projects")
def list_projects(user: Employee = Depends(current_user),db: Session = Depends(db_session)):
    projects=db.scalars(select(Project).order_by(Project.id.desc())).all()
    details={d.project_id:d for d in db.scalars(select(ProjectDetail))}
    awards=set(db.scalars(select(ProjectBonusAward.project_id)).all())
    # Legacy project rows are retained and can be viewed without falsely generated IDs.
    return [serialize(p,details.get(p.id),awards) for p in projects]


@router.post("/projects",status_code=201)
def create_project(body: ProjectCreate,user: Employee = Depends(manage),db: Session = Depends(db_session)):
    staff=db.get(Employee,body.sourced_by_id)
    if not staff or staff.status!="active":
        raise HTTPException(422,detail={"field":"sourced_by_id","message":"Select an active employee who sourced this project."})
    project=Project(name=body.name,client=body.client,description=body.description,status="active")
    db.add(project)
    db.flush()
    # Database nextval guarantees uniqueness even if two users saw the same preview.
    number=db.execute(text("SELECT nextval('hrms_project_number_seq')")).scalar_one()
    detail=ProjectDetail(
        project_id=project.id,project_number=f"JG-P-{number:04d}",
        candidate_name=body.candidate_name.strip(),vendor_name=body.vendor_name.strip(),
        prime_vendor_name=body.prime_vendor_name.strip(),engagement_type=body.engagement_type,
        rate=body.rate,currency=body.currency,rate_unit=body.rate_unit,
        sourced_by_id=body.sourced_by_id,start_date=body.start_date,bonus_amount_inr=body.bonus_amount_inr
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
    awarded=db.get(ProjectBonusAward,project_id) is not None
    return serialize(project,db.get(ProjectDetail,project_id),{project_id} if awarded else set())


@router.post("/projects/{project_id}/award-bonus",status_code=201)
def award_bonus(project_id: int,user: Employee = Depends(manage),db: Session = Depends(db_session)):
    # Serialize award attempts; one project may only produce one incentive.
    db.execute(select(func.pg_advisory_xact_lock(83001,project_id)))
    project=db.get(Project,project_id)
    detail=db.get(ProjectDetail,project_id)
    if not project or not detail:
        raise HTTPException(404,"Project details not found")
    if project.status!="active":
        raise HTTPException(409,"Only active projects are eligible for a bonus")
    status,eligible_on=bonus_eligibility(detail)
    if status!="eligible":
        raise HTTPException(409,f"Project is not eligible for its 30-day bonus yet (eligible on {eligible_on}).")
    if db.get(ProjectBonusAward,project_id):
        raise HTTPException(409,"A bonus has already been awarded for this project")
    owner=db.get(Employee,detail.sourced_by_id)
    if not owner or owner.status!="active":
        raise HTTPException(409,"Sourcing employee account is not active")
    bonus=Bonus(employee_id=owner.id,amount=detail.bonus_amount_inr,
                period=eligible_on.strftime("%Y-%m"),
                reason=f"30-day project milestone: {project.name} (#{project_id})",
                status="planned")
    db.add(bonus)
    db.flush()
    db.add(ProjectBonusAward(project_id=project_id,bonus_id=bonus.id,awarded_by_id=user.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"Project bonus already exists") from exc
    return {"project_id":project_id,"bonus_id":bonus.id,"employee_id":owner.id,
            "amount_inr":float(bonus.amount),"status":bonus.status,"eligible_on":eligible_on}


@router.get("/bonuses")
def project_bonuses(user: Employee = Depends(manage),db: Session = Depends(db_session)):
    rows=db.execute(select(ProjectBonusAward,Bonus,Project).join(
        Bonus,Bonus.id==ProjectBonusAward.bonus_id).join(
        Project,Project.id==ProjectBonusAward.project_id).order_by(ProjectBonusAward.project_id.desc())).all()
    return [{"project_id":award.project_id,"project":project.name,"employee_id":bonus.employee_id,
             "amount_inr":float(bonus.amount),"bonus_id":bonus.id,"status":bonus.status}
            for award,bonus,project in rows]
