from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nour_transfers.app import create_app

NOW = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)
ALLOWED_ORIGIN = "https://branch.nour.example"


def inbox_branch():
    stock = {("src", "X"): 100, ("src", "Y"): 100, ("src", "Z"): 100,
             ("dst", "X"): 1, ("dst", "Y"): 5, ("dst", "Z"): 10}
    items = {"X": {"chronic": True, "reserve": 0},
             "Y": {"chronic": False, "reserve": 0},
             "Z": {"chronic": False, "reserve": 0}}
    sales = {("dst", "X"): 1.0, ("dst", "Y"): 1.0, ("dst", "Z"): 1.0}
    return TestClient(create_app(stock=stock, items=items, sales=sales, now=lambda: NOW))


def request(client, item):
    response = client.post("/v1/transfers", json={
        "itemCode": item, "fromBranch": "src", "toBranch": "dst", "quantity": 1,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_inbox_is_sorted_by_priority_then_request_order():
    client = inbox_branch()
    normal = request(client, "Z")
    urgent_one = request(client, "X")
    high = request(client, "Y")
    urgent_two = request(client, "X")

    items = client.get("/v1/branches/dst/transfers").json()["items"]
    assert [card["id"] for card in items] == [
        urgent_one["id"], urgent_two["id"], high["id"], normal["id"],
    ]
    assert [card["priority"] for card in items] == ["urgent", "urgent", "high", "normal"]


def test_inbox_keeps_approved_transfers_and_ignores_other_branches():
    client = inbox_branch()
    urgent = request(client, "X")
    client.post(f"/v1/transfers/{urgent['id']}/approve")

    items = client.get("/v1/branches/dst/transfers").json()["items"]
    assert [(card["id"], card["status"], card["priority"]) for card in items] == [
        (urgent["id"], "approved", "urgent"),
    ]
    assert client.get("/v1/branches/src/transfers").json()["items"] == []
    assert client.get("/v1/branches/nowhere/transfers").json()["items"] == []


def test_preflight_from_allowed_origin(client):
    for origin in (ALLOWED_ORIGIN, "http://localhost:5173"):
        response = client.options("/v1/transfers", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200, response.text
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "POST" in response.headers["access-control-allow-methods"]
        assert "GET" in response.headers["access-control-allow-methods"]
        assert "content-type" in response.headers["access-control-allow-headers"].lower()
        assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_preflight_from_other_origin_is_refused(client):
    response = client.options("/v1/transfers", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_normal_requests_only_echo_allowed_origins(client):
    allowed = client.get("/v1/branches/tanta/stock/MET500", headers={"Origin": ALLOWED_ORIGIN})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN

    other = client.get("/v1/branches/tanta/stock/MET500", headers={"Origin": "https://evil.example"})
    assert other.status_code == 200
    assert "access-control-allow-origin" not in other.headers
