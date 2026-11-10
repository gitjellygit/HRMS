"""Controlled invoice settlements, credit notes and receivables ageing.

All amounts are invoice-currency amounts, two decimal places. A credit note is a
recorded adjustment, not a tax-compliant statutory credit note until business GST
metadata and numbering are configured.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .main import Base, Employee, db_session, current_user
from .project_finance import ClientInvoice, authorized, audit

router=APIRouter(prefix="/finance",tags=["Invoice Settlements"])
CENT=Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT,rounding=ROUND_HALF_UP)


class InvoicePayment(Base):
    __tablename__="finance_invoice_payments"
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey("finance_invoices.id"),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    received_on:Mapped[date]=mapped_column(Date)
    reference:Mapped[str]=mapped_column(String(120))
    recorded_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint("invoice_id","reference",name="uq_invoice_payment_reference"),)


class InvoiceCreditNote(Base):
    __tablename__="finance_invoice_credit_notes"
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey("finance_invoices.id"),index=True)
    subtotal:Mapped[Decimal]=mapped_column(Numeric(14,2))
    tax_rate_pct:Mapped[Decimal]=mapped_column(Numeric(6,2))
    tax_amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    total:Mapped[Decimal]=mapped_column(Numeric(14,2))
    reason:Mapped[str]=mapped_column(Text)
    reference:Mapped[str]=mapped_column(String(120))
    issued_on:Mapped[date]=mapped_column(Date)
    created_by:Mapped[int]=mapped_column(ForeignKey("employees.id"))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint("invoice_id","reference",name="uq_invoice_credit_reference"),)


class PaymentIn(BaseModel):
    amount:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    received_on:date=Field(default_factory=date.today)
    reference:str=Field(min_length=3,max_length=120)


class CreditIn(BaseModel):
    subtotal:Decimal=Field(gt=0,le=100000000,decimal_places=2)
    reason:str=Field(min_length=10,max_length=1000)
    reference:str=Field(min_length=3,max_length=120)
    issued_on:date=Field(default_factory=date.today)


def settlement(db:Session,invoice:ClientInvoice):
    payments=db.scalars(select(InvoicePayment).where(InvoicePayment.invoice_id==invoice.id)).all()
    credits=db.scalars(select(InvoiceCreditNote).where(InvoiceCreditNote.invoice_id==invoice.id)).all()
    paid=money(sum((Decimal(p.amount) for p in payments),Decimal("0")))
    credited=money(sum((Decimal(c.total) for c in credits),Decimal("0")))
    outstanding=money(Decimal(invoice.total)-paid-credited)
    return {"invoice_id":invoice.id,"currency":invoice.currency,
            "total":money(invoice.total),"paid":paid,"credited":credited,
            "outstanding":outstanding,"payment_count":len(payments),
            "credit_note_count":len(credits)}


def locked_invoice(db,invoice_id):
    invoice=db.scalar(select(ClientInvoice).where(ClientInvoice.id==invoice_id).with_for_update())
    if invoice is None:raise HTTPException(404,"Invoice not found")
    if invoice.status=="void":raise HTTPException(409,"Voided invoices cannot receive settlements")
    if invoice.status=="draft":raise HTTPException(409,"Mark invoice as sent before recording settlement")
    return invoice


def payment_view(p:InvoicePayment):
    return {"id":p.id,"invoice_id":p.invoice_id,"amount":p.amount,
            "received_on":p.received_on,"reference":p.reference,"recorded_by":p.recorded_by}


def credit_view(c:InvoiceCreditNote):
    return {"id":c.id,"invoice_id":c.invoice_id,"subtotal":c.subtotal,
            "tax_rate_pct":c.tax_rate_pct,"tax_amount":c.tax_amount,
            "total":c.total,"issued_on":c.issued_on,"reference":c.reference,
            "reason":c.reason,"created_by":c.created_by,
            "document_status":"internal_adjustment_not_tax_credit_note"}


@router.post("/invoices/{invoice_id}/payments",status_code=201)
def record_payment(invoice_id:int,body:PaymentIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    invoice=locked_invoice(db,invoice_id)
    if body.received_on>date.today():
        raise HTTPException(422,detail={"field":"received_on","message":"Payment date cannot be in the future."})
    if db.scalar(select(InvoicePayment.id).where(
        InvoicePayment.invoice_id==invoice_id,InvoicePayment.reference==body.reference.strip())):
        raise HTTPException(409,detail={"field":"reference","message":"This payment reference is already recorded for this invoice."})
    balance=settlement(db,invoice)
    if body.amount>balance["outstanding"]:
        raise HTTPException(422,detail={"field":"amount","message":"Payment exceeds the remaining invoice balance.",
            "outstanding":str(balance["outstanding"])})
    payment=InvoicePayment(invoice_id=invoice.id,amount=body.amount,received_on=body.received_on,
                           reference=body.reference.strip(),recorded_by=user.id)
    db.add(payment);db.flush()
    after=settlement(db,invoice)
    if after["outstanding"]==0:
        invoice.status="paid"
        invoice.paid_at=datetime.now(timezone.utc)
    audit(db,user,invoice.project_id,"invoice_payment_recorded",
          f"Invoice #{invoice.id}; receipt #{payment.id}; amount {body.amount} {invoice.currency}")
    db.commit()
    return {"payment":payment_view(payment),"balance":after}


@router.post("/invoices/{invoice_id}/credit-notes",status_code=201)
def create_credit_note(invoice_id:int,body:CreditIn,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    invoice=locked_invoice(db,invoice_id)
    if invoice.status=="paid":
        raise HTTPException(409,"Paid invoices require a separate refund process; do not issue a credit against a settled invoice.")
    if body.issued_on>date.today():
        raise HTTPException(422,detail={"field":"issued_on","message":"Credit note date cannot be in the future."})
    if db.scalar(select(InvoiceCreditNote.id).where(
        InvoiceCreditNote.invoice_id==invoice_id,InvoiceCreditNote.reference==body.reference.strip())):
        raise HTTPException(409,detail={"field":"reference","message":"This credit note reference is already recorded."})
    tax=money(body.subtotal*Decimal(invoice.tax_rate_pct)/Decimal(100))
    total=money(body.subtotal+tax)
    balance=settlement(db,invoice)
    if total>balance["outstanding"]:
        raise HTTPException(422,detail={"field":"subtotal","message":"Credit exceeds the outstanding invoice balance.",
            "outstanding":str(balance["outstanding"])})
    credit=InvoiceCreditNote(invoice_id=invoice.id,subtotal=body.subtotal,
        tax_rate_pct=invoice.tax_rate_pct,tax_amount=tax,total=total,
        issued_on=body.issued_on,reason=body.reason.strip(),reference=body.reference.strip(),created_by=user.id)
    db.add(credit);db.flush()
    after=settlement(db,invoice)
    if after["outstanding"]==0:
        invoice.status="settled_by_credit"
    audit(db,user,invoice.project_id,"invoice_credit_recorded",
          f"Invoice #{invoice.id}; credit #{credit.id}; total {total} {invoice.currency}; reason: {body.reason.strip()}")
    db.commit()
    return {"credit_note":credit_view(credit),"balance":after}


@router.get("/invoices/{invoice_id}/settlement")
def invoice_settlement(invoice_id:int,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    invoice=db.get(ClientInvoice,invoice_id)
    if invoice is None:raise HTTPException(404,"Invoice not found")
    payments=db.scalars(select(InvoicePayment).where(InvoicePayment.invoice_id==invoice.id).order_by(InvoicePayment.id)).all()
    credits=db.scalars(select(InvoiceCreditNote).where(InvoiceCreditNote.invoice_id==invoice.id).order_by(InvoiceCreditNote.id)).all()
    return {"balance":settlement(db,invoice),"payments":[payment_view(x) for x in payments],
            "credit_notes":[credit_view(x) for x in credits]}


@router.get("/receivables/ageing")
def receivables_ageing(as_of:date|None=None,user:Employee=Depends(current_user),db:Session=Depends(db_session)):
    authorized(user)
    as_of=as_of or date.today()
    if as_of>date.today():raise HTTPException(422,"Cannot age receivables to a future date")
    rows=[]
    for invoice in db.scalars(select(ClientInvoice).where(ClientInvoice.status.notin_(("draft","void"))).order_by(ClientInvoice.due_date,ClientInvoice.id)):
        balance=settlement(db,invoice)
        if balance["outstanding"]<=0:continue
        overdue=max((as_of-invoice.due_date).days,0)
        bucket=("current" if overdue==0 else "1_30" if overdue<=30
                else "31_60" if overdue<=60 else "61_90" if overdue<=90 else "90_plus")
        rows.append({"invoice_id":invoice.id,"project_id":invoice.project_id,
                     "recipient_name":invoice.recipient_name,"currency":invoice.currency,
                     "due_date":invoice.due_date,"days_overdue":overdue,"bucket":bucket,
                     "outstanding":balance["outstanding"]})
    totals={}
    for row in rows:
        group=totals.setdefault(row["currency"],{"currency":row["currency"],
            "current":Decimal(0),"1_30":Decimal(0),"31_60":Decimal(0),
            "61_90":Decimal(0),"90_plus":Decimal(0),"total":Decimal(0)})
        group[row["bucket"]]+=row["outstanding"]
        group["total"]+=row["outstanding"]
    return {"as_of":as_of,"invoices":rows,"currency_totals":list(totals.values())}
