from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src import create_app
from src import kiosk
from src.schemas import OrderInput
from src.services.face_service import FaceService
from src.storage import Store, StoreError

AUTH = ('owner', 'test-owner-password-123')


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('OWNER_AUTH_MODE', 'database')
    monkeypatch.setenv('STORE_ID', 'primary')
    monkeypatch.setenv('KIOSK_AUTH_REQUIRED', 'true')
    with TestClient(create_app(tmp_path / 'kiosk.db')) as client:
        client.app.state.store.provision_owner(*AUTH)
        yield client


def device(client):
    response = client.post('/api/owner/kiosks/pairing-codes', auth=AUTH, json={'name': '입구'})
    assert response.status_code == 200
    response = client.post('/api/kiosk/register', json={'code': response.json()['code']})
    assert response.status_code == 200
    return response.json()


def session(client, registered=None):
    registered = registered or device(client)
    response = client.post('/api/kiosk/sessions', headers={'X-Kiosk-Device': registered['device_token']})
    assert response.status_code == 200
    return {'X-Kiosk-Session': response.json()['session_token']}


def payload():
    return dict(request_id=str(uuid4()), order_mode='takeout', payment_method='counter',
                items=[{'menu_id': 'ame_hot', 'qty': 2}])


def quote(client, headers, data=None):
    data = data or payload()
    response = client.post('/api/order-quotes', headers=headers, json=data)
    assert response.status_code == 200
    return {**data, 'quote_id': response.json()['quote_id']}


def test_pairing_single_use_hashes_and_owner_scope(client):
    url = '/api/owner/kiosks/pairing-codes'
    assert client.post(url, json={'name': '입구'}).status_code == 401
    assert client.post(url, auth=AUTH, json={'name': '  '}).status_code == 422
    code = client.post(url, auth=AUTH, json={'name': ' 입구 '}).json()['code']
    registered = client.post('/api/kiosk/register', json={'code': code}).json()
    assert client.post('/api/kiosk/register', json={'code': code}).status_code == 401
    headers = session(client, registered)
    with client.app.state.store.connect() as db:
        dump = '\n'.join(db.iterdump())
        assert code not in dump and registered['device_token'] not in dump
        assert headers['X-Kiosk-Session'] not in dump
    listed = client.get('/api/owner/kiosks', auth=AUTH).json()['devices']
    assert listed[0]['name'] == '입구' and 'token_hash' not in str(listed)
    client.app.state.store.change_membership(AUTH[0], False, '회수', 'operator')
    assert client.post(url, auth=AUTH, json={'name': '추가'}).status_code == 403
    assert client.get('/api/owner/kiosks', auth=AUTH).status_code == 403
    assert client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH).status_code == 403


def test_expired_and_concurrent_pairing(client, monkeypatch):
    clock = datetime(2026, 10, 22, tzinfo=timezone.utc)
    monkeypatch.setattr(kiosk, 'now', lambda: clock)
    code = client.app.state.store.pairing('입구')['code']
    clock += timedelta(minutes=10)
    assert client.post('/api/kiosk/register', json={'code': code}).status_code == 401
    code = client.app.state.store.pairing('입구')['code']
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: client.post('/api/kiosk/register', json={'code': code}).status_code, range(2)))
    assert sorted(statuses) == [200, 401]


@pytest.mark.parametrize('path', ['/api/orders', '/api/order-quotes', '/api/orders/confirm'])
def test_order_requires_session(client, path):
    data = payload()
    data['quote_id'] = str(uuid4()) if path.endswith('confirm') else None
    assert client.post(path, json=data).status_code == 401
    assert client.post(path, json=data, headers={'X-Kiosk-Session': 'invalid'}).status_code == 401


def test_own_order_quote_isolation_and_retry(client):
    first, other = session(client), session(client)
    data = quote(client, first)
    assert client.post('/api/orders/confirm', headers=other, json=data).status_code == 409
    response = client.post('/api/orders/confirm', headers=first, json=data)
    assert response.status_code == 200
    order = response.json()['order']
    assert client.post('/api/orders/confirm', headers=first, json=data).json() == response.json()
    assert client.post('/api/orders/confirm', headers=other, json=data).status_code == 409
    assert client.get(f"/api/kiosk/orders/{order['id']}", headers=first).json() == order
    assert client.get(f"/api/kiosk/orders/{order['id']}", headers=other).status_code == 404
    assert client.get('/api/owner/orders', headers=first).status_code == 401
    assert client.post('/api/orders/confirm', headers=first, json=quote(client, first)).status_code == 409


@pytest.mark.parametrize('path', ['/api/order-quotes', '/api/orders'])
def test_session_cannot_use_legacy_payment_or_skip_quote(client, path):
    headers = session(client)
    data = payload()
    data['payment_method'] = 'card'
    assert client.post(path, headers=headers, json=data).status_code == 422
    assert client.post('/api/orders', headers=headers, json=payload()).status_code == 422


def test_concurrent_confirmation_changes_stock_once(client):
    headers = session(client)
    with client.app.state.store.connect() as db:
        db.execute("UPDATE menus SET stock=10 WHERE menu_id='ame_hot'")
    data = quote(client, headers)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post('/api/orders/confirm', headers=headers, json=data), range(4)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()['order']['id'] for r in responses}) == 1
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT stock FROM menus WHERE menu_id='ame_hot'").fetchone()[0] == 8
        assert db.execute('SELECT count(*) FROM stock_movements').fetchone()[0] == 1


def test_link_failure_rolls_back_order_and_stock(client):
    headers = session(client)
    with client.app.state.store.connect() as db:
        db.execute("UPDATE menus SET stock=10 WHERE menu_id='ame_hot'")
        db.execute("CREATE TRIGGER fail_link BEFORE INSERT ON kiosk_order_links BEGIN SELECT RAISE(ABORT,'test'); END")
    data = quote(client, headers)
    with pytest.raises(sqlite3.IntegrityError):
        client.post('/api/orders/confirm', headers=headers, json=data)
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT count(*) FROM orders').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM stock_movements').fetchone()[0] == 0
        assert db.execute("SELECT stock FROM menus WHERE menu_id='ame_hot'").fetchone()[0] == 10


def test_new_customer_and_explicit_end_clear_preferences(client):
    registered = device(client)
    first, other = session(client, registered), session(client)
    assert client.patch('/api/kiosk/session/preferences', headers=first,
                        json={'face': True, 'recommendation': True}).json() == {'face': True, 'voice': False, 'recommendation': True}
    assert client.patch('/api/kiosk/session/preferences', headers=first, json={'voice': 'true'}).status_code == 422
    assert client.patch('/api/kiosk/session/preferences', headers=first, json={'ended': False}).status_code == 422
    latest = session(client, registered)
    assert client.patch('/api/kiosk/session/preferences', headers=first, json={}).status_code == 401
    assert client.patch('/api/kiosk/session/preferences', headers=other, json={}).status_code == 200
    assert client.patch('/api/kiosk/session/preferences', headers=latest, json={}).json() == dict(face=False, voice=False, recommendation=False)
    assert client.post('/api/kiosk/session/end', headers=latest).status_code == 200
    assert client.post('/api/order-quotes', headers=latest, json=payload()).status_code == 401
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT count(*) FROM kiosk_sessions WHERE ended=1 AND (face=1 OR voice=1 OR recommendation=1)').fetchone()[0] == 0


def test_idle_and_absolute_expiry(client, monkeypatch):
    clock = datetime(2026, 10, 22, tzinfo=timezone.utc)
    monkeypatch.setattr(kiosk, 'now', lambda: clock)
    registered = device(client)
    headers = session(client, registered)
    clock += timedelta(minutes=15)
    assert client.patch('/api/kiosk/session/preferences', headers=headers, json={}).status_code == 401
    headers = session(client, registered)
    for _ in range(5):
        clock += timedelta(minutes=10)
        assert client.patch('/api/kiosk/session/preferences', headers=headers, json={}).status_code == 200
    clock += timedelta(minutes=10)
    assert client.patch('/api/kiosk/session/preferences', headers=headers, json={}).status_code == 401


@pytest.mark.parametrize('action', ['revoke', 'store'])
def test_revocation_or_store_stop_blocks_existing_credentials(client, action):
    registered = device(client)
    headers = session(client, registered)
    device_headers = {'X-Kiosk-Device': registered['device_token']}
    assert client.post('/api/kiosk/heartbeat', headers=device_headers).status_code == 200
    if action == 'revoke':
        assert client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH).status_code == 200
    else:
        with client.app.state.store.connect() as db:
            db.execute("UPDATE stores SET active=0 WHERE id='primary'")
    assert client.post('/api/kiosk/heartbeat', headers=device_headers).status_code == 401
    assert client.post('/api/kiosk/sessions', headers=device_headers).status_code == 401
    assert client.post('/api/order-quotes', headers=headers, json=payload()).status_code == 401


def test_recommendation_requires_opt_in_and_rechecks_after_inference(client, monkeypatch):
    headers = session(client)
    calls = []
    def detect(_self, _data):
        calls.append(True)
        return 55
    monkeypatch.setattr(FaceService, 'detect_age', detect)
    def recommend():
        return client.post('/api/recommend', headers=headers, files={'file': ('face.png', b'test', 'image/png')})
    assert recommend().status_code == 403 and not calls
    client.patch('/api/kiosk/session/preferences', headers=headers, json={'face': True, 'recommendation': True})
    assert recommend().status_code == 200 and len(calls) == 1
    def end_during_analysis(_self, _data):
        client.app.state.store.end_session(headers['X-Kiosk-Session'])
        return 55
    monkeypatch.setattr(FaceService, 'detect_age', end_during_analysis)
    assert recommend().status_code == 401


def test_invalid_mode_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('KIOSK_AUTH_REQUIRED', 'tru')
    with pytest.raises(ValueError, match='KIOSK_AUTH_REQUIRED'):
        create_app(tmp_path / 'invalid.db')


def test_migration_keeps_existing_quotes_orders_and_is_repeatable(tmp_path):
    store = Store(tmp_path / 'upgrade.db')
    store.initialize()
    data = OrderInput(**payload())
    order = store.create_order(data)
    quoted = store.quote(OrderInput(**payload()))
    with store.connect() as db:
        db.execute('ALTER TABLE quotes DROP COLUMN session_id')
        for table in ('kiosk_order_links', 'kiosk_sessions', 'kiosk_devices', 'kiosk_pairings'):
            db.execute(f'DROP TABLE {table}')
    store.initialize()
    store.initialize()
    with store.connect() as db:
        assert store.read_order(db, order['id']) == order
        assert db.execute('SELECT id FROM quotes').fetchone()[0] == quoted['quote_id']
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    token = store.start_session(store.register_device(store.pairing('입구')['code'])['device_token'])['session_token']
    with pytest.raises(StoreError) as error:
        store.create_order(data, token)
    assert error.value.status == 409


def test_legacy_mode_still_validates_supplied_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv('KIOSK_AUTH_REQUIRED', 'false')
    with TestClient(create_app(tmp_path / 'legacy.db')) as client:
        data = payload()
        assert client.post('/api/orders', json=data).status_code == 200
        assert client.post('/api/orders', json=data, headers={'X-Kiosk-Session': 'invalid'}).status_code == 401
