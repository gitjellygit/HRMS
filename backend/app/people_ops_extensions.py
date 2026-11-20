"""Preserved people-operations capabilities from the alternate 31–45 implementation."""
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .people_operations import (
    HR, HelpdeskTicket, ExitCase, audit, now, require_hr, owned
)
router=APIRouter(prefix="/people", tags=["People Operations: assets, tickets and clearance"])

class AssetAllocation(Base):
    __tablename__="people_asset_allocations"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    name:Mapped[str]=mapped_column(String(150))
    serial_number:Mapped[str]=mapped_column(String(120),unique=True)
    allocated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    returned_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class HelpdeskMessage(Base):
    __tablename__="people_helpdesk_messages"
    id:Mapped[int]=mapped_column(primary_key=True)
    ticket_id:Mapped[int]=mapped_column(ForeignKey("people_helpdesk_tickets.id"),index=True)
    author_id:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    body:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExitClearance(Base):
    __tablename__="people_exit_clearance_approvals"
    id:Mapped[int]=mapped_column(primary_key=True)
    exit_id:Mapped[int]=mapped_column(ForeignKey("people_exit_cases.id"),index=True)
    kind:Mapped[str]=mapped_column(String(20))
    approved_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    note:Mapped[str]=mapped_column(Text)
    approved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("exit_id","kind",name="uq_exit_clearance_approval"),)

class AssetIn(BaseModel):
    employee_id:int
    name:str=Field(min_length=3,max_length=150)
    serial_number:str=Field(min_length=3,max_length=120)

class MessageIn(BaseModel):
    body:str=Field(min_length=2,max_length=4000)

class ClearanceIn(BaseModel):
    kind:Literal["assets","it","finance"]
    note:str=Field(min_length=10,max_length=2000)

@router.post("/assets",status_code=201)
def allocate_asset(data:AssetIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    if not db.get(Employee,data.employee_id):raise HTTPException(422,"Employee not found")
    if db.scalar(select(AssetAllocation.id).where(AssetAllocation.serial_number==data.serial_number)):
        raise HTTPException(409,"Asset already allocated")
    a=AssetAllocation(**data.model_dump())
    db.add(a);db.flush();audit(db,user,"asset",a.id,"allocated");db.commit();db.refresh(a)
    return {"id":a.id,"returned_at":a.returned_at}

@router.get("/assets")
def assets(employee_id:int|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if employee_id is not None:owned(user,employee_id)
    q=select(AssetAllocation).order_by(AssetAllocation.id.desc())
    if employee_id is not None:q=q.where(AssetAllocation.employee_id==employee_id)
    elif user.role not in HR:q=q.where(AssetAllocation.employee_id==user.id)
    return [{"id":a.id,"employee_id":a.employee_id,"name":a.name,"serial_number":a.serial_number,
             "allocated_at":a.allocated_at,"returned_at":a.returned_at} for a in db.scalars(q).all()]

@router.post("/assets/{asset_id}/return")
def return_asset(asset_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    require_hr(user)
    a=db.get(AssetAllocation,asset_id)
    if not a:raise HTTPException(404,"Asset not found")
    if a.returned_at:raise HTTPException(409,"Asset already returned")
    a.returned_at=now();audit(db,user,"asset",a.id,"returned");db.commit()
    return {"id":a.id,"returned_at":a.returned_at}

@router.get("/tickets/{ticket_id}/messages")
def ticket_messages(ticket_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    ticket=db.get(HelpdeskTicket,ticket_id)
    if not ticket:raise HTTPException(404,"Ticket not found")
    owned(user,ticket.employee_id)
    return [{"id":m.id,"author_id":m.author_id,"body":m.body,"created_at":m.created_at}
      for m in db.scalars(select(HelpdeskMessage).where(HelpdeskMessage.ticket_id==ticket_id)
         .order_by(HelpdeskMessage.id)).all()]

@router.post("/tickets/{ticket_id}/messages",status_code=201)
def ticket_message(ticket_id:int,data:MessageIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    ticket=db.get(HelpdeskTicket,ticket_id)
    if not ticket:raise HTTPException(404,"Ticket not found")
    owned(user,ticket.employee_id)
    if ticket.status=="closed":raise HTTPException(409,"Closed ticket")
    m=HelpdeskMessage(ticket_id=ticket.id,author_id=user.id,body=data.body)
    db.add(m);db.flush();ticket.updated_at=now()
    audit(db,user,"ticket",ticket.id,"message")
    db.commit()
    return {"id":m.id,"sent":True}

@router.get("/exits/{exit_id}/clearances")
def exit_clearances(exit_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    case=db.get(ExitCase,exit_id)
    if not case:raise HTTPException(404,"Exit not found")
    owned(user,case.employee_id)
    return [{"kind":c.kind,"approved_by":c.approved_by,"approved_at":c.approved_at,"note":c.note}
      for c in db.scalars(select(ExitClearance).where(ExitClearance.exit_id==exit_id)).all()]

@router.post("/exits/{exit_id}/clearances",status_code=201)
def approve_clearance(exit_id:int,data:ClearanceIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if data.kind=="finance":
        if user.role not in (*HR,"accountant"):raise HTTPException(403,"Finance/HR access required")
    else:require_hr(user)
    case=db.get(ExitCase,exit_id)
    if not case:raise HTTPException(404,"Exit not found")
    if case.status not in ("approved","clearance"):raise HTTPException(409,"Exit approval required first")
    if db.scalar(select(ExitClearance.id).where(ExitClearance.exit_id==exit_id,ExitClearance.kind==data.kind)):
        raise HTTPException(409,"Clearance already recorded")
    if data.kind=="assets":
        outstanding=db.scalar(select(AssetAllocation.id).where(
            AssetAllocation.employee_id==case.employee_id,AssetAllocation.returned_at.is_(None)))
        if outstanding:raise HTTPException(409,"Employee has outstanding company assets")
    row=ExitClearance(exit_id=exit_id,kind=data.kind,note=data.note,approved_by=user.id)
    db.add(row);db.flush();audit(db,user,"exit",exit_id,"clearance_"+data.kind)
    db.commit();return {"id":row.id,"kind":row.kind,"approved_at":row.approved_at}
