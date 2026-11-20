"""Invoice numbering and Indian GST draft invariants (not statutory certification)."""
from datetime import date,timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app,SessionLocal
from app.project_management import ProjectDetail
from test_pay_people import seed,ORIGIN
from test_finance_pricing_salary_components import placement
from test_hardening_billing import configure


def test_fiscal_invoice_numbering_and_gst_breakdowns():
    with TestClient(app) as c:
        _,_,owner,_=seed(c)
        pid=placement(c,owner)
        configure(c,pid,tax="18.00")
        details={"supplier_gstin":"27ABCDE1234F1Z5",
                 "recipient_gstin":"29ABCDE1234F1Z5",
                 "sac_code":"998314","place_of_supply":"27"}
        window={"project_id":pid,"period_start":(date.today()-timedelta(days=2)).isoformat(),
                "period_end":date.today().isoformat(),"quantity":"2"}
        # Indian GST drafts are restricted to INR projects.
        denied=c.post("/finance/invoices",headers=ORIGIN,json={**window,"gst_details":details})
        assert denied.status_code==422,denied.text
        with SessionLocal() as db:
            info=db.get(ProjectDetail,pid)
            info.currency="INR"
            db.commit()
        intra=c.post("/finance/invoices",headers=ORIGIN,json={**window,"gst_details":details})
        assert intra.status_code==201,intra.text
        first=intra.json()
        assert first["invoice_number"].startswith("JG/")
        assert first["tax_scheme"]=="cgst_sgst"
        assert Decimal(str(first["cgst_amount"]))==Decimal("18.00")
        assert Decimal(str(first["sgst_amount"]))==Decimal("18.00")
        assert Decimal(str(first["igst_amount"]))==0
        assert first["statutory_tax_invoice"] is False
        invalid=c.post("/finance/invoices",headers=ORIGIN,json={
            **window,"gst_details":{**details,"supplier_gstin":"invalid"}})
        assert invalid.status_code==422,invalid.text
        # Second invoice in another period must receive a distinct number.
        other={**window,"period_start":(date.today()-timedelta(days=5)).isoformat(),
               "period_end":(date.today()-timedelta(days=3)).isoformat(),
               "gst_details":{**details,"place_of_supply":"29"}}
        interstate=c.post("/finance/invoices",headers=ORIGIN,json=other)
        assert interstate.status_code==201,interstate.text
        second=interstate.json()
        assert second["invoice_number"]!=first["invoice_number"]
        assert second["tax_scheme"]=="igst"
        assert Decimal(str(second["igst_amount"]))==Decimal("36.00")
        assert Decimal(str(second["cgst_amount"]))==0
        assert Decimal(str(second["sgst_amount"]))==0
        pdf=c.get(f'/finance/invoices/{first["id"]}.pdf')
        assert pdf.status_code==200,pdf.text
        assert pdf.content.startswith(b"%PDF")
