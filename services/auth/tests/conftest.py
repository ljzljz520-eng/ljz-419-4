import os
import pathlib
import tempfile

# Point the service at a throwaway database BEFORE importing app modules.
_tmpdir = tempfile.mkdtemp(prefix="auth-test-")
os.environ["DATABASE_URL"] = "sqlite:///{}/test.db".format(_tmpdir)
os.environ["JWT_SECRET"] = "test-secret"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

SERVICE_DIR = pathlib.Path(__file__).resolve().parents[1]

_cfg = Config(str(SERVICE_DIR / "alembic.ini"))
_cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
command.upgrade(_cfg, "head")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def register(username, password="secret123", role="customer"):
    return client.post("/auth/register", json={
        "username": username, "password": password, "role": role,
    })


def login(username, password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def token_of(username, password="secret123"):
    resp = login(username, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": "Bearer " + token}
