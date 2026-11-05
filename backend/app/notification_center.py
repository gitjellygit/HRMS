"""In-app inbox: employee-scoped notifications, read state and soft archive.

External email/SMS/push queue remains independent. Archive hides an item from the
inbox, but retains its history for audit and does not revoke policy acknowledgement.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, select, func
from sqlalchemy.orm import Session, Mapped, mapped_column
from .main import Base, Employee, db_session, current_user

router=APIRouter(prefix="/notification-center",tags=["In-app notifications"])

class InboxNotification(Base):
    __tablename__="employee_inbox_notifications"
    id:Mapped[int]=mapped_column(primary_key=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id"),index=True)
    event:Mapped[str]=mapped_column(String(50))
    title:Mapped[str]=mapped_column(String(180))
    body:Mapped[str]=mapped_column(Text)
    destination:Mapped[str]=mapped_column(String(80),default="people")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    archived_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

def add_inbox(db:Session,employee_id:int,event:str,title:str,body:str,destination:str="people"):
    item=InboxNotification(employee_id=employee_id,event=event,title=title,body=body,
                            destination=destination)
    db.add(item)
    return item

def view(n:InboxNotification):
    return {"id":n.id,"event":n.event,"title":n.title,"body":n.body,
            "destination":n.destination,"created_at":n.created_at,
            "read":n.read_at is not None,"archived":n.archived_at is not None,
            "read_at":n.read_at}

@router.get("")
def list_inbox(limit:int=50,include_archived:bool=False,
               user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if limit<1 or limit>200:raise HTTPException(422,"Limit must be between 1 and 200")
    q=select(InboxNotification).where(InboxNotification.employee_id==user.id)
    if not include_archived:q=q.where(InboxNotification.archived_at.is_(None))
    rows=db.scalars(q.order_by(InboxNotification.id.desc()).limit(limit)).all()
    unread=db.scalar(select(func.count()).select_from(InboxNotification).where(
        InboxNotification.employee_id==user.id,InboxNotification.read_at.is_(None),
        InboxNotification.archived_at.is_(None))) or 0
    return {"items":[view(n) for n in rows],"unread_count":unread}

@router.post("/{notification_id}/read")
def mark_read(notification_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(InboxNotification,notification_id)
    if not row or row.employee_id!=user.id:raise HTTPException(404,"Notification not found")
    if row.read_at is None:row.read_at=datetime.now(timezone.utc)
    db.commit()
    return {"id":row.id,"read":True}

@router.post("/{notification_id}/archive")
def archive(notification_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    row=db.get(InboxNotification,notification_id)
    if not row or row.employee_id!=user.id:raise HTTPException(404,"Notification not found")
    if row.archived_at is None:row.archived_at=datetime.now(timezone.utc)
    db.commit()
    return {"id":row.id,"archived":True}

@router.post("/read-all")
def mark_all_read(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(InboxNotification).where(
        InboxNotification.employee_id==user.id,InboxNotification.read_at.is_(None),
        InboxNotification.archived_at.is_(None))).all()
    stamp=datetime.now(timezone.utc)
    for row in rows:row.read_at=stamp
    db.commit()
    return {"marked":len(rows)}
