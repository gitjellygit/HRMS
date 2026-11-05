"""Accountant review queue for project schedule runs, never guess approved hours."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, current_user, db_session
from .project_finance import FINANCE, ProjectBilling, ClientInvoice, project_detail, create_row, invoice_view, audit

router=APIRouter(prefix="/finance",tags=["Billing Review Tasks"])

class BillableReview(Base):
    __tablename__="finance_billable_reviews"
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey("projects.id"),index=True)
    period_start:Mapped[date]=mapped_column(Date)
    period_end:Mapped[date]=mapped_column(Date)
    scheduled_on:Mapped[date]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(20),default="needs_units")
    invoice_id:Mapped[int|None]=mapped_column(ForeignKey("finance_invoices.id"),nullable=True)
    __table_args__=(UniqueConstraint("project_id","period_start","period_end",
         name="uq_finance_review_window"),)

class ApprovedUnits(BaseModel):
    quantity:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    tax_rate_pct:Decimal=Field(default=0,ge=0,le=100,decimal_places=2)

def create_review(db:Session,user:Employee,project_id:int,start:date,end:date,scheduled_on:date):
    present=db.scalar(select(BillableReview.id).where(
        BillableReview.project_id==project_id,BillableReview.period_start==start,
        BillableReview.period_end==end))
    if present:return None
    task=BillableReview(project_id=project_id,period_start=start,period_end=end,scheduled_on=scheduled_on)
    db.add(task);db.flush()
    audit(db,user,project_id,"invoice_units_required","Billing quantity to be verified by accountant")
    return {"id":task.id,"project_id":project_id,"status":task.status,
            "period_start":task.period_start,"period_end":task.period_end}

@router.get("/reviews")
def list_reviews(user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in FINANCE:raise HTTPException(403,"Finance/HR permission required")
    rows=db.scalars(select(BillableReview).order_by(BillableReview.id.desc()).limit(500)).all()
    return [{"id":t.id,"project_id":t.project_id,"period_start":t.period_start,
       "period_end":t.period_end,"status":t.status,"invoice_id":t.invoice_id}
       for t in rows]

@router.post("/reviews/{review_id}/invoice",status_code=201)
def issue_reviewed_invoice(review_id:int,body:ApprovedUnits,
     user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in FINANCE:raise HTTPException(403,"Finance/HR permission required")
    row=db.scalar(select(BillableReview).where(BillableReview.id==review_id).with_for_update())
    if row is None:raise HTTPException(404,"Billing review not found")
    if row.status!="needs_units":raise HTTPException(409,"Review already invoiced")
    p,d=project_detail(db,row.project_id)
    c=db.get(ProjectBilling,row.project_id)
    if c is None:raise HTTPException(422,"Billing profile required")
    invoice=create_row(db,user,p,d,c,row.period_start,row.period_end,
          body.quantity,body.tax_rate_pct,date.today(),"schedule_reviewed")
    db.flush();row.invoice_id=invoice.id;row.status="invoiced"
    db.commit();db.refresh(invoice)
    return invoice_view(invoice)
