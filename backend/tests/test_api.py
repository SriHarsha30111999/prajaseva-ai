"""Backend tests: authentication, role permissions, workflow transitions."""
import jwt

from app.auth import ALGORITHM, SECRET_KEY


# ---------------------------------------------------------------- authentication
def test_login_success_and_me(client, as_user):
    h = as_user("vro")
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["role"] == "VRO"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "vro", "password": "nope"})
    assert r.status_code == 401


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/applications").status_code == 401
    assert client.get("/api/applications", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_token_rejected(client):
    tok = jwt.encode({"sub": "vro", "exp": 1}, SECRET_KEY, algorithm=ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_inactive_user_cannot_login(client, as_user):
    admin = as_user("admin")
    users = client.get("/api/admin/users", headers=admin).json()
    vro = next(u for u in users if u["username"] == "vro")
    client.post(f"/api/admin/users/{vro['id']}/toggle-active", headers=admin)
    assert client.post("/api/auth/login", json={"username": "vro", "password": "vro123"}).status_code == 401


# ---------------------------------------------------------------- role permissions
def test_roles_cannot_act_outside_their_role(client, as_user, app_by_status):
    sub, scr = app_by_status("SUBMITTED"), app_by_status("UNDER_SCRUTINY")
    fld, fin = app_by_status("AWAITING_FIELD_VERIFICATION"), app_by_status("AWAITING_FINAL_REVIEW")
    # Inspector / Tahsildar cannot do VRO things
    assert client.post(f"/api/applications/{sub}/start-scrutiny", headers=as_user("inspector")).status_code == 403
    body = {"field_verification_required": False, "remarks": "all documents fine"}
    assert client.post(f"/api/applications/{scr}/forward", json=body, headers=as_user("tahsildar")).status_code == 403
    # VRO cannot decide
    assert client.post(f"/api/applications/{fin}/decision", json={"decision": "APPROVE"}, headers=as_user("vro")).status_code == 403
    # VRO cannot submit a field report
    rep = {"observations": {}, "report_text": "A long enough report text."}
    assert client.post(f"/api/applications/{fld}/field-report", json=rep, headers=as_user("vro")).status_code == 403
    # Only admin can manage users
    assert client.get("/api/admin/users", headers=as_user("vro")).status_code == 403
    assert client.delete(f"/api/admin/applications/{sub}", headers=as_user("tahsildar")).status_code == 403


def test_ai_endpoints_are_role_protected(client, as_user, app_by_status):
    scr = app_by_status("UNDER_SCRUTINY")
    assert client.post(f"/api/applications/{scr}/ai/analyze", json={"lang": "en"}, headers=as_user("tahsildar")).status_code == 403


# ---------------------------------------------------------------- workflow transitions
def test_full_workflow_with_field_verification(client, as_user, app_by_status):
    app_id = app_by_status("SUBMITTED")
    vro, ri, th = as_user("vro"), as_user("inspector"), as_user("tahsildar")

    r = client.post(f"/api/applications/{app_id}/start-scrutiny", headers=vro)
    assert r.json()["status"] == "UNDER_SCRUTINY"

    # forwarding needs remarks
    bad = {"field_verification_required": True, "remarks": ""}
    assert client.post(f"/api/applications/{app_id}/forward", json=bad, headers=vro).status_code == 422
    ok = {"field_verification_required": True, "remarks": "Please verify residence"}
    r = client.post(f"/api/applications/{app_id}/forward", json=ok, headers=vro)
    assert r.json()["status"] == "AWAITING_FIELD_VERIFICATION" and r.json()["current_stage"] == "REVENUE_INSPECTOR"

    obs = {"visit_date": "2026-11-10", "persons_met": "Applicant", "residence_type": "Rented room", "livelihood": "Labour"}
    r = client.post(f"/api/applications/{app_id}/ai/field-report", json=obs, headers=ri)
    assert r.status_code == 200 and r.json()["mode"] == "demo"
    rep = {"observations": obs, "report_text": r.json()["output"]["report_text"], "ai_mode": "demo"}
    r = client.post(f"/api/applications/{app_id}/field-report", json=rep, headers=ri)
    assert r.json()["status"] == "AWAITING_FINAL_REVIEW" and len(r.json()["reports"]) == 1

    r = client.post(f"/api/applications/{app_id}/ai/summary", json={"lang": "en"}, headers=th)
    assert r.status_code == 200 and r.json()["mode"] == "demo" and r.json()["output"]["summary"]
    r = client.post(f"/api/applications/{app_id}/decision", json={"decision": "APPROVE", "remarks": "Verified"}, headers=th)
    assert r.json()["status"] == "APPROVED" and r.json()["current_stage"] == "COMPLETED"

    actions = [h["action"] for h in r.json()["history"]]
    for a in ("SUBMITTED", "SCRUTINY_STARTED", "FORWARDED_FOR_FIELD_VERIFICATION", "FIELD_REPORT_SUBMITTED", "APPROVED"):
        assert a in actions
    last = r.json()["history"][-1]
    assert (last["previous_status"], last["new_status"], last["role"]) == ("AWAITING_FINAL_REVIEW", "APPROVED", "TAHSILDAR")


def test_field_verification_is_optional(client, as_user, app_by_status):
    app_id = app_by_status("UNDER_SCRUTINY")
    body = {"field_verification_required": False, "remarks": "Documents consistent"}
    r = client.post(f"/api/applications/{app_id}/forward", json=body, headers=as_user("vro"))
    assert r.json()["status"] == "AWAITING_FINAL_REVIEW" and r.json()["reports"] == []


def test_vro_return_and_resubmit(client, as_user, app_by_status):
    app_id = app_by_status("UNDER_SCRUTINY")
    vro, admin = as_user("vro"), as_user("admin")
    assert client.post(f"/api/applications/{app_id}/return", json={"remarks": ""}, headers=vro).status_code == 422
    r = client.post(f"/api/applications/{app_id}/return", json={"remarks": "Upload ration card"}, headers=vro)
    assert r.json()["status"] == "RETURNED_FOR_CORRECTION"
    r = client.post(f"/api/applications/{app_id}/resubmit", headers=admin)
    assert r.json()["status"] == "SUBMITTED"


def test_tahsildar_reject_and_return_need_remarks(client, as_user, app_by_status):
    app_id = app_by_status("AWAITING_FINAL_REVIEW")
    th = as_user("tahsildar")
    assert client.post(f"/api/applications/{app_id}/decision", json={"decision": "REJECT"}, headers=th).status_code == 422
    body = {"decision": "RETURN", "remarks": "Please recheck income"}
    r = client.post(f"/api/applications/{app_id}/decision", json=body, headers=th)
    assert r.json()["status"] == "UNDER_SCRUTINY" and r.json()["current_stage"] == "VRO"


def test_invalid_transitions_are_blocked(client, as_user, app_by_status):
    sub = app_by_status("SUBMITTED")
    # Cannot forward before scrutiny starts
    body = {"field_verification_required": False, "remarks": "skipping"}
    assert client.post(f"/api/applications/{sub}/forward", json=body, headers=as_user("vro")).status_code == 409
    # Tahsildar cannot decide an application still in scrutiny
    scr = app_by_status("UNDER_SCRUTINY")
    assert client.post(f"/api/applications/{scr}/decision", json={"decision": "APPROVE"}, headers=as_user("tahsildar")).status_code == 409
    # Completed applications are final
    done = app_by_status("APPROVED")
    late = {"decision": "REJECT", "remarks": "changed mind"}
    assert client.post(f"/api/applications/{done}/decision", json=late, headers=as_user("tahsildar")).status_code == 409


# ---------------------------------------------------------------- dashboard + AI labelling
def test_dashboard_stats_come_from_database(client, as_user):
    s = client.get("/api/dashboard", headers=as_user("vro")).json()["stats"]
    assert s["total"] == 11
    parts = ("pending", "under_scrutiny", "returned", "awaiting_field", "awaiting_final", "approved", "rejected")
    assert s["total"] == sum(s[k] for k in parts)


def test_ai_demo_mode_is_labelled_and_detects_issues(client, as_user):
    # Seeded: "Suresh Goud" has a salary slip (280000) vs declared income (120000)
    rows = client.get("/api/applications", params={"status": "UNDER_SCRUTINY", "q": "Suresh"}, headers=as_user("vro")).json()
    r = client.post(f"/api/applications/{rows[0]['id']}/ai/analyze", json={"lang": "en"}, headers=as_user("vro")).json()
    assert r["mode"] == "demo" and r["model"].startswith("none")
    assert any(d["field"] == "income" for d in r["output"]["discrepancies"])
    assert client.get("/api/ai/status", headers=as_user("vro")).json()["mode"] == "demo"
