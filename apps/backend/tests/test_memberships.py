from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from test_identity import PASSWORD, identity_client


def test_revoke_grant_and_audit(identity_client):
    store = identity_client.app.state.store
    auth = ('owner-a', PASSWORD)
    assert store.change_membership('owner-a', False, ' 운영 종료 ', 'operator')
    assert identity_client.get('/api/owner/orders/export.csv', auth=auth).status_code == 403
    assert identity_client.get('/api/owner/stores', auth=auth).json()['stores'] == []
    assert not store.change_membership('owner-a', False, '재시도', 'operator')
    assert store.change_membership('owner-a', True, '운영 재개', 'operator')
    assert identity_client.get('/api/owner/menus', auth=auth).status_code == 200
    history = store.membership_history()
    assert [r['action'] for r in history] == ['grant','revoke']
    assert history[-1]['reason'] == '운영 종료'
    assert len(store.membership_history(1)) == 1
    assert 'password_hash' not in str(store.memberships())


def test_membership_validation_and_inactive_account(identity_client):
    store = identity_client.app.state.store
    for username, reason in [('missing','사유'), ('owner-a','  ')]:
        with pytest.raises(ValueError):
            store.change_membership(username, False, reason, 'operator')
    assert store.membership_history() == []
    store.change_membership('owner-a', False, '회수', 'operator')
    store.set_owner_active('owner-a', False)
    with pytest.raises(ValueError):
        store.change_membership('owner-a', True, '부여', 'operator')
    assert store.memberships()[0]['membership_active'] == 0


def test_audit_failure_rolls_back_membership(identity_client):
    store = identity_client.app.state.store
    with store.connect() as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON membership_audit BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.change_membership('owner-a', False, '회수', 'operator')
    assert store.memberships()[0]['membership_active'] == 1


def test_concurrent_revoke_only_one_audit(identity_client):
    store = identity_client.app.state.store
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.change_membership('owner-a', False, '회수', 'operator'), range(2)))
    assert sorted(results) == [False, True]
    assert len(store.membership_history()) == 1


def test_v1_upgrade_preserves_memberships(identity_client):
    store = identity_client.app.state.store
    with store.connect() as db:
        db.execute('DROP TABLE membership_audit')
        db.execute('DELETE FROM identity_migrations WHERE version=2')
    store.initialize()
    store.initialize()
    assert len(store.memberships()) == 1
    assert store.membership_history() == []
