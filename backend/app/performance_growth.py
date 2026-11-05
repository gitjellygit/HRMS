"""Performance and growth: goals, review cycles and development plans (36–38)."""
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .employee_core import EmployeeCore

router = APIRouter(prefix="/performance", tags=["Performance and growth"])
HR = ("hr", "admin", "super_admin")

def utcnow():
    return datetime.now(timezone.utc)

class Goal(Base):
    __tablename__ = "perf_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class ReviewCycle(Base):
    __tablename__ = "perf_cycles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")

class PerformanceReview(Base):
    __tablename__ = "perf_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("perf_cycles.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    self_notes: Mapped[str] = mapped_column(Text, default="")
    manager_notes: Mapped[str] = mapped_column(Text, default="")
    manager_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id"),)

class DevelopmentPlan(Base):
    __tablename__ = "perf_development_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    skill: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    created_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))

class GoalIn(BaseModel):
    employee_id: int
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(default="", max_length=3000)
    target_date: date

class ProgressIn(BaseModel):
    progress: int = Field(ge=0, le=100)

class CycleIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    start_date: date
    end_date: date

class ReviewIn(BaseModel):
    cycle_id: int
    employee_id: int
    self_notes: str = Field(default="", max_length=5000)

class ManagerReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: str = Field(min_length=10, max_length=5000)

class PlanIn(BaseModel):
    employee_id: int
    skill: str = Field(min_length=2, max_length=120)
    action: str = Field(min_length=5, max_length=3000)
    target_date: date

class PlanStatusIn(BaseModel):
    status: Literal["planned", "in_progress", "completed"]

def can_manage(db: Session, user: Employee, employee_id: int) -> bool:
    if user.role in HR: return True
    if user.role != "manager": return False
    return db.scalar(select(EmployeeCore.employee_id).where(
        EmployeeCore.employee_id == employee_id,
        EmployeeCore.manager_id == user.id)) is not None

def allowed(db: Session, user: Employee, employee_id: int) -> bool:
    return user.id == employee_id or can_manage(db, user, employee_id)

def require_employee(db: Session, employee_id: int):
    employee = db.get(Employee, employee_id)
    if not employee or employee.status != "active":
        raise HTTPException(422, "Active employee required")

def view_goal(g):
    return dict(id=g.id, employee_id=g.employee_id, title=g.title,
                description=g.description, target_date=g.target_date,
                status=g.status, progress=g.progress)

def view_review(r):
    return dict(id=r.id, cycle_id=r.cycle_id, employee_id=r.employee_id,
                self_notes=r.self_notes, manager_notes=r.manager_notes,
                manager_rating=r.manager_rating, status=r.status)

@router.post("/goals", status_code=201)
def add_goal(data: GoalIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    require_employee(db, data.employee_id)
    if not allowed(db, user, data.employee_id):
        raise HTTPException(403, "Not authorized")
    goal = Goal(**data.model_dump(), created_by=user.id)
    db.add(goal); db.commit(); db.refresh(goal)
    return view_goal(goal)

@router.get("/goals")
def goals(employee_id: int | None = None, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    q = select(Goal).order_by(Goal.id.desc())
    if employee_id is not None:
        if not allowed(db, user, employee_id): raise HTTPException(403, "Not authorized")
        q = q.where(Goal.employee_id == employee_id)
    elif user.role not in HR:
        if user.role == "manager":
            team = select(EmployeeCore.employee_id).where(EmployeeCore.manager_id == user.id)
            q = q.where((Goal.employee_id == user.id) | (Goal.employee_id.in_(team)))
        else:
            q = q.where(Goal.employee_id == user.id)
    return [view_goal(g) for g in db.scalars(q).all()]

@router.patch("/goals/{goal_id}/progress")
def update_progress(goal_id: int, data: ProgressIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    goal = db.get(Goal, goal_id)
    if not goal: raise HTTPException(404, "Goal not found")
    if not allowed(db, user, goal.employee_id): raise HTTPException(404, "Goal not found")
    goal.progress = data.progress
    goal.status = "completed" if data.progress == 100 else "in_progress"
    db.commit(); return view_goal(goal)

@router.post("/cycles", status_code=201)
def add_cycle(data: CycleIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if user.role not in HR: raise HTTPException(403, "HR access required")
    if data.end_date < data.start_date: raise HTTPException(422, "End before start")
    if db.scalar(select(ReviewCycle.id).where(ReviewCycle.name == data.name)):
        raise HTTPException(409, "Review cycle already exists")
    cycle = ReviewCycle(**data.model_dump())
    db.add(cycle); db.commit(); db.refresh(cycle)
    return dict(id=cycle.id, name=cycle.name, start_date=cycle.start_date,
                end_date=cycle.end_date, status=cycle.status)

@router.get("/cycles")
def cycles(user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    return [dict(id=c.id, name=c.name, start_date=c.start_date,
                 end_date=c.end_date, status=c.status) for c in db.scalars(select(ReviewCycle)).all()]

@router.post("/reviews", status_code=201)
def add_review(data: ReviewIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    if user.id != data.employee_id: raise HTTPException(403, "Only self-review can be submitted")
    require_employee(db, data.employee_id)
    cycle = db.get(ReviewCycle, data.cycle_id)
    if not cycle or cycle.status != "open": raise HTTPException(422, "Open review cycle required")
    if db.scalar(select(PerformanceReview.id).where(
        PerformanceReview.cycle_id == data.cycle_id,
        PerformanceReview.employee_id == data.employee_id)):
        raise HTTPException(409, "Review already exists")
    review = PerformanceReview(**data.model_dump(), status="self_submitted")
    db.add(review); db.commit(); db.refresh(review)
    return view_review(review)

@router.get("/reviews")
def reviews(employee_id: int | None = None, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    q = select(PerformanceReview).order_by(PerformanceReview.id.desc())
    if employee_id is not None:
        if not allowed(db, user, employee_id): raise HTTPException(403, "Not authorized")
        q = q.where(PerformanceReview.employee_id == employee_id)
    elif user.role not in HR:
        if user.role == "manager":
            team = select(EmployeeCore.employee_id).where(EmployeeCore.manager_id == user.id)
            q = q.where((PerformanceReview.employee_id == user.id) | (PerformanceReview.employee_id.in_(team)))
        else:
            q = q.where(PerformanceReview.employee_id == user.id)
    return [view_review(r) for r in db.scalars(q).all()]

@router.post("/reviews/{review_id}/manager")
def manager_review(review_id: int, data: ManagerReviewIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    review = db.get(PerformanceReview, review_id)
    if not review: raise HTTPException(404, "Review not found")
    if not can_manage(db, user, review.employee_id): raise HTTPException(404, "Review not found")
    if review.status != "self_submitted": raise HTTPException(409, "Employee self-review required")
    review.manager_rating = data.rating; review.manager_notes = data.feedback
    review.reviewed_by = user.id; review.status = "completed"
    db.commit(); return view_review(review)

@router.post("/plans", status_code=201)
def add_plan(data: PlanIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    require_employee(db, data.employee_id)
    if not allowed(db, user, data.employee_id): raise HTTPException(403, "Not authorized")
    plan = DevelopmentPlan(**data.model_dump(), created_by=user.id)
    db.add(plan); db.commit(); db.refresh(plan)
    return dict(id=plan.id, employee_id=plan.employee_id, skill=plan.skill,
                action=plan.action, target_date=plan.target_date, status=plan.status)

@router.get("/plans")
def plans(employee_id: int | None = None, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    q = select(DevelopmentPlan).order_by(DevelopmentPlan.id.desc())
    if employee_id is not None:
        if not allowed(db, user, employee_id): raise HTTPException(403, "Not authorized")
        q = q.where(DevelopmentPlan.employee_id == employee_id)
    elif user.role not in HR:
        if user.role == "manager":
            team = select(EmployeeCore.employee_id).where(EmployeeCore.manager_id == user.id)
            q = q.where((DevelopmentPlan.employee_id == user.id) | (DevelopmentPlan.employee_id.in_(team)))
        else:
            q = q.where(DevelopmentPlan.employee_id == user.id)
    return [dict(id=p.id, employee_id=p.employee_id, skill=p.skill,
                 action=p.action, target_date=p.target_date, status=p.status)
            for p in db.scalars(q).all()]

@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, data: PlanStatusIn, user: Employee = Depends(current_user), db: Session = Depends(db_session)):
    plan = db.get(DevelopmentPlan, plan_id)
    if not plan: raise HTTPException(404, "Plan not found")
    if not allowed(db, user, plan.employee_id): raise HTTPException(404, "Plan not found")
    plan.status = data.status; db.commit()
    return dict(id=plan.id, status=plan.status)
