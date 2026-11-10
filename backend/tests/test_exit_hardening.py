"""Exit configuration, pending task protection and HR audit smoke tests."""
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, ORIGIN


def test_exit_tasks_block_final_settlement_and_templates_can_be_disabled():
    with TestClient(app) as client:
        admin,hr,worker,other=seed(client)
        created=client.post("/exit-workflow/templates",headers=ORIGIN,json={
            "title":"Collect signed handover certificate",
            "assignee_role":"employee","active":True})
        assert created.status_code==201,created.text
        template_id=created.json()["id"]
        changed=client.put(f"/exit-workflow/templates/{template_id}",headers=ORIGIN,json={
            "title":"Collect signed handover certificate",
            "assignee_role":"employee","active":False})
        assert changed.status_code==200,changed.text
        assert changed.json()["active"] is False
        case=client.post("/exit-workflow/cases",headers=ORIGIN,json={
            "employee_id":worker,
            "reason":"HR initiated exit for resignation and handover testing.",
            "notice_days":30})
        assert case.status_code==201,case.text
        case_id=case.json()["id"]
        deactivate=client.post(f"/core/employees/{worker}/deactivate",headers=ORIGIN,
            json={"reason":"Attempt to skip pending clearance and final settlement"})
        assert deactivate.status_code==409,deactivate.text
        assert deactivate.json()["detail"]["field"]=="exit_case"
        tasks=client.get(f"/exit-workflow/cases/{case_id}/tasks")
        assert tasks.status_code==200,tasks.text
        assert len(tasks.json())>=1
        assert not any(task["title"]=="Collect signed handover certificate" for task in tasks.json())
        blocked=client.post(f"/people/exits/{case_id}/review",headers=ORIGIN,json={
            "status":"settled","clearance_assets":True,"clearance_it":True,
            "clearance_finance":True,"final_settlement_inr":"0",
            "final_settlement_note":"Reviewing exit checklist before settlement."})
        assert blocked.status_code==422,blocked.text
        assert blocked.json()["detail"]["field"]=="exit_tasks"
        assert len(blocked.json()["detail"]["pending_tasks"])>=1
        # HR may only complete HR tasks; employee tasks remain theirs.
        staff_task=next(t for t in tasks.json() if t["assignee_role"]=="employee")
        completed=client.post(f'/exit-workflow/tasks/{staff_task["id"]}/complete',
            headers=ORIGIN,json={"note":"Handover documents verified and signed."})
        assert completed.status_code==200,completed.text
