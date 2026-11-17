"""Isolated People Operations and activity-agent P0 regression contracts."""
import io
import hashlib
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import login, seed, PASS, ORIGIN

def as_user(c,email,password=PASS):
    c.post("/auth/logout",headers=ORIGIN)
    login(c,email,password)

def test_device_enrollment_heartbeat_reason_and_private_status():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        enrolled=c.post("/activity-agent/devices",json={"employee_id":one,"device_label":"QA Windows 11"},headers=ORIGIN)
        assert enrolled.status_code==201,enrolled.text
        token=enrolled.json()["token"]
        device_id=enrolled.json()["device_id"]
        beat=c.post("/activity-agent/heartbeat",headers={"Authorization":"Bearer "+token},json={
            "state":"monitoring","active_seconds":345,"idle_seconds":55,"apps":{"chrome":145,"code":200}})
        assert beat.status_code==200,beat.text
        devices=c.get("/activity-agent/devices")
        assert devices.status_code==200
        device=next(item for item in devices.json() if item["id"]==device_id)
        assert device["status"]=="monitoring" and device["apps"]["code"]==200
        bad=c.post("/activity-agent/heartbeat",headers={"Authorization":"Bearer "+token},json={
            "state":"stopped","active_seconds":350,"idle_seconds":55,"exit_reason":"short"})
        assert bad.status_code==422
        stopped=c.post("/activity-agent/heartbeat",headers={"Authorization":"Bearer "+token},json={
            "state":"stopped","active_seconds":350,"idle_seconds":55,
            "exit_reason":"Employee ended the work session for the day.","apps":{"chrome":150,"code":200}})
        assert stopped.status_code==200,stopped.text
        data=next(x for x in c.get("/activity-agent/devices").json() if x["id"]==device_id)
        assert data["status"]=="stopped"
        assert "ended" in data["exit_reason"]
        as_user(c,"payroll.person.qa@example.org")
        assert c.get("/activity-agent/devices").status_code==403
        assert c.post("/activity-agent/devices",json={"employee_id":other},headers=ORIGIN).status_code==403
        as_user(c,"admin@example.com","test-admin-password-12345")
        revoke=c.post(f"/activity-agent/devices/{device_id}/revoke",headers=ORIGIN)
        assert revoke.status_code==200
        assert c.post("/activity-agent/heartbeat",headers={"Authorization":"Bearer "+token},json={
            "state":"monitoring","active_seconds":1,"idle_seconds":0}).status_code==401

def test_onboarding_categories_assignment_and_visibility():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        new=c.post("/people/onboarding/categories",headers=ORIGIN,json={"slug":"qa_access","display_name":"QA Access"})
        assert new.status_code==201,new.text
        category_id=new.json()["id"]
        task=c.post("/people/onboarding",headers=ORIGIN,json={"employee_id":one,"assigned_to":other,
            "title":"Provide QA project access","category":"qa_access"})
        assert task.status_code==201,task.text
        tasks=c.get("/people/onboarding").json()
        assert any(t["id"]==task.json()["id"] and t["assigned_to"]==other for t in tasks)
        renamed=c.put(f"/people/onboarding/categories/{category_id}",headers=ORIGIN,json={"display_name":"Testing Access","active":True})
        assert renamed.status_code==200
        archived=c.delete(f"/people/onboarding/categories/{category_id}",headers=ORIGIN)
        assert archived.status_code==200
        rejected=c.post("/people/onboarding",headers=ORIGIN,json={"employee_id":one,"assigned_to":other,
            "title":"New testing request","category":"qa_access"})
        assert rejected.status_code==422
        as_user(c,"payroll.other.qa@example.org")
        visible=c.get("/people/onboarding").json()
        assert any(t["id"]==task.json()["id"] for t in visible)
        assert c.post("/people/onboarding/categories",headers=ORIGIN,json={"slug":"bad","display_name":"Bad"}).status_code==403

def test_announcement_audience_isolation_with_media():
    from PIL import Image
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        stream=io.BytesIO();Image.new("RGB",(40,40),(160,30,50)).save(stream,"PNG")
        published=c.post("/people/announcements/with-media",headers=ORIGIN,
             data={"title":"QA Arrival Notice","body":"This is a restricted pilot announcement.",
                   "requires_ack":"true","audience_json":f"[{one}]"},
             files={"image":("qa.png",stream.getvalue(),"image/png")})
        assert published.status_code==201,published.text
        announcement_id=published.json()["id"]
        assert published.json()["recipients"]==1
        as_user(c,"payroll.other.qa@example.org")
        assert all(n["id"]!=announcement_id for n in c.get("/people/announcements").json())
        assert c.get(f"/people/announcements/{announcement_id}/image").status_code==403
        as_user(c,"payroll.person.qa@example.org")
        assert any(n["id"]==announcement_id for n in c.get("/people/announcements").json())
        assert c.get(f"/people/announcements/{announcement_id}/image").status_code==200

def test_offer_template_edit_archive_and_logo_document():
    from PIL import Image
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        logo=io.BytesIO();Image.new("RGB",(220,80),(30,90,120)).save(logo,"PNG")
        saved=c.post("/people/letterhead/logo",headers=ORIGIN,files={"file":("brand.png",logo.getvalue(),"image/png")})
        assert saved.status_code==200,saved.text
        made=c.post("/people/offer-templates",headers=ORIGIN,json={
            "name":"QA Branded Employment Offer",
            "content":"Dear {{employee_name}}, you are offered the position {{job_title}} and annual CTC {{annual_ctc}}."})
        assert made.status_code==201,made.text
        template_id=made.json()["id"]
        edit=c.put(f"/people/offer-templates/{template_id}",headers=ORIGIN,json={
            "name":"QA Branded Employment Letter",
            "content":"Dear {{employee_name}}, your position is {{job_title}} and your CTC is INR {{annual_ctc}}."})
        assert edit.status_code==200,edit.text
        offer=c.post("/people/offers",headers=ORIGIN,json={"employee_id":one,"template_id":template_id,
            "title":"QA Analyst","annual_ctc":450000,"joining_date":date.today().isoformat()})
        assert offer.status_code==201,offer.text
        pdf=c.get(f"/people/offers/{offer.json()['id']}.pdf")
        assert pdf.status_code==200 and pdf.content.startswith(b"%PDF-")
        archived=c.delete(f"/people/offer-templates/{template_id}",headers=ORIGIN)
        assert archived.status_code==200
        assert c.put(f"/people/offer-templates/{template_id}",headers=ORIGIN,json={
            "name":"QA Branded Employment Letter",
            "content":"Dear {{employee_name}}, your position is {{job_title}} and your CTC is INR {{annual_ctc}}."}).status_code==409
