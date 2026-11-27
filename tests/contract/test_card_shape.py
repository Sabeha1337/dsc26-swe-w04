import json
import pathlib
from datetime import datetime

from jsonschema import Draft202012Validator

SCHEMA = json.loads(
    (pathlib.Path(__file__).parents[2] / "contracts/transfer_card.schema.json").read_text()
)
CARD_KEYS = {"id", "itemCode", "fromBranch", "toBranch", "quantity", "priority",
             "status", "requestedAt"}


def check_card(card):
    Draft202012Validator(SCHEMA).validate(card)
    assert set(card) == CARD_KEYS


def test_every_transfer_card_matches_the_contract(client):
    created = client.post("/v1/transfers", json={
        "itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta", "quantity": 20,
    })
    assert created.status_code == 201
    card = created.json()
    check_card(card)
    assert card["id"].startswith("tr_")

    approved = client.post(f"/v1/transfers/{card['id']}/approve")
    assert approved.status_code == 200
    check_card(approved.json())
    assert approved.json()["status"] == "approved"

    for item in client.get("/v1/branches/tanta/transfers").json()["items"]:
        check_card(item)


def test_requested_at_is_utc_with_z(client):
    card = client.post("/v1/transfers", json={
        "itemCode": "AMOX250", "fromBranch": "heliopolis", "toBranch": "tanta", "quantity": 1,
    }).json()
    assert card["requestedAt"].endswith("Z")
    parsed = datetime.fromisoformat(card["requestedAt"].replace("Z", "+00:00"))
    assert parsed.utcoffset().total_seconds() == 0


def test_ids_follow_request_order(client):
    payload = {"itemCode": "AMOX250", "fromBranch": "heliopolis", "toBranch": "tanta",
               "quantity": 1}
    first = client.post("/v1/transfers", json=payload).json()
    second = client.post("/v1/transfers", json=payload).json()
    assert (first["id"], second["id"]) == ("tr_1", "tr_2")
