"""Configurable employee exit checklist with HR initiation and delegated tasks."""
from datetime import date,timedelta
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import ForeignKey,String,Date,Text,select
from sqlalchemy.orm import Session,Mapped,mapped_column
from .main import Base,Employee,current_user,db_session
from .people_operations import ExitCase,HR,audit

router=APIRouter(prefix="/exit-workflow",tags=["Exit checklists"])

class ExitTaskTemplate(Base):
    __tablename__="exit_task_templates"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(180))
    assignee_role:Mapped[str]=mapped_column(String(24),default="hr")
    active:Mapped[bool]=mapped_column(default=True)

class ExitTask(Base):
    __tablename__="exit_assigned_tasks"
    id:Mapped[int]=mapped_column(primary_key=True)
    exit_id:Mapped[int]=mapped_column(ForeignKey("people_exit_cases.id"),index=True)
    title:Mapped[str]=mapped_column(String(180))
    assignee_role:Mapped[str]=mapped_column(String(24))
    assignee_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default="pending")
    completion_note:Mapped[str]=mapped_column(Text,default="")
    completed_by:Mapped[int|None]=mapped_column(ForeignKey("employees.id"),nullable=True)

DEFAULTS=[("Return company laptop and accessories","employee"),
          ("Complete handover and knowledge transfer","employee"),
          ("Collect and verify company equipment","hr"),
          ("Disable access and revoke credentials","hr"),
          ("Confirm outstanding payroll, reimbursements and F&F","hr")]

class TemplateIn(BaseModel):
    title:str=Field(min_length=5,max_length=180)
    assignee_role:Literal["employee","hr"]="hr"
    active:bool=True

class StartExitIn(BaseModel):
    employee_id:int
    reason:str=Field(min_length=10,max_length=2000)
    notice_days:int=Field(ge=0,le=365)
    requested_date:date=Field(default_factory=date.today)

class CompleteIn(BaseModel):
    note:str=Field(min_length=5,max_length=1000)

def require_hr(user):
    if user.role not in HR:raise HTTPException(403,"Only HR may configure or initiate an exit")

def templates(db:Session):
    configured=db.scalars(select(ExitTaskTemplate).order_by(ExitTaskTemplate.id)).all()
    return configured if configured else []

def create_tasks(db:Session,case:ExitCase):
    configured=templates(db)
    defaults=[{"title":title,"assignee_role":role,"active":True} for title,role in DEFAULTS]
    to_create=[{"title":x.title,"assignee_role":x.assignee_role,"active":x.active} for x in configured] if configured else defaults
    for item in to_create:
        if not item["active"]:continue
        db.add(ExitTask(exit_id=case.id,title=item["title"],assignee_role=item["assignee_role"],
                        assignee_id=case.employee_id if item["assignee_role"]=="employee" else None))

@router.get("/templates")
def list_templates(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    saved=templates(db)
    return [{"id":x.id,"title":x.title,"assignee_role":x.assignee_role,"active":x.active} for x in saved] if saved else [
        {"id":None,"title":title,"assignee_role":role,"active":True} for title,role in DEFAULTS]

@router.post("/templates",status_code=201)
def add_template(data:TemplateIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    # Preserve standard clearances in configuration when customizing for the first time.
    if not templates(db):
        for title,role in DEFAULTS:
            db.add(ExitTaskTemplate(title=title,assignee_role=role,active=True))
    row=ExitTaskTemplate(**data.model_dump())
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"title":row.title,"assignee_role":row.assignee_role,"active":row.active}

@router.put("/templates/{template_id}")
def edit_template(template_id:int,data:TemplateIn,user:Employee=Depends(current_user),
                  db:Session=Depends(db_session)):
    require_hr(user)
    row=db.get(ExitTaskTemplate,template_id)
    if not row:raise HTTPException(404,"Exit checklist template not found")
    previous=f"{row.title} / {row.assignee_role} / active={row.active}"
    for key,value in data.model_dump().items():setattr(row,key,value)
    audit(db,user,"exit_template",template_id,"updated",previous)
    db.commit()
    return {"id":row.id,"title":row.title,"assignee_role":row.assignee_role,"active":row.active}


@router.post("/cases",status_code=201)
def initiate(data:StartExitIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    employee=db.get(Employee,data.employee_id)
    if not employee or employee.status!="active":raise HTTPException(422,"Select an active employee")
    existing=db.scalar(select(ExitCase.id).where(ExitCase.employee_id==data.employee_id,
                      ExitCase.status.in_(["requested","approved","clearance"])))
    if existing:raise HTTPException(409,"This employee already has an active exit case")
    row=ExitCase(employee_id=data.employee_id,reason=data.reason.strip(),
                 requested_date=data.requested_date,notice_days=data.notice_days,
                 planned_last_day=data.requested_date+timedelta(days=data.notice_days))
    db.add(row);db.flush();create_tasks(db,row)
    audit(db,user,"exit",row.id,"initiated_by_hr");db.commit()
    return {"id":row.id,"status":"requested","employee_id":row.employee_id}

@router.get("/cases/{case_id}/tasks")
def list_tasks(case_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    case=db.get(ExitCase,case_id)
    if not case:raise HTTPException(404,"Exit case not found")
    if user.role not in HR and case.employee_id!=user.id:raise HTTPException(403,"This exit case is not assigned to you")
    rows=db.scalars(select(ExitTask).where(ExitTask.exit_id==case_id).order_by(ExitTask.id)).all()
    if not rows and case.status=="requested":
        create_tasks(db,case);db.commit()
        rows=db.scalars(select(ExitTask).where(ExitTask.exit_id==case_id).order_by(ExitTask.id)).all()
    return [{"id":t.id,"title":t.title,"assignee_role":t.assignee_role,
             "status":t.status,"completion_note":t.completion_note,"completed_by":t.completed_by}
            for t in rows if user.role in HR or t.assignee_role=="employee"]

@router.post("/tasks/{task_id}/complete")
def complete(task_id:int,data:CompleteIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(ExitTask,task_id)
    if not row:raise HTTPException(404,"Exit task not found")
    case=db.get(ExitCase,row.exit_id)
    if user.role not in HR and (row.assignee_role!="employee" or case.employee_id!=user.id):
        raise HTTPException(403,"This exit task is not assigned to you")
    if row.status=="completed":raise HTTPException(409,"Task has already been completed")
    row.status="completed";row.completion_note=data.note.strip();row.completed_by=user.id
    audit(db,user,"exit",row.exit_id,"task_completed",row.title)
    db.commit()
    return {"id":row.id,"status":"completed"}
