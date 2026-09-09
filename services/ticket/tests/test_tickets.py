from conftest import as_user, auth_header, client


def create_ticket(title="refund request", priority="medium"):
    resp = client.post("/tickets", json={
        "title": title, "description": "customer asks for a refund", "priority": priority,
    }, headers=auth_header())
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_ticket_defaults_to_open():
    as_user(3)
    ticket = create_ticket()
    assert ticket["status"] == "open"
    assert ticket["creator_id"] == 3
    assert ticket["assignee_id"] is None


def test_create_ticket_rejects_bad_priority():
    as_user(3)
    resp = client.post("/tickets", json={"title": "x", "priority": "p0"},
                       headers=auth_header())
    assert resp.status_code == 400


def test_customer_sees_only_own_tickets():
    as_user(3)
    create_ticket("ticket from customer 3")
    as_user(4)
    create_ticket("ticket from customer 4")

    resp = client.get("/tickets", headers=auth_header())
    titles = [t["title"] for t in resp.json()["tickets"]]
    assert "ticket from customer 4" in titles
    assert "ticket from customer 3" not in titles

    as_user(1)  # admin sees everything
    resp = client.get("/tickets", headers=auth_header())
    titles = [t["title"] for t in resp.json()["tickets"]]
    assert "ticket from customer 3" in titles
    assert "ticket from customer 4" in titles


def test_customer_cannot_view_others_ticket():
    as_user(3)
    ticket = create_ticket()
    as_user(4)
    resp = client.get(f"/tickets/{ticket['id']}", headers=auth_header())
    assert resp.status_code == 403


def test_assign_requires_staff_role():
    as_user(3)
    ticket = create_ticket()
    resp = client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 2},
                       headers=auth_header())
    assert resp.status_code == 403


def test_assign_flow():
    as_user(3)
    ticket = create_ticket()
    as_user(1)  # admin dispatches to agent 2
    resp = client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 2},
                       headers=auth_header())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "assigned"
    assert body["assignee_id"] == 2


def test_assign_to_customer_rejected():
    as_user(3)
    ticket = create_ticket()
    as_user(1)
    resp = client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 4},
                       headers=auth_header())
    assert resp.status_code == 400


def test_assign_to_unknown_user_rejected():
    as_user(3)
    ticket = create_ticket()
    as_user(1)
    resp = client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 999},
                       headers=auth_header())
    assert resp.status_code == 400


def test_close_by_creator_and_double_close_conflict():
    as_user(3)
    ticket = create_ticket()
    resp = client.post(f"/tickets/{ticket['id']}/close", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"

    again = client.post(f"/tickets/{ticket['id']}/close", headers=auth_header())
    assert again.status_code == 409


def test_close_forbidden_for_unrelated_customer():
    as_user(3)
    ticket = create_ticket()
    as_user(4)
    resp = client.post(f"/tickets/{ticket['id']}/close", headers=auth_header())
    assert resp.status_code == 403


def test_assignee_can_close_and_closed_ticket_cannot_be_assigned():
    as_user(3)
    ticket = create_ticket()
    as_user(1)
    client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 2},
                headers=auth_header())
    as_user(2)  # the assignee closes it
    resp = client.post(f"/tickets/{ticket['id']}/close", headers=auth_header())
    assert resp.status_code == 200

    as_user(1)
    resp = client.post(f"/tickets/{ticket['id']}/assign", json={"assignee_id": 2},
                       headers=auth_header())
    assert resp.status_code == 409


def test_status_filter():
    as_user(3)
    open_ticket = create_ticket("still open")
    closed = create_ticket("to be closed")
    client.post(f"/tickets/{closed['id']}/close", headers=auth_header())

    as_user(1)
    resp = client.get("/tickets?status=open", headers=auth_header())
    ids = [t["id"] for t in resp.json()["tickets"]]
    assert open_ticket["id"] in ids
    assert closed["id"] not in ids


def test_trace_id_echoed():
    resp = client.get("/health", headers={"X-Trace-ID": "trace-ticket-1"})
    assert resp.headers["X-Trace-ID"] == "trace-ticket-1"
