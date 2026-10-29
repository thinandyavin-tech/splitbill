import threading
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import repository as repo
from app import service
from app.db import SessionLocal, engine
from app.main import app
from app.schemas import ExpenseCreate


def post_expense(client, user, body, group_id=1, key=None):
    headers = {"X-User": user}
    if key:
        headers["Idempotency-Key"] = key
    return client.post(f"/groups/{group_id}/expenses", json=body, headers=headers)


def equal(amount, members, paid_by="alice", description="Dinner"):
    return {
        "description": description,
        "paid_by": paid_by,
        "amount": amount,
        "split": {"type": "equal", "members": members},
    }


def balances(client, user="alice", group_id=1):
    res = client.get(f"/groups/{group_id}/balances", headers={"X-User": user})
    assert res.status_code == 200
    return {b["user"]: b["balance"] for b in res.json()["balances"]}


def expense_count():
    with engine.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM expenses"))


# --- Required: equal split and zero-sum balances ---


def test_equal_split_100_three_ways_and_balances_sum_to_zero(client):
    res = post_expense(client, "alice", equal("100.00", ["alice", "bob", "carol"]))
    assert res.status_code == 201
    assert [(s["user"], s["amount"]) for s in res.json()["shares"]] == [
        ("alice", "33.34"),
        ("bob", "33.33"),
        ("carol", "33.33"),
    ]
    result = balances(client)
    assert result == {"alice": "66.66", "bob": "-33.33", "carol": "-33.33"}
    assert sum(Decimal(v) for v in result.values()) == Decimal("0.00")


def test_brief_example_dinner(client):
    res = post_expense(client, "alice", equal("1000.00", ["alice", "bob", "carol"]))
    assert [s["amount"] for s in res.json()["shares"]] == ["333.34", "333.33", "333.33"]
    assert balances(client) == {"alice": "666.66", "bob": "-333.33", "carol": "-333.33"}


def test_balances_stay_zero_sum_across_many_expenses(client):
    post_expense(client, "alice", equal("0.01", ["bob", "carol", "alice"]))
    post_expense(client, "bob", equal("999.99", ["carol", "alice"], paid_by="bob"))
    post_expense(client, "carol", equal("7.00", ["alice", "bob", "carol"], paid_by="carol"))
    assert sum(Decimal(v) for v in balances(client).values()) == Decimal("0.00")


# --- Required: exact split must add up ---


def test_exact_split_not_summing_to_amount_is_rejected(client):
    body = {
        "description": "Hotel",
        "paid_by": "alice",
        "amount": "1000.00",
        "split": {
            "type": "exact",
            "shares": {"alice": "500.00", "bob": "300.00", "carol": "100.00"},
        },
    }
    res = post_expense(client, "alice", body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "shares_mismatch"
    assert "900.00" in res.json()["error"]["message"]
    assert expense_count() == 0


def test_exact_split_accepted(client):
    body = {
        "description": "Hotel",
        "paid_by": "alice",
        "amount": "1000.00",
        "split": {
            "type": "exact",
            "shares": {"alice": "500.00", "bob": "300.00", "carol": "200.00"},
        },
    }
    res = post_expense(client, "alice", body)
    assert res.status_code == 201
    assert balances(client) == {"alice": "500.00", "bob": "-300.00", "carol": "-200.00"}


# --- Required: monetary precision ---


def test_amount_with_three_decimal_places_is_rejected(client):
    res = post_expense(client, "alice", equal("10.005", ["alice", "bob"]))
    assert res.status_code == 422
    assert "2 decimal places" in res.json()["error"]["message"]
    assert expense_count() == 0


@pytest.mark.parametrize(
    ("amount", "code"),
    [("0.00", "validation_error"), ("-10.00", "validation_error"), (10.5, "invalid_request")],
)
def test_zero_negative_or_numeric_amount_is_rejected(client, amount, code):
    res = post_expense(client, "alice", equal(amount, ["alice", "bob"]))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == code
    assert expense_count() == 0


def test_exact_share_with_three_decimal_places_is_rejected(client):
    body = {
        "description": "Hotel",
        "paid_by": "alice",
        "amount": "10.00",
        "split": {"type": "exact", "shares": {"alice": "5.005", "bob": "4.995"}},
    }
    res = post_expense(client, "alice", body)
    assert res.status_code == 422
    assert "2 decimal places" in res.json()["error"]["message"]
    assert expense_count() == 0


# --- Consistent JSON errors ---


def test_out_of_range_id_is_a_json_error_not_a_crash(client):
    res = client.get("/groups/99999999999", headers={"X-User": "alice"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_unexpected_server_error_is_json(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(service, "balances", boom)
    res = TestClient(app, raise_server_exceptions=False).get(
        "/groups/1/balances", headers={"X-User": "alice"}
    )
    assert res.status_code == 500
    assert res.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong on the server"}
    }


# --- Required: idempotency ---


def test_repeated_idempotency_key_creates_one_expense(client):
    body = equal("1000.00", ["alice", "bob", "carol"])
    first = post_expense(client, "alice", body, key="7f3c2a10-dinner-0001")
    second = post_expense(client, "alice", body, key="7f3c2a10-dinner-0001")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert expense_count() == 1


def test_same_idempotency_key_in_another_group_is_independent(client):
    post_expense(client, "bob", equal("10.00", ["bob", "carol"], paid_by="bob"), 1, key="k")
    res = post_expense(client, "bob", equal("10.00", ["bob", "dan"], paid_by="bob"), 2, key="k")
    assert res.status_code == 201
    assert expense_count() == 2


def test_concurrent_requests_with_same_key_create_one_expense():
    """Force the race: request A has inserted the key but not committed when request B
    arrives. B's lookup can't see A's row yet, so B reaches the INSERT, which must wait
    for A and then hand back A's expense instead of creating a second one."""
    data = ExpenseCreate(**equal("300.00", ["alice", "bob", "carol"]))
    with SessionLocal() as session_a, SessionLocal() as session_b:
        alice = repo.get_user(session_a, "alice")
        group = repo.get_group(session_a, 1)
        winner_id = repo.insert_expense(
            session_a,
            group_id=1,
            description=data.description,
            paid_by_id=alice.id,
            created_by_id=alice.id,
            amount=Decimal("300.00"),
            split_type="equal",
            idempotency_key="race-1",
            shares=[(m.id, Decimal("100.00")) for m in group.members],
        )

        result = {}
        b_user = repo.get_user(session_b, "alice")
        b_group = repo.get_group(session_b, 1)
        thread = threading.Thread(
            target=lambda: result.update(
                out=service.create_expense(session_b, b_group, b_user, data, "race-1")
            )
        )
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "request B should be blocked on A's uncommitted key"

        session_a.commit()
        thread.join(timeout=10)

    expense, created = result["out"]
    assert created is False
    assert expense.id == winner_id
    assert expense_count() == 1


# --- Required: group access ---


def test_alice_cannot_read_group_2(client):
    headers = {"X-User": "alice"}
    for path in ["/groups/2", "/groups/2/expenses", "/groups/2/balances"]:
        res = client.get(path, headers=headers)
        assert res.status_code == 404, path
        assert res.json()["error"]["code"] == "group_not_found"
    groups = client.get("/groups", headers=headers).json()
    assert [g["id"] for g in groups] == [1]


def test_alice_cannot_write_group_2(client):
    res = post_expense(client, "alice", equal("10.00", ["bob", "dan"], paid_by="bob"), group_id=2)
    assert res.status_code == 404
    bob_expense = post_expense(client, "bob", equal("10.00", ["bob", "dan"], paid_by="bob"), 2)
    res = client.delete(
        f"/groups/2/expenses/{bob_expense.json()['id']}", headers={"X-User": "alice"}
    )
    assert res.status_code == 404
    assert expense_count() == 1


def test_non_member_in_split_is_rejected(client):
    res = post_expense(client, "alice", equal("10.00", ["alice", "dan"]))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_group_member"
    res = post_expense(client, "alice", equal("10.00", ["alice"], paid_by="dan"))
    assert res.json()["error"]["code"] == "not_group_member"


@pytest.mark.parametrize("headers", [{}, {"X-User": "mallory"}])
def test_missing_or_unknown_user_is_unauthenticated(client, headers):
    res = client.get("/groups", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


# --- Required: only the payer can delete; deletion is soft ---


def test_only_payer_can_delete_expense(client):
    expense = post_expense(client, "alice", equal("90.00", ["alice", "bob", "carol"])).json()
    url = f"/groups/1/expenses/{expense['id']}"

    res = client.delete(url, headers={"X-User": "bob"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "not_payer"

    assert client.delete(url, headers={"X-User": "alice"}).status_code == 204
    assert client.get("/groups/1/expenses", headers={"X-User": "alice"}).json() == []
    assert balances(client) == {"alice": "0.00", "bob": "0.00", "carol": "0.00"}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT deleted_at IS NOT NULL FROM expenses")) is True

    assert client.delete(url, headers={"X-User": "alice"}).status_code == 404


def test_expenses_listed_newest_first(client):
    for name in ["first", "second", "third"]:
        post_expense(client, "alice", equal("1.00", ["alice"], description=name))
    res = client.get("/groups/1/expenses", headers={"X-User": "bob"})
    assert [e["description"] for e in res.json()] == ["third", "second", "first"]
