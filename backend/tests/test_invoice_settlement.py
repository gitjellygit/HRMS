"""Money invariants and auditability for invoice settlement and internal credits."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, ORIGIN
from test_finance_pricing_salary_components import placement
from test_hardening_billing import configure


def new_invoice(client,tax="10.00"):
    _,_,owner,_=seed(client)
    project=placement(client,owner)
    configure(client,project,tax=tax)
    invoice=client.post("/finance/invoices",headers=ORIGIN,json={
        "project_id":project,"period_start":(date.today()-timedelta(days=2)).isoformat(),
        "period_end":date.today().isoformat(),"quantity":"1"})
    assert invoice.status_code==201,invoice.text
    ident=invoice.json()["id"]
    marked=client.post(f"/finance/invoices/{ident}/status",headers=ORIGIN,
                       json={"status":"sent","reference":"Invoice delivered to customer"})
    assert marked.status_code==200,marked.text
    return project,ident


def test_partial_payments_credit_and_final_settlement_are_balanced():
    with TestClient(app) as c:
        project,invoice_id=new_invoice(c)
        partial=c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"40.00","reference":"bank-transfer-A1"})
        assert partial.status_code==201,partial.text
        assert Decimal(str(partial.json()["balance"]["outstanding"]))==Decimal("70.00")
        assert c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"10","reference":"bank-transfer-A1"}).status_code==409
        excess=c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"70.01","reference":"bank-transfer-A2"})
        assert excess.status_code==422,excess.text
        credit=c.post(f"/finance/invoices/{invoice_id}/credit-notes",headers=ORIGIN,json={
            "subtotal":"20","reason":"Incorrect billable quantity correction",
            "reference":"CREDIT-CORRECTION-1"})
        assert credit.status_code==201,credit.text
        assert Decimal(str(credit.json()["credit_note"]["tax_amount"]))==Decimal("2.00")
        assert Decimal(str(credit.json()["balance"]["outstanding"]))==Decimal("48.00")
        assert c.post(f"/finance/invoices/{invoice_id}/credit-notes",headers=ORIGIN,json={
            "subtotal":"20","reason":"Incorrect billable quantity correction",
            "reference":"CREDIT-CORRECTION-1"}).status_code==409
        summary=c.get(f"/finance/invoices/{invoice_id}/settlement")
        assert summary.status_code==200,summary.text
        assert len(summary.json()["payments"])==1
        assert len(summary.json()["credit_notes"])==1
        assert c.post(f"/finance/invoices/{invoice_id}/status",headers=ORIGIN,
            json={"status":"void","reference":"Should reject after financial settlement"}).status_code==409
        finished=c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"48","reference":"bank-transfer-A3"})
        assert finished.status_code==201,finished.text
        assert Decimal(str(finished.json()["balance"]["outstanding"]))==Decimal("0.00")
        state=next(x for x in c.get("/finance/invoices").json() if x["id"]==invoice_id)
        assert state["stored_status"]=="paid"
        assert c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"1","reference":"extra"}).status_code==422
        audit=c.get("/finance/audit").json()
        assert any(x["event"]=="invoice_payment_recorded" for x in audit)
        assert any(x["event"]=="invoice_credit_recorded" for x in audit)
        ageing=c.get("/finance/receivables/ageing")
        assert ageing.status_code==200
        assert all(x["invoice_id"]!=invoice_id for x in ageing.json()["invoices"])


def test_legacy_mark_paid_backfills_receipt_and_ageing_uses_outstanding_amount():
    with TestClient(app) as c:
        project,invoice_id=new_invoice(c,tax="0")
        first=c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
             json={"amount":"30","reference":"cash-reference-002"})
        assert first.status_code==201,first.text
        ageing=c.get("/finance/receivables/ageing").json()
        row=next(x for x in ageing["invoices"] if x["invoice_id"]==invoice_id)
        assert Decimal(str(row["outstanding"]))==Decimal("70.00")
        assert row["currency"] in [group["currency"] for group in ageing["currency_totals"]]
        legacy=c.post(f"/finance/invoices/{invoice_id}/status",headers=ORIGIN,
             json={"status":"paid","reference":"Manual confirmed bank settlement"})
        assert legacy.status_code==200,legacy.text
        detail=c.get(f"/finance/invoices/{invoice_id}/settlement").json()
        assert Decimal(str(detail["balance"]["paid"]))==Decimal("100.00")
        assert Decimal(str(detail["balance"]["outstanding"]))==0
        assert len(detail["payments"])==2
        assert c.post(f"/finance/invoices/{invoice_id}/status",headers=ORIGIN,
             json={"status":"paid"}).status_code==409


def test_credit_cannot_exceed_outstanding_and_cannot_be_added_to_draft():
    with TestClient(app) as c:
        project,invoice_id=new_invoice(c,tax="5.00")
        larger=c.post(f"/finance/invoices/{invoice_id}/credit-notes",headers=ORIGIN,json={
            "subtotal":"1000","reason":"Unapproved excessive credit correction",
            "reference":"OVERCREDIT-5"})
        assert larger.status_code==422,larger.text
        valid=c.post(f"/finance/invoices/{invoice_id}/credit-notes",headers=ORIGIN,json={
            "subtotal":"100","reason":"Full service amount credited as correction",
            "reference":"CREDIT-FULL-1"})
        assert valid.status_code==201,valid.text
        assert Decimal(str(valid.json()["balance"]["outstanding"]))==0
        assert c.post(f"/finance/invoices/{invoice_id}/payments",headers=ORIGIN,
            json={"amount":"1","reference":"unexpected-payment"}).status_code==422
