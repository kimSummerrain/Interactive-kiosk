from datetime import datetime, timezone

from test_api import AUTH, client
from test_ordering import configure, quoted


def test_stock_history_adjustment_order_and_cancel(client):
    configure(client, stock=5)
    response = client.patch('/api/owner/menus/latte_hot', auth=AUTH,
                            json={'stock': 8, 'stock_note': '  재고 실사  '})
    assert response.status_code == 200
    data = quoted(client)
    order = client.post('/api/orders/confirm', json=data).json()['order']
    client.post('/api/orders/confirm', json=data)
    for _ in range(2):
        client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH, json={'status':'cancelled'})
    result = client.get('/api/owner/stock-movements?menu_id=latte_hot', auth=AUTH).json()
    assert result['total'] == 3
    assert [m['reason'] for m in result['movements']] == ['cancel', 'order', 'owner_adjustment']
    assert [m['delta'] for m in result['movements']] == [1, -1, 3]
    assert result['movements'][-1]['note'] == '재고 실사'
    assert result['movements'][-1]['order_id'] is None
    filtered = client.get('/api/owner/stock-movements?reason=order', auth=AUTH).json()
    assert filtered['total'] == 1
    paged = client.get('/api/owner/stock-movements?page=2&page_size=1', auth=AUTH).json()
    assert paged['total'] == 3 and paged['movements'][0]['reason'] == 'order'


def test_noop_and_invalid_notes(client):
    configure(client)
    assert client.patch('/api/owner/menus/latte_hot', auth=AUTH,
                        json={'stock':5,'stock_note':'재확인'}).status_code == 200
    assert client.get('/api/owner/stock-movements', auth=AUTH).json()['total'] == 0
    for body in [{'stock_note':'사유'}, {'stock':4,'stock_note':'   '},
                 {'stock':None,'stock_note':'제한 해제'}, {'stock':4,'stock_note':None}]:
        assert client.patch('/api/owner/menus/latte_hot', auth=AUTH, json=body).status_code == 422


def test_history_auth_filters_and_kst_boundary(client):
    assert client.get('/api/owner/stock-movements').status_code == 401
    for query in ['page=0', 'page_size=101', 'reason=wrong', 'menu_id=', 'start=2026-10-07&end=2026-10-06']:
        assert client.get('/api/owner/stock-movements?' + query, auth=AUTH).status_code == 422
    with client.app.state.store.connect() as db:
        for when in ['2026-10-05T14:59:59+00:00','2026-10-05T15:00:00+00:00',
                     '2026-10-06T14:59:59+00:00','2026-10-06T15:00:00+00:00']:
            db.execute("INSERT INTO stock_movements(menu_id,delta,reason,created_at) VALUES('ame_hot',1,'owner_adjustment',?)", (when,))
    result = client.get('/api/owner/stock-movements?start=2026-10-06&end=2026-10-06', auth=AUTH).json()
    assert result['total'] == 2
    assert all(m['note'] == '' for m in result['movements'])


def test_legacy_stock_history_migration(client):
    with client.app.state.store.connect() as db:
        db.execute('DROP TABLE stock_movements')
        db.execute('''CREATE TABLE stock_movements(id INTEGER PRIMARY KEY,menu_id TEXT NOT NULL,
            order_id INTEGER,delta INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,
            UNIQUE(order_id,menu_id,reason))''')
        db.execute("INSERT INTO stock_movements VALUES(1,'ame_hot',NULL,3,'owner_adjustment',?)",
                   (datetime.now(timezone.utc).isoformat(),))
    client.app.state.store.initialize()
    client.app.state.store.initialize()
    result = client.get('/api/owner/stock-movements', auth=AUTH).json()
    assert result['total'] == 1 and result['movements'][0]['note'] == ''
