def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, email="alice@test.com", password="password12"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def test_api_requires_auth(client):
    assert client.get("/api/expenses").status_code == 401


def test_expenses_crud_and_analytics(client):
    token = _register(client)
    h = _headers(token)

    assert client.get("/api/expenses", headers=h).get_json() == []

    r = client.post(
        "/api/expenses",
        headers=h,
        json={
            "date": "2026-05-10",
            "category": "Food",
            "description": "snack",
            "amount": 5.5,
            "payment_method": "cash",
        },
    )
    assert r.status_code == 201

    rows = client.get("/api/expenses", headers=h).get_json()
    assert len(rows) == 1
    assert rows[0]["category"] == "Food"
    eid = rows[0]["id"]

    j = client.get("/api/analytics", headers=h).get_json()
    assert j["total"] == 5.5
    assert j["categories"].get("Food") == 5.5

    assert (
        client.put(
            f"/api/expenses/{eid}",
            headers=h,
            json={
                "date": "2026-05-10",
                "category": "Food",
                "description": "snack",
                "amount": 10.0,
                "payment_method": "cash",
            },
        ).status_code
        == 200
    )

    assert client.get("/api/analytics", headers=h).get_json()["total"] == 10.0

    assert client.delete(f"/api/expenses/{eid}", headers=h).status_code == 200
    assert client.get("/api/expenses", headers=h).get_json() == []


def test_update_expense_404(client):
    token = _register(client)
    h = _headers(token)
    assert (
        client.put(
            "/api/expenses/99999",
            headers=h,
            json={
                "date": "1",
                "category": "x",
                "description": "",
                "amount": 1,
                "payment_method": "",
            },
        ).status_code
        == 404
    )


def test_banks_and_bills_smoke(client):
    token = _register(client)
    h = _headers(token)
    assert client.get("/api/banks", headers=h).status_code == 200
    assert client.get("/api/bills", headers=h).status_code == 200


def test_users_data_isolated(client):
    ta = _register(client, "a@test.com", "password12")
    tb = _register(client, "b@test.com", "password12")
    ha, hb = _headers(ta), _headers(tb)

    client.post(
        "/api/expenses",
        headers=ha,
        json={
            "date": "2026-01-01",
            "category": "Food",
            "description": "a-only",
            "amount": 1,
            "payment_method": "cash",
        },
    )
    assert len(client.get("/api/expenses", headers=ha).get_json()) == 1
    assert client.get("/api/expenses", headers=hb).get_json() == []


def test_duplicate_register(client):
    _register(client, "dup@test.com", "password12")
    r = client.post("/api/auth/register", json={"email": "dup@test.com", "password": "password12"})
    assert r.status_code == 409
