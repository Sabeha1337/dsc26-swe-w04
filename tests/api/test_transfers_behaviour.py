from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nour_transfers.app import create_app

NOW = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)


def make_client(stock, items, sales=None):
    return TestClient(create_app(stock=stock, items=items, sales=sales or {}, now=lambda: NOW))


def post(client, item="MET500", source="heliopolis", dest="tanta", quantity=20):
    return client.post("/v1/transfers", json={
        "itemCode": item, "fromBranch": source, "toBranch": dest, "quantity": quantity,
    })


def units(client, branch, item):
    r = client.get(f"/v1/branches/{branch}/stock/{item}")
    assert r.status_code == 200
    return r.json()["units"]


def test_request_returns_a_pending_card_and_moves_nothing(client):
    before = units(client, "heliopolis", "MET500")
    r = post(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["itemCode"] == "MET500"
    assert body["fromBranch"] == "heliopolis"
    assert body["toBranch"] == "tanta"
    assert body["quantity"] == 20
    assert units(client, "heliopolis", "MET500") == before
    assert units(client, "tanta", "MET500") == 2


def test_exact_reserve_is_allowed_one_past_it_is_not():
    client = make_client({("src", "X"): 10, ("dst", "X"): 0},
                         {"X": {"chronic": False, "reserve": 5}})
    assert post(client, item="X", source="src", dest="dst", quantity=5).status_code == 201
    refused = post(client, item="X", source="src", dest="dst", quantity=6)
    assert refused.status_code == 409
    assert refused.json()["type"] == "/problems/below-reserve"
    assert refused.headers["content-type"].startswith("application/problem+json")
    assert units(client, "src", "X") == 10


def test_approve_moves_stock_once_and_twice_is_not_pending(client):
    transfer = post(client).json()
    assert units(client, "heliopolis", "MET500") == 40
    assert units(client, "tanta", "MET500") == 2

    approved = client.post(f"/v1/transfers/{transfer['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert units(client, "heliopolis", "MET500") == 20
    assert units(client, "tanta", "MET500") == 22

    again = client.post(f"/v1/transfers/{transfer['id']}/approve")
    assert again.status_code == 409
    assert again.json()["type"] == "/problems/not-pending"
    assert units(client, "heliopolis", "MET500") == 20
    assert units(client, "tanta", "MET500") == 22


def test_approve_refused_when_stock_fell_since_the_request():
    client = make_client({("src", "X"): 40, ("dst", "X"): 0},
                         {"X": {"chronic": False, "reserve": 10}})
    first = post(client, item="X", source="src", dest="dst", quantity=20).json()
    second = post(client, item="X", source="src", dest="dst", quantity=20).json()
    assert client.post(f"/v1/transfers/{first['id']}/approve").status_code == 200
    refused = client.post(f"/v1/transfers/{second['id']}/approve")
    assert refused.status_code == 409
    assert refused.json()["type"] == "/problems/below-reserve"
    assert units(client, "src", "X") == 20
    assert units(client, "dst", "X") == 20


def test_unknown_transfer_is_a_problem_404(client):
    r = client.post("/v1/transfers/tr_999/approve")
    assert r.status_code == 404
    assert r.json()["type"] == "/problems/unknown-transfer"
    assert r.json()["status"] == 404
    assert r.headers["content-type"].startswith("application/problem+json")


def test_same_branch_is_rejected(client):
    r = post(client, source="tanta", dest="tanta")
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/same-branch"
    assert r.headers["content-type"].startswith("application/problem+json")
    assert units(client, "tanta", "MET500") == 2


def test_unknown_item_and_branch_are_distinct_404s(client):
    item = post(client, item="NOPE")
    assert item.status_code == 404
    assert item.json()["type"] == "/problems/unknown-item"

    source = post(client, source="nowhere")
    assert source.status_code == 404
    assert source.json()["type"] == "/problems/unknown-branch"

    dest = post(client, dest="nowhere")
    assert dest.status_code == 404
    assert dest.json()["type"] == "/problems/unknown-branch"

    both = post(client, item="NOPE", source="nowhere")
    assert both.json()["type"] == "/problems/unknown-item"


def test_validation_errors_are_problem_documents(client):
    missing = client.post("/v1/transfers", json={
        "itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta",
    })
    assert missing.status_code == 422
    assert missing.json()["type"] == "/problems/validation"
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert any("quantity" in error["loc"] for error in missing.json()["errors"])

    zero = post(client, quantity=0)
    assert zero.status_code == 422
    assert zero.json()["type"] == "/problems/validation"


def test_extra_body_fields_are_ignored(client):
    r = client.post("/v1/transfers", json={
        "itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta",
        "quantity": 1, "note": "please hurry",
    })
    assert r.status_code == 201


def test_stock_lookup_known_and_unknown(client):
    assert units(client, "heliopolis", "MET500") == 40
    assert units(client, "tanta", "AMOX250") == 25
    assert units(client, "heliopolis", "NOPE") == 0
    assert units(client, "nowhere", "MET500") == 0


def test_each_app_starts_empty_and_copies_its_input():
    stock = {("src", "X"): 10, ("dst", "X"): 0}
    items = {"X": {"chronic": False, "reserve": 0}}
    first = TestClient(create_app(stock=stock, items=items, sales={}, now=lambda: NOW))
    second = TestClient(create_app(stock=stock, items=items, sales={}, now=lambda: NOW))

    assert post(first, item="X", source="src", dest="dst", quantity=1).json()["id"] == "tr_1"
    assert post(second, item="X", source="src", dest="dst", quantity=1).json()["id"] == "tr_1"
    assert second.get("/v1/branches/dst/transfers").json()["items"][0]["id"] == "tr_1"

    stock[("src", "X")] = 999
    assert units(first, "src", "X") == 10
