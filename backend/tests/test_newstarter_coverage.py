"""New hire -> prorated leave -> manager -> HR -> logout -> re-login."""
from datetime import date,timedelta,datetime
from fastapi.testclient import TestClient
from app.main import app
from app.leave_management import fy_start_year
from test_pay_people import seed,create,login,PASS,ORIGIN

def switch(c,email,password=PASS):
 c.post("/auth/logout",headers=ORIGIN)
 return login(c,email,password)

def test_new_employee_leave_end_to_end():
 with TestClient(app) as c:
  admin,hr,one,other=seed(c)
  mgr=create(c,"qa.onboarding.manager@example.org","Onboarding Manager","manager",admin)
  email="qa.onboarding."+str(datetime.now().timestamp()).replace(".","")+"@example.org"
  employee=create(c,email,"Onboarding Newstarter","employee",mgr)
  fy=fy_start_year(date.today())
  policy=c.put("/leave/policies",headers=ORIGIN,json={
    "leave_type":"casual","annual_days":12,"monthly_accrual":0,
    "approval_chain":["manager","hr"],"probation_allowed":True,"active":True})
  assert policy.status_code==200,policy.text
  switch(c,email)
  assert c.get("/me").status_code==200
  balance=c.get(f"/leave/balances?year={fy}")
  assert balance.status_code==200,balance.text
  initial=next(x for x in balance.json() if x["leave_type"]=="casual")
  assert 0<initial["allocated"]<=12
  future=date.today()+timedelta(days=14)
  while future.weekday()>4:future+=timedelta(days=1)
  request=c.post("/leave/requests",headers=ORIGIN,json={
    "leave_type":"casual","start_date":future.isoformat(),
    "end_date":future.isoformat(),"day_part":"full",
    "reason":"Planned new employee family leave"})
  assert request.status_code==201,request.text
  row=request.json();rid=row["id"]
  assert row["current_stage"]=="manager"
  assert c.post(f"/leave/requests/{rid}/review",headers=ORIGIN,json={
    "action":"approve","note":"Cannot approve own leave"}).status_code==403
  reserved=c.get(f"/leave/balances?year={fy}").json()
  assert next(x["used"] for x in reserved if x["leave_type"]=="casual")>=1
  switch(c,"qa.onboarding.manager@example.org")
  manager=c.post(f"/leave/requests/{rid}/review",headers=ORIGIN,json={
      "action":"approve","note":"Reporting manager approval"})
  assert manager.status_code==200,manager.text
  assert manager.json()["current_stage"]=="hr"
  switch(c,"payroll.hr.qa@example.org")
  reviewed=c.post(f"/leave/requests/{rid}/review",headers=ORIGIN,json={
      "action":"approve","note":"HR verified approval"})
  assert reviewed.status_code==200,reviewed.text
  assert reviewed.json()["status"]=="approved"
  switch(c,email)
  assert any(x["id"]==rid and x["status"]=="approved"
      for x in c.get("/leave/requests?scope=mine").json())
  assert c.get(f"/leave/requests/{rid}/history").status_code==200
  assert c.post("/auth/logout",headers=ORIGIN).status_code==200
  assert c.get("/me").status_code==401
  assert login(c,email,PASS)["role"]=="employee"
