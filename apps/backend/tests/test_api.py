import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src import create_app
from src.services.face_service import FaceService
from src.storage import KST, Store

AUTH = ("manager", "test-only-password")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", AUTH[0])
    monkeypatch.setenv("ADMIN_PASSWORD", AUTH[1])
    monkeypatch.setenv("SERVE_WEB", "true")
    with TestClient(create_app(tmp_path / "test.db")) as test_client:
        yield test_client


def payload(**changes):
    return {"request_id": str(uuid4()), "order_mode": "takeout", "payment_method": "card",
            "items": [{"menu_id": "ame_hot", "qty": 2}], **changes}


def test_app_and_admin_auth(client):
    assert client.get("/health").json() == {"ok": True}
    for url in ("/", "/kiosk", "/admin", "/kiosk-static/app.js", "/admin-static/app.js", "/static/images/ame_hot.png", "/docs"):
        assert client.get(url).status_code == 200
    assert len(client.get("/api/menus").json()["menus"]) == 14
    for url in ("/api/admin/me", "/api/admin/orders", "/api/admin/orders/1", "/api/admin/sales"):
        assert client.get(url).status_code == 401
        assert client.get(url, auth=("manager", "wrong")).status_code == 401
    assert client.get("/api/admin/me", auth=AUTH).json() == {"username": "manager"}
    assert client.patch("/api/admin/orders/1", json={"status": "cancelled"}).status_code == 401


def test_admin_disabled_without_password(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    with TestClient(create_app(tmp_path / "no-auth.db")) as client:
        assert client.get("/api/admin/orders", auth=AUTH).status_code == 503


def test_backend_can_run_without_frontend(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVE_WEB", "false")
    with TestClient(create_app(tmp_path / "api-only.db")) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/menus").status_code == 200
        assert client.get("/kiosk").status_code == 404
        assert client.get("/admin-static/app.js").status_code == 404


def test_order_lifecycle_sales_and_price_snapshot(client):
    data = payload()
    response = client.post("/api/orders", json=data)
    assert response.status_code == 200
    order = response.json()["order"]
    assert order["total"] == 3000
    assert order["status"] == "pending" and order["payment_status"] == "unpaid"
    assert "request_id" not in order
    assert client.get("/api/admin/sales", auth=AUTH).json()["revenue"] == 0
    url = f"/api/admin/orders/{order['id']}"
    assert client.patch(url, auth=AUTH, json={"status": "completed"}).status_code == 409
    assert client.patch(url, auth=AUTH, json={"status": "preparing"}).status_code == 200
    assert client.patch(url, auth=AUTH, json={"status": "completed"}).status_code == 409
    assert client.patch(url, auth=AUTH, json={"payment_status": "paid"}).status_code == 200
    assert client.patch(url, auth=AUTH, json={"status": "cancelled"}).status_code == 409
    assert client.patch(url, auth=AUTH, json={"status": "completed"}).status_code == 200
    assert client.patch(url, auth=AUTH, json={"status": "pending"}).status_code == 409
    with client.app.state.store.connect() as db:
        db.execute("UPDATE menus SET price=9999,name='changed' WHERE menu_id='ame_hot'")
    detail = client.get(url, auth=AUTH).json()
    assert detail["items"][0]["price"] == 1500
    assert detail["items"][0]["name"] != "changed"
    summary = client.get("/api/admin/sales", auth=AUTH).json()
    assert summary["revenue"] == 3000 and summary["paid_count"] == 1
    assert summary["top_menus"][0]["quantity"] == 2
    assert summary["daily"][0]["date"] == datetime.now(KST).date().isoformat()
    assert client.get("/api/admin/orders", auth=AUTH).json()["orders"][0] == detail


def test_idempotency_and_conflict(client):
    data = payload()
    first = client.post("/api/orders", json=data).json()
    assert client.post("/api/orders", json=data).json() == first
    data["items"][0]["qty"] = 3
    assert client.post("/api/orders", json=data).status_code == 409
    assert client.get("/api/admin/orders", auth=AUTH).json()["total"] == 1


def test_concurrent_duplicate_requests(client):
    data = payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post("/api/orders", json=data), range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["order"]["id"] for response in responses}) == 1
    assert client.get("/api/admin/orders", auth=AUTH).json()["total"] == 1


@pytest.mark.parametrize("changes", [
    {"items": []}, {"items": [{"menu_id": "ame_hot", "qty": 0}]},
    {"items": [{"menu_id": "ame_hot", "qty": -1}]},
    {"items": [{"menu_id": "ame_hot", "qty": 100}]},
    {"items": [{"menu_id": "ame_hot", "qty": True}]},
    {"items": [{"menu_id": "ame_hot", "qty": 1.5}]},
    {"items": [{"menu_id": "ame_hot", "qty": 1, "price": 1}]},
    {"items": [{"menu_id": "ame_hot", "qty": 1}, {"menu_id": "ame_hot", "qty": 2}]},
    {"items": [{"menu_id": "ame_hot", "qty": 1}, {"menu_id": "missing", "qty": 1}]},
    {"age_group": "unknown"}, {"request_id": "invalid"}, {"order_mode": "other"}, {"total": 1},
])
def test_invalid_order_is_atomic(client, changes):
    assert client.post("/api/orders", json=payload(**changes)).status_code == 422
    assert client.get("/api/admin/orders", auth=AUTH).json()["total"] == 0


def test_cancel_filters_dates_and_pagination(client):
    ids = [client.post("/api/orders", json=payload()).json()["order"]["id"] for _ in range(3)]
    url = f"/api/admin/orders/{ids[0]}"
    assert client.patch(url, auth=AUTH, json={"status": "cancelled"}).status_code == 200
    assert client.patch(url, auth=AUTH, json={"payment_status": "paid"}).status_code == 409
    assert client.get("/api/admin/orders?status=cancelled", auth=AUTH).json()["total"] == 1
    page = client.get("/api/admin/orders?page=2&page_size=2", auth=AUTH).json()
    assert len(page["orders"]) == 1 and page["total"] == 3
    assert client.get("/api/admin/sales", auth=AUTH).json()["cancelled_count"] == 1
    assert client.get("/api/admin/orders?start=2020-01-01&end=2020-01-02", auth=AUTH).json()["total"] == 0
    for query in ("start=2025-01-02&end=2025-01-01", "start=2020-01-01&end=2025-01-01", "page=0", "status=bad"):
        assert client.get(f"/api/admin/orders?{query}", auth=AUTH).status_code == 422
    assert client.get("/api/admin/orders/999", auth=AUTH).status_code == 404


def test_face_optional_and_validated(client, monkeypatch):
    assert client.post("/api/recommend", files={"file": ("test.txt", b"test", "text/plain")}).status_code == 415
    assert client.post("/api/recommend", files={"file": ("test.png", b"", "image/png")}).status_code == 413
    def missing(_self, _data):
        raise ImportError("not installed")
    monkeypatch.setattr(FaceService, "detect_age", missing)
    assert client.post("/api/recommend", files={"file": ("face.png", b"test", "image/png")}).status_code == 503
    monkeypatch.setattr(FaceService, "detect_age", lambda _self, _data: 55)
    result = client.post("/api/recommend", files={"file": ("face.png", b"test", "image/png")}).json()
    assert result["age_group"] == "41_50" and len(result["menus"]) == 14


def test_existing_database_is_preserved(tmp_path):
    original = tmp_path / "original.db"
    with sqlite3.connect(original) as db:
        db.executescript("CREATE TABLE menus(menu_id TEXT PRIMARY KEY,menu_index INTEGER,name TEXT,price INTEGER,image_path TEXT);"
                         "INSERT INTO menus VALUES('custom',1,'Custom',4100,'images/custom.png');"
                         "CREATE TABLE age_menu_stats(age_group TEXT PRIMARY KEY,menu_1 INTEGER);"
                         "INSERT INTO age_menu_stats VALUES('10_40',7);")
    before = original.read_bytes()
    store = Store(tmp_path / "live.db")
    store.initialize(original)
    store.initialize(original)
    assert store.menus()[0]["price"] == 4100
    assert store.recommended_menus("10_40")[0]["menu_id"] == "custom"
    assert original.read_bytes() == before
