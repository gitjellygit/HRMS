"""Device can be registered before employee exists, but cannot upload activity."""
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import login, seed, PASS, ORIGIN

def test_one_use_invite_pending_assignment_and_heartbeat_gate():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        invited=c.post("/activity-agent/invitations",headers=ORIGIN)
        assert invited.status_code==201,invited.text
        code=invited.json()["invitation_code"]
        assert len(code)>20
        c.post("/auth/logout",headers=ORIGIN)
        pending=c.post("/activity-agent/register",json={"invitation_code":code,"device_label":"JG-LAP-021"})
        assert pending.status_code==201,pending.text
        device_id=pending.json()["device_id"]
        token=pending.json()["token"]
        assert c.post("/activity-agent/register",json={"invitation_code":code,"device_label":"JG-LAP-022"}).status_code==401
        auth={"Authorization":"Bearer "+token}
        assert c.get("/activity-agent/status",headers=auth).json()=={"status":"pending","assigned":False}
        assert c.post("/activity-agent/heartbeat",headers={**auth,"Content-Type":"application/json"},
             json={"state":"monitoring","active_seconds":1,"idle_seconds":0,"apps":{"chrome":1}}).status_code==403
        assert c.get("/activity-agent/status").status_code==401
        login(c,"admin@example.com","test-admin-password-12345")
        devices=c.get("/activity-agent/devices").json()
        p=next(x for x in devices if x["id"]==device_id)
        assert p["status"]=="pending" and p["employee_id"] is None
        assert p["apps"]=={} and p["active_seconds"]==0
        assert c.post(f"/activity-agent/devices/{device_id}/assign",headers=ORIGIN,
              json={"employee_id":employee}).status_code==200
        assert c.get("/activity-agent/status",headers=auth).json()=={"status":"assigned","assigned":True}
        beat=c.post("/activity-agent/heartbeat",headers={**ORIGIN,**auth,"Content-Type":"application/json"},
            json={"state":"monitoring","active_seconds":120,"idle_seconds":15,"apps":{"code":100}})
        assert beat.status_code==200,beat.text
        assert c.post(f"/activity-agent/devices/{device_id}/assign",headers=ORIGIN,
              json={"employee_id":other}).status_code==409
        c.post(f"/activity-agent/devices/{device_id}/revoke",headers=ORIGIN)
        assert c.get("/activity-agent/status",headers=auth).status_code==401

def test_only_hr_may_issue_invites_or_assign_devices():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        invited=c.post("/activity-agent/invitations",headers=ORIGIN)
        assert invited.status_code==201
        code=invited.json()["invitation_code"]
        c.post("/auth/logout",headers=ORIGIN)
        device=c.post("/activity-agent/register",json={"invitation_code":code,"device_label":"JG-IT-012"})
        assert device.status_code==201
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        assert c.post("/activity-agent/invitations",headers=ORIGIN).status_code==403
        assert c.post(f"/activity-agent/devices/{device.json()['device_id']}/assign",
           json={"employee_id":employee},headers=ORIGIN).status_code==403
