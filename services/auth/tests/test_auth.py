from conftest import auth_header, client, login, register, token_of


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_login():
    resp = register("alice")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == "alice"
    assert body["role"] == "customer"

    token = token_of("alice")
    verify = client.get("/auth/verify", headers=auth_header(token))
    assert verify.status_code == 200
    assert verify.json()["username"] == "alice"


def test_register_duplicate_username_conflict():
    register("bob")
    resp = register("bob")
    assert resp.status_code == 409


def test_register_unknown_role_rejected():
    resp = register("carol", role="superuser")
    assert resp.status_code == 400


def test_login_wrong_password():
    register("dave")
    resp = login("dave", "wrong-password")
    assert resp.status_code == 401


def test_verify_without_token_rejected():
    assert client.get("/auth/verify").status_code == 401


def test_verify_with_garbage_token_rejected():
    resp = client.get("/auth/verify", headers=auth_header("not-a-token"))
    assert resp.status_code == 401


def test_users_list_requires_admin():
    register("erin")
    token = token_of("erin")
    assert client.get("/auth/users", headers=auth_header(token)).status_code == 403

    admin_token = token_of("admin", "admin123")
    resp = client.get("/auth/users", headers=auth_header(admin_token))
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()["users"]]
    assert "admin" in usernames and "erin" in usernames


def test_get_user_by_id_staff_only():
    register("frank")
    customer_token = token_of("frank")
    assert client.get("/auth/users/1", headers=auth_header(customer_token)).status_code == 403

    register("gina", role="agent")
    agent_token = token_of("gina")
    resp = client.get("/auth/users/1", headers=auth_header(agent_token))
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"

    assert client.get("/auth/users/9999", headers=auth_header(agent_token)).status_code == 404


def test_roles_seeded_by_migration():
    resp = client.get("/auth/roles")
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {"admin", "agent", "customer"}


def test_trace_id_echoed_in_response_header():
    resp = client.get("/health", headers={"X-Trace-ID": "trace-abc-123"})
    assert resp.headers["X-Trace-ID"] == "trace-abc-123"
    generated = client.get("/health")
    assert generated.headers["X-Trace-ID"]
