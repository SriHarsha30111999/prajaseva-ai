"""Security + integration tests: RBAC matrix, uploads, token handling, audit integrity, live-AI error handling."""
import io
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import ai_service
from app.auth import ALGORITHM, SECRET_KEY, hash_password, verify_password
from app.main import app as fastapi_app

V, R, T, A = "vro", "inspector", "tahsildar", "admin"
EVERYONE = {V, R, T, A}

# (method, path template, roles allowed). Every protected route must be listed here.
ACL = [
    ("GET", "/api/auth/me", EVERYONE),
    ("GET", "/api/ai/status", EVERYONE),
    ("GET", "/api/dashboard", EVERYONE),
    ("GET", "/api/applications", EVERYONE),
    ("GET", "/api/applications/{app}", EVERYONE),
    ("GET", "/api/history", EVERYONE),
    ("GET", "/api/documents/{doc}/file", EVERYONE),
    ("POST", "/api/applications/{app}/start-scrutiny", {V}),
    ("POST", "/api/applications/{app}/ai/analyze", {V}),
    ("POST", "/api/applications/{app}/forward", {V}),
    ("POST", "/api/applications/{app}/return", {V}),
    ("POST", "/api/applications/{app}/documents", {V, A}),
    ("POST", "/api/applications/{app}/ai/field-report", {R}),
    ("POST", "/api/applications/{app}/field-report", {R}),
    ("POST", "/api/applications/{app}/ai/summary", {T}),
    ("POST", "/api/applications/{app}/decision", {T}),
    ("POST", "/api/applications/{app}/resubmit", {A}),
    ("DELETE", "/api/admin/applications/{app}", {A}),
    ("GET", "/api/admin/users", {A}),
    ("POST", "/api/admin/users", {A}),
    ("POST", "/api/admin/users/{user}/toggle-active", {A}),
    ("POST", "/api/admin/reset-demo-data", {A}),
]
PUBLIC = {("POST", "/api/auth/login"), ("GET", "/api/meta/demo-users"), ("GET", "/api/health")}


def test_acl_table_covers_every_route():
    routes = {(m, r.path) for r in fastapi_app.routes if hasattr(r, "methods") and r.path.startswith("/api")
              for m in r.methods if m not in ("HEAD", "OPTIONS")}
    listed = {(m, p.replace("{app}", "{app_id}").replace("{doc}", "{doc_id}").replace("{user}", "{user_id}")) for m, p, _ in ACL}
    assert routes - listed - PUBLIC == set(), "route(s) missing from the RBAC matrix"


def test_rbac_matrix(client, as_user):
    admin = as_user(A)
    ids = {"app": client.get("/api/applications", headers=admin).json()[0]["id"], "user": 1, "doc": 1}
    heads = {u: as_user(u) for u in EVERYONE}
    for method, tpl, allowed in ACL:
        if "reset-demo" in tpl:
            continue  # destructive: only the negative cases are exercised below
        url = tpl.format(**ids)
        r = client.request(method, url, json={})
        assert r.status_code == 401, f"{method} {url} without token -> {r.status_code}"
    for method, tpl, allowed in ACL:
        url = tpl.format(**ids)
        for user in EVERYONE - allowed:
            r = client.request(method, url, json={}, headers=heads[user])
            assert r.status_code == 403, f"{method} {url} as {user} -> {r.status_code} (expected 403)"


# ---------------------------------------------------------------- tokens + passwords
def _tok(**kw):
    payload = {"sub": "vro", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    payload.update(kw)
    return jwt.encode(payload, kw.pop("_key", SECRET_KEY), algorithm=ALGORITHM)


def test_forged_and_malformed_tokens_rejected(client):
    bad = [
        jwt.encode({"sub": "vro", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret", algorithm=ALGORITHM),
        jwt.encode({"sub": "vro"}, SECRET_KEY, algorithm=ALGORITHM),  # no exp
        jwt.encode({"sub": "ghost", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM),
        jwt.encode({"sub": "vro", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, None, algorithm="none"),
    ]
    for t in bad:
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_valid_token_is_accepted(client):
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_tok()}"}).status_code == 200


def test_role_comes_from_database_not_token(client):
    # A token claiming ADMIN for the vro user must not grant admin rights.
    t = jwt.encode({"sub": "vro", "role": "ADMIN", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM)
    assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {t}"}).status_code == 403


def test_passwords_are_salted_hashes(client):
    from app.database import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        u = db.query(User).filter_by(username="vro").one()
        assert "vro123" not in u.password_hash and "$" in u.password_hash
        assert verify_password("vro123", u.password_hash) and not verify_password("x", u.password_hash)
    assert hash_password("same") != hash_password("same")  # random salt


def test_demo_credentials_endpoint_can_be_disabled(client, monkeypatch):
    assert client.get("/api/meta/demo-users").json()
    monkeypatch.setenv("SHOW_DEMO_CREDENTIALS", "false")
    assert client.get("/api/meta/demo-users").json() == []


# ---------------------------------------------------------------- uploads
def _upload(client, headers, app_id, name="a.txt", content=b"Name: X\n", doc_type="AADHAAR"):
    return client.post(f"/api/applications/{app_id}/documents", headers=headers, data={"doc_type": doc_type},
                       files={"file": (name, io.BytesIO(content))})


def test_upload_validation_and_download_auth(client, as_user, app_by_status):
    app_id = app_by_status("UNDER_SCRUTINY")
    vro = as_user(V)
    assert _upload(client, vro, app_id, "evil.exe", b"MZ").status_code == 415
    assert _upload(client, vro, app_id, "a.txt", b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert _upload(client, vro, app_id, "a.txt", b"").status_code == 422
    assert _upload(client, vro, app_id, doc_type="HACK").status_code == 422
    r = _upload(client, vro, app_id, "../../etc/passwd.txt", b"Name: Y\n")  # path components are stripped
    assert r.status_code == 200
    doc = r.json()["documents"][-1]
    assert "/" not in doc["filename"] and ".." not in doc["filename"]
    assert client.get(f"/api/documents/{doc['id']}/file").status_code == 401  # no token
    assert client.get(f"/api/documents/{doc['id']}/file", headers=vro).status_code == 200


def test_upload_blocked_outside_scrutiny(client, as_user, app_by_status):
    done = app_by_status("APPROVED")
    assert _upload(client, as_user(A), done).status_code == 409
    sub = app_by_status("SUBMITTED")
    assert _upload(client, as_user(V), sub).status_code == 409  # VRO must start scrutiny first


# ---------------------------------------------------------------- audit integrity
def test_archive_keeps_history_and_hides_record(client, as_user, app_by_status):
    app_id = app_by_status("APPROVED")
    admin = as_user(A)
    before = len(client.get(f"/api/applications/{app_id}", headers=admin).json()["history"])
    assert client.delete(f"/api/admin/applications/{app_id}", headers=admin).status_code == 200
    assert all(a["id"] != app_id for a in client.get("/api/applications", headers=admin).json())
    d = client.get(f"/api/applications/{app_id}", headers=admin).json()
    assert d["archived"] and d["available_actions"] == [] and len(d["history"]) == before + 1
    assert d["history"][-1]["action"] == "ARCHIVED"
    assert client.get("/api/dashboard", headers=admin).json()["stats"]["total"] == 10
    assert client.delete(f"/api/admin/applications/{app_id}", headers=admin).status_code == 409


def test_no_api_can_modify_history():
    for r in fastapi_app.routes:
        if hasattr(r, "methods") and "history" in r.path:
            assert r.methods <= {"GET", "HEAD"}, f"{r.path} allows {r.methods}"


def test_return_and_resubmit_are_recorded(client, as_user, app_by_status):
    app_id = app_by_status("UNDER_SCRUTINY")
    client.post(f"/api/applications/{app_id}/return", json={"remarks": "Missing ration card"}, headers=as_user(V))
    r = client.post(f"/api/applications/{app_id}/resubmit", headers=as_user(A)).json()
    last2 = r["history"][-2:]
    assert [(h["action"], h["previous_status"], h["new_status"], h["role"]) for h in last2] == [
        ("RETURNED_FOR_CORRECTION", "UNDER_SCRUTINY", "RETURNED_FOR_CORRECTION", "VRO"),
        ("RESUBMITTED", "RETURNED_FOR_CORRECTION", "SUBMITTED", "ADMIN"),
    ]
    assert last2[0]["remarks"] == "Missing ration card"


def test_ai_mode_field_is_restricted(client, as_user, app_by_status):
    app_id = app_by_status("AWAITING_FIELD_VERIFICATION")
    body = {"observations": {}, "report_text": "A sufficiently long report.", "ai_mode": "totally-real-ai"}
    assert client.post(f"/api/applications/{app_id}/field-report", json=body, headers=as_user(R)).status_code == 422


# ---------------------------------------------------------------- live AI error handling (HTTP mocked; no real API call)
class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload, text

    def json(self):
        return self._p


def _live(monkeypatch, resp=None, exc=None):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")

    def fake_post(*a, **k):
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)


def _analysis_target(client, as_user):
    return client.get("/api/applications", params={"status": "UNDER_SCRUTINY"}, headers=as_user(V)).json()[0]["id"]


def test_live_ai_invalid_key_is_an_error_not_fake_output(client, as_user, monkeypatch):
    _live(monkeypatch, FakeResp(401, text='{"error":"invalid x-api-key"}'))
    app_id = _analysis_target(client, as_user)
    r = client.post(f"/api/applications/{app_id}/ai/analyze", json={"lang": "en"}, headers=as_user(V))
    assert r.status_code == 502 and "401" in r.json()["detail"]
    d = client.get(f"/api/applications/{app_id}", headers=as_user(V)).json()
    assert d["analysis"] is None  # nothing stored, nothing faked
    assert not any(h["action"].startswith("AI_") for h in d["history"])


def test_live_ai_network_error_and_bad_json(client, as_user, monkeypatch):
    app_id = _analysis_target(client, as_user)
    _live(monkeypatch, exc=ai_service.httpx.ConnectError("boom"))
    assert client.post(f"/api/applications/{app_id}/ai/analyze", json={"lang": "en"}, headers=as_user(V)).status_code == 502
    _live(monkeypatch, FakeResp(200, {"content": [{"type": "text", "text": "Sorry, I cannot help."}]}))
    assert client.post(f"/api/applications/{app_id}/ai/analyze", json={"lang": "en"}, headers=as_user(V)).status_code == 502
    _live(monkeypatch, FakeResp(200, {"content": [{"type": "text", "text": '{"missing_information": "not a list"}'}]}))
    assert client.post(f"/api/applications/{app_id}/ai/analyze", json={"lang": "en"}, headers=as_user(V)).status_code == 502


def test_live_ai_success_is_labelled_live(client, as_user, monkeypatch):
    good = '{"extracted_documents": [], "missing_information": ["x"], "discrepancies": [{"issue": "i", "severity": "weird"}], "field_verification_reason": "r", "suggested_next_step": "s"}'
    _live(monkeypatch, FakeResp(200, {"content": [{"type": "text", "text": "Here: " + good}]}))
    app_id = _analysis_target(client, as_user)
    r = client.post(f"/api/applications/{app_id}/ai/analyze", json={"lang": "en"}, headers=as_user(V)).json()
    assert r["mode"] == "live" and r["model"] and r["output"]["discrepancies"][0]["severity"] == "medium"
    assert client.get("/api/ai/status", headers=as_user(V)).json()["mode"] == "live"


def test_missing_key_means_demo_mode(client, as_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    assert client.get("/api/ai/status", headers=as_user(V)).json()["mode"] == "demo"
