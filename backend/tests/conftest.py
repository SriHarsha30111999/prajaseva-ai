import os
import tempfile

# Use an isolated temp data dir BEFORE the app is imported.
os.environ["PRAJASEVA_DATA_DIR"] = tempfile.mkdtemp(prefix="prajaseva_test_")
os.environ.pop("ANTHROPIC_API_KEY", None)  # tests always run in demo AI mode
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.seed import seed


@pytest.fixture()
def client():
    with SessionLocal() as db:
        seed(db)  # fresh demo data for every test
    with TestClient(app) as c:
        yield c


PASSWORDS = {"vro": "vro123", "inspector": "inspector123", "tahsildar": "tahsildar123", "admin": "admin123"}


@pytest.fixture()
def as_user(client):
    def _login(username):
        r = client.post("/api/auth/login", json={"username": username, "password": PASSWORDS[username]})
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture()
def app_by_status(client, as_user):
    def _find(status):
        rows = client.get("/api/applications", params={"status": status}, headers=as_user("admin")).json()
        assert rows, f"no seeded application with status {status}"
        return rows[0]["id"]

    return _find
