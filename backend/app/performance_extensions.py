"""Additional growth workflows: confidential peer feedback and career learning."""
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .performance_growth import ReviewCycle, allowed, can_manage, require_employee, HR

router = APIRouter(prefix="/growth", tags=["Learning, career and 360 feedback"])

class FeedbackAssignment(Base):
    __tablename__ = "growth_feedback_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("perf_cycles.id"), index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class LearningTask(Base):
    __tablename__ = "growth_learning_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    provider: Mapped[str] = mapped_column(String(120), default="")
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    created_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))

class CareerMilestone(Base):
    __tablename__ = "growth_career_milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    target_role: Mapped[str] = mapped_column(String(150))
    requirements: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    created_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))

class AssignFeedback(BaseModel):
    employee_id: int
    reviewer_id: int
    cycle_id: int

class SubmitFeedback(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str = Field(min_length=15, max_length=3000)

class AssignLearning(BaseModel):
    employee_id: int
    title: str = Field(min_length=3, max_length=180)
    provider: str = Field(default="", max_length=120)
    target_date: date

class AssignCareer(BaseModel):
    employee_id: int
    target_role: str = Field(min_length=3, max_length=150)
    requirements: str = Field(min_length=10, max_length=3000)
    target_date: date

class TaskStatus(BaseModel):
    status: Literal["assigned", "in_progress", "completed"]

class CareerStatus(BaseModel):
    status: Literal["planned", "in_progress", "achieved"]

def scope(db, user, employee_id):
    if not allowed(db,user,employee_id): raise HTTPException(403,"Not authorized")

@router.post("/feedback-assignments", status_code=201)
def assign_feedback(data: AssignFeedback, user: Employee=Depends(current_user), db: Session=Depends(db_session)):
    if user.role not in HR: raise HTTPException(403,"HR access required")
    if data.employee_id == data.reviewer_id: raise HTTPException(422,"Self-rating is managed separately")
    require_employee(db,data.employee_id);require_employee(db,data.reviewer_id)
    if not db.get(ReviewCycle,data.cycle_id):raise HTTPException(422,"Cycle not found")
    existing=db.scalar(select(FeedbackAssignment.id).where(
        FeedbackAssignment.employee_id==data.employee_id,
        FeedbackAssignment.reviewer_id==data.reviewer_id,
        FeedbackAssignment.cycle_id==data.cycle_id))
    if existing:raise HTTPException(409,"Feedback assignment already exists")
    a=FeedbackAssignment(**data.model_dump())
    db.add(a);db.commit();db.refresh(a)
    return {"id":a.id,"employee_id":a.employee_id,"reviewer_id":a.reviewer_id,"status":"pending"}

@router.get("/feedback-assignments")
def my_feedback_assignments(user: Employee=Depends(current_user), db: Session=Depends(db_session)):
    q=select(FeedbackAssignment).where(FeedbackAssignment.reviewer_id==user.id)
    return [{"id":a.id,"employee_id":a.employee_id,"cycle_id":a.cycle_id,
             "status":"submitted" if a.submitted_at else "pending"}
            for a in db.scalars(q).all()]

@router.post("/feedback-assignments/{assignment_id}/submit")
def submit_feedback(assignment_id:int,data:SubmitFeedback,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    a=db.get(FeedbackAssignment,assignment_id)
    if not a or a.reviewer_id != user.id:raise HTTPException(404,"Assignment not found")
    if a.submitted_at:raise HTTPException(409,"Already submitted")
    a.score=data.score;a.feedback=data.feedback;a.submitted_at=datetime.now(timezone.utc)
    db.commit();return {"id":a.id,"status":"submitted"}

@router.get("/feedback-summary/{employee_id}/{cycle_id}")
def feedback_summary(employee_id:int,cycle_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,user,employee_id)
    entries=db.scalars(select(FeedbackAssignment).where(
        FeedbackAssignment.employee_id==employee_id,FeedbackAssignment.cycle_id==cycle_id,
        FeedbackAssignment.submitted_at.is_not(None))).all()
    # Protect the identity of peer reviewers: release scores only after 3 submissions.
    available = len(entries)>=3 or user.role in HR
    result={"employee_id":employee_id,"cycle_id":cycle_id,"response_count":len(entries),
            "average_score":round(sum(e.score for e in entries)/len(entries),2) if entries and available else None}
    if user.role in HR:
        result["confidential_reviews"]=[{"reviewer_id":e.reviewer_id,"score":e.score,
                                         "feedback":e.feedback} for e in entries]
    return result

@router.post("/learning",status_code=201)
def add_learning(data:AssignLearning,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_employee(db,data.employee_id)
    if not allowed(db,user,data.employee_id):raise HTTPException(403,"Not authorized")
    row=LearningTask(**data.model_dump(),created_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

@router.get("/learning")
def learning(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(LearningTask).order_by(LearningTask.id.desc())
    if employee_id is not None:scope(db,user,employee_id);q=q.where(LearningTask.employee_id==employee_id)
    elif user.role not in HR:
        if user.role=="manager":
            from .employee_core import EmployeeCore
            q=q.where((LearningTask.employee_id==user.id)|(LearningTask.employee_id.in_(
                select(EmployeeCore.employee_id).where(EmployeeCore.manager_id==user.id))))
        else:q=q.where(LearningTask.employee_id==user.id)
    return [{"id":r.id,"employee_id":r.employee_id,"title":r.title,"provider":r.provider,
             "target_date":r.target_date,"status":r.status} for r in db.scalars(q).all()]

@router.patch("/learning/{item_id}")
def mark_learning(item_id:int,data:TaskStatus,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(LearningTask,item_id)
    if not row or not allowed(db,user,row.employee_id):raise HTTPException(404,"Learning item not found")
    row.status=data.status;db.commit();return {"id":row.id,"status":row.status}

@router.post("/career",status_code=201)
def add_career(data:AssignCareer,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_employee(db,data.employee_id)
    if not can_manage(db,user,data.employee_id):raise HTTPException(403,"Manager/HR authorization required")
    row=CareerMilestone(**data.model_dump(),created_by=user.id)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"status":row.status}

@router.get("/career")
def career(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    q=select(CareerMilestone).order_by(CareerMilestone.id.desc())
    if employee_id is not None:scope(db,user,employee_id);q=q.where(CareerMilestone.employee_id==employee_id)
    elif user.role not in HR:
        if user.role=="manager":
            from .employee_core import EmployeeCore
            q=q.where((CareerMilestone.employee_id==user.id)|(CareerMilestone.employee_id.in_(
                select(EmployeeCore.employee_id).where(EmployeeCore.manager_id==user.id))))
        else:q=q.where(CareerMilestone.employee_id==user.id)
    return [{"id":r.id,"employee_id":r.employee_id,"target_role":r.target_role,
             "requirements":r.requirements,"target_date":r.target_date,
             "status":r.status} for r in db.scalars(q).all()]

@router.patch("/career/{item_id}")
def update_career(item_id:int,data:CareerStatus,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(CareerMilestone,item_id)
    if not row or not can_manage(db,user,row.employee_id):raise HTTPException(404,"Career milestone not found")
    row.status=data.status;db.commit();return {"id":row.id,"status":row.status}
