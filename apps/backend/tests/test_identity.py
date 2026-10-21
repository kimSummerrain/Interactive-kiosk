import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from src import create_app
from src.identity import hash_password, verify_password
from src.storage import Store

PASSWORD = 'test-owner-password-123'


@pytest.fixture
def identity_client(tmp_path, monkeypatch):
    monkeypatch.setenv('OWNER_AUTH_MODE', 'database')
    monkeypatch.setenv('STORE_ID', 'primary')
    monkeypatch.setenv('ADMIN_PASSWORD', 'legacy-test-password')
    with TestClient(create_app(tmp_path / 'owners.db')) as client:
        client.app.state.store.provision_owner('owner-a', PASSWORD)
        yield client


def test_hashing():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password('wrong', first)
    assert not verify_password(PASSWORD, 'corrupt')
    with pytest.raises(ValueError):
        hash_password('short')
    with pytest.raises(ValueError):
        hash_password('한글로는인증할수없는비밀번호입니다')


def test_database_auth_all_routes_and_no_legacy_fallback(identity_client):
    client = identity_client
    auth = ('owner-a', PASSWORD)
    for url in ['/api/owner/me', '/api/admin/me', '/api/owner/menus', '/api/owner/orders',
                '/api/owner/sales', '/api/owner/sales/hourly', '/api/owner/orders/export.csv',
                '/api/owner/sales/hourly/export.csv', '/api/owner/stock-movements']:
        assert client.get(url, auth=auth).status_code == 200
        assert client.get(url, auth=('admin','legacy-test-password')).status_code == 401
    assert client.get('/api/owner/stores', auth=auth).json()['stores'][0]['id'] == 'primary'
    client.app.state.store.set_owner_active('owner-a', False)
    assert client.get('/api/owner/menus', auth=auth).status_code == 401


def test_membership_and_store_revocation(identity_client):
    client = identity_client
    auth = ('owner-a', PASSWORD)
    with client.app.state.store.connect() as db:
        db.execute("INSERT INTO stores VALUES('other','다른 매장',1)")
        db.execute("INSERT INTO store_memberships SELECT 'other',id,1 FROM owner_accounts")
        db.execute("UPDATE store_memberships SET active=0 WHERE store_id='primary'")
    assert [s['id'] for s in client.get('/api/owner/stores', auth=auth).json()['stores']] == ['other']
    for url in ['/api/owner/orders', '/api/admin/orders', '/api/owner/orders/export.csv', '/api/owner/sales']:
        assert client.get(url, auth=auth).status_code == 403
    assert client.patch('/api/owner/menus/ame_hot', auth=auth, json={'price':10}).status_code == 403
    with client.app.state.store.connect() as db:
        db.execute("UPDATE store_memberships SET active=1")
        db.execute("UPDATE stores SET active=0 WHERE id='primary'")
    assert client.get('/api/owner/menus', auth=auth).status_code == 403


def test_provision_duplicate_is_atomic(identity_client):
    store = identity_client.app.state.store
    with pytest.raises(ValueError):
        store.provision_owner('owner-a', 'different-password-123')
    assert store.authenticate_owner('owner-a', PASSWORD)
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM owner_accounts').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM store_memberships').fetchone()[0] == 1


def test_version_failure_rolls_back(tmp_path):
    store = Store(tmp_path / 'unknown.db')
    with store.connect() as db:
        db.execute('CREATE TABLE identity_migrations(version INTEGER PRIMARY KEY,applied_at TEXT)')
        db.execute("INSERT INTO identity_migrations VALUES(99,'future')")
    with pytest.raises(RuntimeError):
        store.initialize()
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='menus'").fetchone()[0] == 0


def test_migration_repeat_backup_and_store_binding(tmp_path):
    path = tmp_path / 'existing.db'
    # Simulate an existing pre-identity menu table, without relying on the new initializer.
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE menus(menu_id TEXT PRIMARY KEY,menu_index INTEGER NOT NULL,name TEXT NOT NULL,price INTEGER NOT NULL,image_path TEXT)')
    db.execute("INSERT INTO menus VALUES('old',1,'기존 메뉴',1234,NULL)")
    db.commit()
    db.close()
    store = Store(path)
    backup = tmp_path / 'before.db'
    store.backup(backup)
    store.initialize()
    store.initialize()
    assert store.menus()[0]['price'] == 1234
    with pytest.raises(FileExistsError):
        store.backup(backup)
    with pytest.raises(RuntimeError):
        Store(path, 'other-store').initialize()
    db = sqlite3.connect(backup)
    assert db.execute('SELECT price FROM menus').fetchone()[0] == 1234
    assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='owner_accounts'").fetchone()[0] == 0
    db.close()


def test_failed_migration_does_not_leave_partial_tables(tmp_path):
    store = Store(tmp_path / 'partial.db')
    with store.connect() as db:
        db.execute('CREATE TABLE owner_accounts(conflict TEXT)')
    with pytest.raises(sqlite3.OperationalError):
        store.initialize()
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='stores'").fetchone()[0] == 0


def test_password_reset_revokes_old_credentials(identity_client):
    store = identity_client.app.state.store
    store.reset_owner_password('owner-a', 'replacement-password-123')
    assert identity_client.get('/api/owner/me', auth=('owner-a', PASSWORD)).status_code == 401
    assert identity_client.get('/api/owner/me', auth=('owner-a', 'replacement-password-123')).status_code == 200


def test_parallel_initialization(tmp_path):
    path = tmp_path / 'parallel.db'
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: Store(path).initialize(), range(2)))
    with Store(path).connect() as db:
        assert db.execute('SELECT COUNT(*) FROM identity_migrations').fetchone()[0] == 2
        assert db.execute('SELECT COUNT(*) FROM menus').fetchone()[0] == 14
