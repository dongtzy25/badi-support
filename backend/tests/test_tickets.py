from tests.conftest import AGENT, CUSTOMER, OTHER_CUSTOMER, TICKET


# ---------- The two tests the brief asks for ----------

def test_creating_a_ticket_generates_a_number_and_starts_open(client, agents):
    first = client.post("/tickets", json=TICKET, headers=CUSTOMER)
    second = client.post("/tickets", json=TICKET, headers=AGENT)

    assert first.status_code == 201
    assert first.json()["number"] == "BD-1001"
    assert first.json()["status"] == "OPEN"
    assert first.json()["assignee"] is None
    assert second.json()["number"] == "BD-1002"  # numbers are unique and sequential


def test_changing_status_creates_an_audit_entry(client, ticket):
    response = client.patch(f"/tickets/{ticket['id']}", json={"status": "IN_PROGRESS"}, headers=AGENT)
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"

    events = client.get(f"/tickets/{ticket['id']}", headers=AGENT).json()["events"]
    status_events = [e for e in events if e["type"] == "STATUS_CHANGED"]
    assert len(status_events) == 1
    assert status_events[0]["old_value"] == "OPEN"
    assert status_events[0]["new_value"] == "IN_PROGRESS"
    assert status_events[0]["actor_agent"]["name"] == "Anas"


# ---------- Audit trail ----------

def test_assignment_and_priority_changes_are_audited_and_no_ops_are_not(client, ticket):
    url = f"/tickets/{ticket['id']}"
    client.patch(url, json={"assignee_id": 2, "priority": "URGENT"}, headers=AGENT)
    client.patch(url, json={"assignee_id": 2, "priority": "URGENT"}, headers=AGENT)  # same values again
    client.patch(url, json={"assignee_id": None}, headers=AGENT)  # unassign

    events = client.get(url, headers=AGENT).json()["events"]
    summary = [(e["type"], e["old_value"], e["new_value"]) for e in events]
    assert summary == [
        ("CREATED", None, "OPEN"),
        ("PRIORITY_CHANGED", "HIGH", "URGENT"),
        ("ASSIGNEE_CHANGED", None, "Maria"),
        ("ASSIGNEE_CHANGED", "Maria", None),
    ]


# ---------- Visibility and permissions ----------

def test_customers_never_see_internal_notes_or_audit_history(client, ticket):
    url = f"/tickets/{ticket['id']}"
    client.post(f"{url}/messages", json={"body": "Are you in Turkey?"}, headers=AGENT)
    client.post(f"{url}/messages", json={"body": "Escalated to provider", "type": "INTERNAL"}, headers=AGENT)

    agent_view = client.get(url, headers=AGENT).json()
    customer_view = client.get(url, headers=CUSTOMER).json()

    assert [m["type"] for m in agent_view["messages"]] == ["PUBLIC", "INTERNAL"]
    assert [m["body"] for m in customer_view["messages"]] == ["Are you in Turkey?"]
    assert customer_view["events"] == []


def test_customers_only_see_their_own_tickets(client, ticket):
    assert client.get(f"/tickets/{ticket['id']}", headers=OTHER_CUSTOMER).status_code == 404
    assert client.get("/tickets", headers=OTHER_CUSTOMER).json()["total"] == 0
    assert client.get("/tickets", headers=CUSTOMER).json()["total"] == 1


def test_customers_cannot_manage_tickets_or_add_internal_notes(client, ticket):
    url = f"/tickets/{ticket['id']}"
    assert client.patch(url, json={"status": "CLOSED"}, headers=CUSTOMER).status_code == 403
    response = client.post(f"{url}/messages", json={"body": "hi", "type": "INTERNAL"}, headers=CUSTOMER)
    assert response.status_code == 403


# ---------- Workflow rules ----------

def test_customer_reply_moves_waiting_ticket_back_to_in_progress(client, ticket):
    url = f"/tickets/{ticket['id']}"
    client.patch(url, json={"status": "WAITING_FOR_CUSTOMER"}, headers=AGENT)

    client.post(f"{url}/messages", json={"body": "Yes, I am in Turkey."}, headers=CUSTOMER)

    detail = client.get(url, headers=AGENT).json()
    assert detail["status"] == "IN_PROGRESS"
    last = detail["events"][-1]
    assert (last["type"], last["old_value"], last["new_value"]) == ("STATUS_CHANGED", "WAITING_FOR_CUSTOMER", "IN_PROGRESS")
    assert last["actor_agent"] is None  # changed by the system, not an agent


def test_closed_tickets_reject_new_messages(client, ticket):
    url = f"/tickets/{ticket['id']}"
    client.patch(url, json={"status": "CLOSED"}, headers=AGENT)
    response = client.post(f"{url}/messages", json={"body": "One more thing"}, headers=CUSTOMER)
    assert response.status_code == 409
    assert "closed" in response.json()["detail"]


# ---------- Filters ----------

def test_list_filters_and_search(client, agents):
    client.post("/tickets", json=TICKET, headers=AGENT)
    client.post("/tickets", json={**TICKET, "category": "REFUND", "subject": "Refund please", "priority": "LOW"}, headers=AGENT)
    client.patch("/tickets/2", json={"assignee_id": 1}, headers=AGENT)

    def numbers(query: str) -> list[str]:
        return [t["number"] for t in client.get(f"/tickets?{query}", headers=AGENT).json()["items"]]

    assert numbers("category=REFUND") == ["BD-1002"]
    assert numbers("priority=HIGH") == ["BD-1001"]
    assert numbers("assignee_id=1") == ["BD-1002"]
    assert numbers("unassigned=true") == ["BD-1001"]
    assert numbers("q=refund") == ["BD-1002"]
    assert numbers("q=BD-1001") == ["BD-1001"]


# ---------- Validation and errors ----------

def test_invalid_ticket_returns_readable_field_errors(client, agents):
    bad = {"customer_email": "not-an-email", "category": "WIFI", "subject": " ", "description": "short", "priorty": "HIGH"}
    response = client.post("/tickets", json=bad, headers=AGENT)

    assert response.status_code == 422
    errors = {e["field"]: e["message"] for e in response.json()["errors"]}
    assert set(errors) == {"customer_email", "category", "subject", "description", "priorty"}
    assert errors["customer_email"] == "Enter a valid email address"
    assert errors["description"] == "Must be at least 10 characters"
    assert errors["priorty"] == "Unknown field 'priorty'"


def test_unknown_ticket_agent_and_missing_identity(client, ticket):
    assert client.get("/tickets/999", headers=AGENT).status_code == 404
    response = client.patch(f"/tickets/{ticket['id']}", json={"assignee_id": 99}, headers=AGENT)
    assert response.status_code == 422
    assert client.get("/tickets").status_code == 401


# ---------- Real time ----------

def test_realtime_signals_respect_internal_notes(client, ticket):
    url = f"/tickets/{ticket['id']}"
    ws_url = f"/ws/tickets/{ticket['id']}"
    with client.websocket_connect(f"{ws_url}?role=agent&agent_id=1") as agent_ws, \
         client.websocket_connect(f"{ws_url}?role=customer&email=customer@example.com") as customer_ws:
        client.post(f"{url}/messages", json={"body": "Checking", "type": "INTERNAL"}, headers=AGENT)
        client.post(f"{url}/messages", json={"body": "Any news?"}, headers=CUSTOMER)

        # The agent hears about both messages; the customer only about the public one.
        assert agent_ws.receive_json() == {"type": "message.created", "ticket_id": ticket["id"]}
        assert agent_ws.receive_json() == {"type": "message.created", "ticket_id": ticket["id"]}
        assert customer_ws.receive_json() == {"type": "message.created", "ticket_id": ticket["id"]}

        client.patch(url, json={"status": "RESOLVED"}, headers=AGENT)
        assert customer_ws.receive_json()["type"] == "ticket.updated"
