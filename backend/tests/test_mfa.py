"""Authenticator enrollment, encrypted secret and 2FA login tests."""
import os
import time
import pyotp
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.main import app,SessionLocal,Employee
from app.security import MFAFactor
from app.payroll import SalaryStructure

ORIGIN={"Origin":"http://localhost:3000"}
PASS="MFA!TestingPass123"

def test_mfa_requires_key_and_otp(monkeypatch):
    from datetime import date
    with TestClient(app) as c:
        assert c.post("/auth/login",headers=ORIGIN,json={"email":"admin@example.com","password":"test-admin-password-12345"}).status_code==200
        admin=c.get("/me").json()["id"]
        email="mfa.user.qa@example.org"
        existing=next((u for u in c.get("/employees").json() if u["email"]==email),None)
        if not existing:
            made=c.post("/core/employees",headers=ORIGIN,json={
              "account":{"name":"MFA Tester","email":email,"password":PASS,"role":"employee",
                         "designation":"QA Specialist","department":"Quality",
                         "joining_date":date.today().isoformat()},
              "master":{"manager_id":admin}})
            assert made.status_code==201,made.text
            user_id=made.json()["id"]
        else:user_id=existing["id"]
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS}).status_code==200
        monkeypatch.delenv("HRMS_PII_KEY",raising=False)
        no_key=c.post("/security/mfa/setup",headers=ORIGIN,json={"current_password":PASS})
        assert no_key.status_code==503
        monkeypatch.setenv("HRMS_PII_KEY",Fernet.generate_key().decode())
        started=c.post("/security/mfa/setup",headers=ORIGIN,json={"current_password":PASS})
        assert started.status_code==200,started.text
        secret=started.json()["secret"]
        assert started.json()["otpauth_uri"].startswith("otpauth://totp/")
        with SessionLocal() as db:
            encrypted=db.get(MFAFactor,user_id).encrypted_secret
            assert secret not in encrypted
        otp=pyotp.TOTP(secret).now()
        confirmed=c.post("/security/mfa/enable",headers=ORIGIN,json={"code":otp})
        assert confirmed.status_code==200,confirmed.text
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS}).status_code==401
        assert c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS,"otp":"000000"}).status_code==401
        assert c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS,"otp":otp}).status_code==401
        future=pyotp.TOTP(secret).at(time.time()+30)
        success=c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS,"otp":future})
        assert success.status_code==200,success.text
        again=c.post("/auth/login",headers=ORIGIN,json={"email":email,"password":PASS,"otp":future})
        assert again.status_code==401
