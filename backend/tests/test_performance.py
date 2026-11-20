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

def test_learning_career_and_private_peer_feedback():
    with TestClient(app) as c:
        admin, hr, one, other = seed(c)
        future=(date.today()+timedelta(days=90)).isoformat()
        learning=c.post("/growth/learning",headers=ORIGIN,json={
            "employee_id":one,"title":"System design workshop","provider":"Internal",
            "target_date":future})
        assert learning.status_code==201,learning.text
        cid=c.post("/performance/cycles",headers=ORIGIN,json={
            "name":"Confidential peers "+str(one),"start_date":date.today().isoformat(),
            "end_date":future})
        assert cid.status_code==201,cid.text
        cycle=cid.json()["id"]
        assignment=c.post("/growth/feedback-assignments",headers=ORIGIN,json={
            "employee_id":one,"reviewer_id":other,"cycle_id":cycle})
        assert assignment.status_code==201,assignment.text
        aid=assignment.json()["id"]
        career=c.post("/growth/career",headers=ORIGIN,json={
            "employee_id":one,"target_role":"Senior Engineer",
            "requirements":"Lead two technical designs and mentor junior engineers.",
            "target_date":future})
        assert career.status_code==201,career.text
        career_id=career.json()["id"]
        c.post("/auth/logout",headers=ORIGIN)

        login(c,"payroll.person.qa@example.org",PASS)
        assert c.post("/growth/career",headers=ORIGIN,json={
            "employee_id":one,"target_role":"Manager",
            "requirements":"Complete leadership development requirements.",
            "target_date":future}).status_code==403
        summary=c.get(f"/growth/feedback-summary/{one}/{cycle}")
        assert summary.status_code==200 and summary.json()["average_score"] is None
        assert c.get(f"/growth/feedback-summary/{other}/{cycle}").status_code==403
        assert c.post(f"/growth/feedback-assignments/{aid}/submit",headers=ORIGIN,json={
            "score":5,"feedback":"Unauthorized submission from the subject employee."}).status_code==404
        assert c.patch(f"/growth/career/{career_id}",headers=ORIGIN,json={
            "status":"achieved"}).status_code==404
        c.post("/auth/logout",headers=ORIGIN)

        login(c,"payroll.other.qa@example.org",PASS)
        mine=c.get("/growth/feedback-assignments")
        assert mine.status_code==200 and any(x["id"]==aid for x in mine.json())
        submitted=c.post(f"/growth/feedback-assignments/{aid}/submit",headers=ORIGIN,json={
            "score":4,"feedback":"Consistently collaborative and technically reliable."})
        assert submitted.status_code==200,submitted.text
        assert c.post(f"/growth/feedback-assignments/{aid}/submit",headers=ORIGIN,json={
            "score":5,"feedback":"Duplicate confidential feedback submission."}).status_code==409
        assert c.get("/growth/learning?employee_id="+str(one)).status_code==403
        c.post("/auth/logout",headers=ORIGIN)

        login(c,"payroll.person.qa@example.org",PASS)
        summary=c.get(f"/growth/feedback-summary/{one}/{cycle}").json()
        assert summary["response_count"]==1 and summary["average_score"] is None
        assert "confidential_reviews" not in summary
        c.post("/auth/logout",headers=ORIGIN)

        login(c,"payroll.hr.qa@example.org",PASS)
        summary=c.get(f"/growth/feedback-summary/{one}/{cycle}").json()
        assert summary["average_score"]==4.0
        assert summary["confidential_reviews"][0]["reviewer_id"]==other
