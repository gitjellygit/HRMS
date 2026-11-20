"""Deterministic monetary regression for half-day and weekend LOP."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, Employee
from app.payroll import calculate, money, ym_bounds
from app.leave_management import LeaveRequest
from test_pay_people import seed, create, configure


def test_half_day_and_weekend_leave_count_only_billable_working_days():
    with TestClient(app) as client:
        admin,_,_,_=seed(client)
        emp_id=create(client,"lop.regression.qa@example.org","Payroll Leave QA","employee",admin)
        configure(client,emp_id)
        period=date.today().strftime("%Y-%m")
        start,end=ym_bounds(period)
        days=(end-start).days+1
        # Avoid any configured public holidays by choosing dates in a fresh
        # isolated test DB and controlling the inserted leave units.
        friday=next(start+timedelta(days=i) for i in range(days-3)
                    if (start+timedelta(days=i)).weekday()==4)
        other=next(start+timedelta(days=i) for i in range(days)
                   if (start+timedelta(days=i)).weekday()==1
                   and (start+timedelta(days=i)) not in (friday,friday+timedelta(days=3)))
        with SessionLocal() as db:
            worker=db.get(Employee,emp_id)
            worker.joining_date=start
            db.add(LeaveRequest(employee_id=emp_id,leave_type="loss_of_pay",
                start_date=friday,end_date=friday+timedelta(days=3),day_part="full",
                days=Decimal("2"),reason="QA approved two working days",
                chain="manager",status="approved",manager_snapshot_id=admin))
            db.add(LeaveRequest(employee_id=emp_id,leave_type="loss_of_pay",
                start_date=other,end_date=other,day_part="half",
                days=Decimal("0.5"),reason="QA approved half day",
                chain="manager",status="approved",manager_snapshot_id=admin))
            db.commit()
            result=calculate(db,worker,period)
            assert result["lop_days"]==Decimal("2.5")
            expected_loss=money(Decimal("50000")*Decimal("2.5")/Decimal(days))
            assert result["lop_amount"]==expected_loss
            assert result["gross"]==Decimal("50000.00")
            assert result["net"]==Decimal("50000.00")-expected_loss-Decimal("1700.00")
