"""Performance & growth role permissions and lifecycle integration tests."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, PASS, ORIGIN

def test_goals_reviews_and_development_permissions():
    with TestClient(app) as c:
        admin, hr, one, other = seed(c)
        future=(date.today()+timedelta(days=90)).isoformat()
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)

        goal=c.post("/performance/goals",headers=ORIGIN,json={
            "employee_id":one,"title":"Improve release quality","description":"Reduce regression escapes",
            "target_date":future})
        assert goal.status_code==201,goal.text
        gid=goal.json()["id"]
        assert c.post("/performance/goals",headers=ORIGIN,json={
            "employee_id":other,"title":"Cross employee write","target_date":future}).status_code==403
        assert c.get("/performance/goals?employee_id="+str(other)).status_code==403
        assert all(row["employee_id"]==one for row in c.get("/performance/goals").json())
        done=c.patch(f"/performance/goals/{gid}/progress",headers=ORIGIN,json={"progress":100})
        assert done.status_code==200 and done.json()["status"]=="completed"
        assert c.patch(f"/performance/goals/{gid}/progress",headers=ORIGIN,json={"progress":101}).status_code==422

        plan=c.post("/performance/plans",headers=ORIGIN,json={
            "employee_id":one,"skill":"Architecture","action":"Complete internal design review",
            "target_date":future})
        assert plan.status_code==201,plan.text
        pid=plan.json()["id"]
        assert c.patch(f"/performance/plans/{pid}",headers=ORIGIN,json={
            "status":"in_progress"}).status_code==200
        assert c.post("/performance/cycles",headers=ORIGIN,json={
            "name":"QA Cycle "+str(one),"start_date":date.today().isoformat(),
            "end_date":future}).status_code==403

        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.other.qa@example.org",PASS)
        assert c.patch(f"/performance/plans/{pid}",headers=ORIGIN,json={
            "status":"completed"}).status_code==404
        assert c.patch(f"/performance/goals/{gid}/progress",headers=ORIGIN,json={
            "progress":50}).status_code==404

        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        cycle=c.post("/performance/cycles",headers=ORIGIN,json={
            "name":"QA Review "+str(one),"start_date":date.today().isoformat(),
            "end_date":future})
        assert cycle.status_code==201,cycle.text
        cid=cycle.json()["id"]
        assert c.post("/performance/cycles",headers=ORIGIN,json={
            "name":"QA Review "+str(one),"start_date":date.today().isoformat(),
            "end_date":future}).status_code==409
        c.post("/auth/logout",headers=ORIGIN)

        login(c,"payroll.person.qa@example.org",PASS)
        review=c.post("/performance/reviews",headers=ORIGIN,json={
            "employee_id":one,"cycle_id":cid,"self_notes":"Delivered agreed goals for this review cycle."})
        assert review.status_code==201,review.text
        rid=review.json()["id"]
        assert c.post("/performance/reviews",headers=ORIGIN,json={
            "employee_id":one,"cycle_id":cid,"self_notes":"Duplicate"}).status_code==409
        assert c.post(f"/performance/reviews/{rid}/manager",headers=ORIGIN,json={
            "rating":4,"feedback":"Strong delivery throughout the cycle."}).status_code==404

        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        r=c.post(f"/performance/reviews/{rid}/manager",headers=ORIGIN,json={
            "rating":4,"feedback":"Strong delivery throughout the cycle."})
        assert r.status_code==200,r.text
        assert r.json()["status"]=="completed" and r.json()["manager_rating"]==4
        assert c.post(f"/performance/reviews/{rid}/manager",headers=ORIGIN,json={
            "rating":4,"feedback":"Double review should fail."}).status_code==409
