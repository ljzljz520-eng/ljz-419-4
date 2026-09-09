import os
import pathlib
import tempfile

# Point the service at a throwaway database BEFORE importing app modules.
_tmpdir = tempfile.mkdtemp(prefix="ticket-test-")
os.environ["DATABASE_URL"] = "sqlite:///{}/test.db".format(_tmpdir)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

SERVICE_DIR = pathlib.Path(__file__).resolve().parents[1]

_cfg = Config(str(SERVICE_DIR / "alembic.ini"))
_cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
command.upgrade(_cfg, "head")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth_client  # noqa: E402
from app.main import app, get_current_user  # noqa: E402

# Fake users standing in for the auth service.
USERS = {
    1: {"id": 1, "username": "admin", "role": "admin"},
    2: {"id": 2, "username": "agent01", "role": "agent"},
    3: {"id": 3, "username": "customer01", "role": "customer"},
    4: {"id": 4, "username": "customer02", "role": "customer"},
}

client = TestClient(app)


def as_user(user_id):
    """Make the next requests run as the given fake user."""
    app.dependency_overrides[get_current_user] = lambda: USERS[user_id]


@pytest.fixture(autouse=True)
def stub_auth_service(monkeypatch):
    """Replace outbound auth-service calls with the fake user table."""
    async def fake_fetch_user(user_id, authorization):
        from fastapi import HTTPException
        if user_id not in USERS:
            raise HTTPException(status_code=400, detail="assignee user not found")
        return USERS[user_id]

    monkeypatch.setattr(auth_client, "fetch_user", fake_fetch_user)
    yield
    app.dependency_overrides.clear()


def auth_header():
    return {"Authorization": "Bearer fake-token"}
