from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src import create_app, kiosk
from src.storage import Store
from test_kiosk import AUTH, client, device, session

HISTORY = '/api/owner/kiosks/history'


def history(client, **params):
    response = client.get(HISTORY, auth=AUTH, params=params)
    assert response.status_code == 200
    return response.json()


def test_registration_revocation_actor_reason_and_snapshot(client):
    registered = device(client)
    with client.app.state.store.connect() as db:
        db.execute("UPDATE kiosk_devices SET name='교체된 이름' WHERE id=?", (registered['device_id'],))
    response = client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH,
                           json={'reason': '  기기 교체  '})
    assert response.status_code == 200
    events = history(client)['events']
    assert [e['action'] for e in events] == ['revoke', 'register']
    assert [e['device_name'] for e in events] == ['교체된 이름', '입구']
    assert [e['operator'] for e in events] == [AUTH[0], AUTH[0]]
    assert events[0]['reason'] == '기기 교체'
    assert not any(secret in str(events) for secret in (registered['device_token'], 'token_hash', 'code_hash', AUTH[1]))
    for _ in range(2):
        assert client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH,
                           json={'reason': '재시도'}).status_code == 200
    assert history(client)['events'] == events


@pytest.mark.parametrize('body', [{'reason': ''}, {'reason': '  '}, {'reason': 'a'*301},
                                 {'reason': '회수', 'operator': 'spoofed'}, {}])
def test_invalid_revoke_body_does_not_change_device(client, body):
    registered = device(client)
    assert client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH, json=body).status_code == 422
    assert history(client)['total'] == 1
    assert client.post('/api/kiosk/heartbeat', headers={'X-Kiosk-Device': registered['device_token']}).status_code == 200


def test_legacy_no_body_revocation_keeps_api_compatible(client):
    registered = device(client)
    assert client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH).json() == {'ok': True}
    assert history(client)['events'][0]['reason'] == ''


def test_registration_audit_failure_rolls_back_code_and_device(client):
    code = client.post('/api/owner/kiosks/pairing-codes', auth=AUTH, json={'name': '입구'}).json()['code']
    with client.app.state.store.connect() as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON kiosk_audit BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        client.post('/api/kiosk/register', json={'code': code})
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT used FROM kiosk_pairings').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM kiosk_devices').fetchone()[0] == 0
        db.execute('DROP TRIGGER fail_audit')
    assert client.post('/api/kiosk/register', json={'code': code}).status_code == 200
    assert history(client)['total'] == 1


def test_revocation_audit_failure_restores_device_and_session(client):
    registered = device(client)
    headers = session(client, registered)
    client.patch('/api/kiosk/session/preferences', headers=headers, json={'face': True})
    with client.app.state.store.connect() as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON kiosk_audit BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke", auth=AUTH, json={'reason': '교체'})
    assert client.post('/api/kiosk/heartbeat', headers={'X-Kiosk-Device': registered['device_token']}).status_code == 200
    assert client.patch('/api/kiosk/session/preferences', headers=headers, json={}).json()['face'] is True
    assert history(client)['total'] == 1


def test_concurrent_revocation_creates_one_event(client):
    registered = device(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post(f"/api/owner/kiosks/{registered['device_id']}/revoke",
            auth=AUTH, json={'reason': '기기 분실'}), range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert history(client, action='revoke')['total'] == 1


def test_kst_date_boundaries_filters_and_stable_pagination(client, monkeypatch):
    clock = datetime(2026, 10, 21, 14, 59, 59, tzinfo=timezone.utc)
    monkeypatch.setattr(kiosk, 'now', lambda: clock)
    before = device(client)
    clock = datetime(2026, 10, 21, 15, tzinfo=timezone.utc)
    first, second = device(client), device(client)
    clock = datetime(2026, 10, 22, 14, 59, 59, tzinfo=timezone.utc)
    client.post(f"/api/owner/kiosks/{first['device_id']}/revoke", auth=AUTH)
    clock = datetime(2026, 10, 22, 15, tzinfo=timezone.utc)
    after = device(client)
    dates = {'start': '2026-10-22', 'end': '2026-10-22'}
    report = history(client, **dates)
    assert report['total'] == 3
    assert [e['device_id'] for e in report['events']] == [first['device_id'], second['device_id'], first['device_id']]
    assert history(client, **dates, device_id=before['device_id'])['total'] == 0
    assert history(client, **dates, device_id=after['device_id'])['total'] == 0
    assert history(client, **dates, device_id=first['device_id'], action='register')['total'] == 1
    assert history(client, **dates, page=2, page_size=1)['events'] == [report['events'][1]]
    assert history(client, **dates, page=9)['events'] == []


@pytest.mark.parametrize('params', [{'page': 0}, {'page_size': 101}, {'action': 'delete'},
    {'start': '2026-10-23', 'end': '2026-10-22'}, {'start': '2020-01-01', 'end': '2026-10-22'},
    {'start': '9999-12-30', 'end': '9999-12-31'}, {'start': '0001-01-01', 'end': '0001-01-02'}, {'device_id': ''}])
def test_invalid_history_filters(client, params):
    assert client.get(HISTORY, auth=AUTH, params=params).status_code == 422


def test_owner_authorization_and_foreign_store_history(client):
    registered = device(client)
    headers = session(client, registered)
    assert client.get(HISTORY).status_code == 401
    assert client.get(HISTORY, headers=headers).status_code == 401
    with client.app.state.store.connect() as db:
        db.execute("INSERT INTO stores VALUES('other','다른 매장',1)")
        db.execute("INSERT INTO kiosk_devices VALUES('foreign','other','외부','hash',1,'2026-10-22T00:00:00+00:00')")
        db.execute("INSERT INTO kiosk_audit(store_id,device_id,device_name,action,operator,created_at) VALUES('other','foreign','외부','register','other-owner',?)",
                   (kiosk.now().isoformat(),))
    assert history(client)['total'] == 1
    assert history(client, device_id='foreign')['events'] == []
    assert client.post('/api/owner/kiosks/foreign/revoke', auth=AUTH).status_code == 404
    client.app.state.store.change_membership(AUTH[0], False, '회수', 'operator')
    assert client.get(HISTORY, auth=AUTH).status_code == 403


def test_upgrade_preserves_old_pairing_and_devices(tmp_path):
    store = Store(tmp_path / 'upgrade.db')
    store.initialize()
    registered = store.register_device(store.pairing('기존 기기')['code'])
    pending = store.pairing('이전 등록 코드')['code']
    with store.connect() as db:
        db.execute('DROP TABLE kiosk_audit')
        db.execute('ALTER TABLE kiosk_pairings DROP COLUMN issued_by')
    store.initialize()
    store.initialize()
    assert store.heartbeat(registered['device_token']) == {'ok': True}
    assert store.kiosk_history(kiosk.now().date(), kiosk.now().date())['total'] == 0
    store.register_device(pending)
    with store.connect() as db:
        assert db.execute('SELECT operator FROM kiosk_audit').fetchone()[0] is None
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_legacy_owner_identity_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv('OWNER_AUTH_MODE', 'legacy')
    monkeypatch.setenv('ADMIN_USERNAME', 'legacy-admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-password')
    with TestClient(create_app(tmp_path / 'legacy.db')) as client:
        auth = ('legacy-admin', 'test-password')
        code = client.post('/api/owner/kiosks/pairing-codes', auth=auth, json={'name': '기기'}).json()['code']
        client.post('/api/kiosk/register', json={'code': code})
        assert client.get(HISTORY, auth=auth).json()['events'][0]['operator'] == 'legacy-admin'
