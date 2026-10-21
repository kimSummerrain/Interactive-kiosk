from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from test_api import AUTH, client, payload


def configure(client, stock=5):
    assert client.patch('/api/owner/menus/latte_hot', auth=AUTH,
                        json={'stock': stock}).status_code == 200
    assert client.post('/api/owner/menus/latte_hot/options', auth=AUTH,
                       json={'option_id': 'vanilla', 'name': '바닐라 시럽', 'price': 500}).status_code == 200


def quoted(client, items=None):
    data = payload(payment_method='counter', items=items or [
        {'menu_id': 'latte_hot', 'qty': 1, 'option_ids': ['vanilla']}])
    quote = client.post('/api/order-quotes', json=data)
    assert quote.status_code == 200, quote.text
    return {**data, 'quote_id': quote.json()['quote_id']}


def stock(client):
    return next(m['stock'] for m in client.get('/api/menus').json()['menus'] if m['menu_id'] == 'latte_hot')


def test_quote_confirm_options_and_cancel_once(client):
    configure(client)
    data = quoted(client, [{'menu_id': 'latte_hot', 'qty': 2, 'option_ids': ['vanilla']},
                           {'menu_id': 'latte_hot', 'qty': 1}])
    assert stock(client) == 5  # A quote does not reserve stock.
    response = client.post('/api/orders/confirm', json=data)
    assert response.status_code == 200, response.text
    order = response.json()['order']
    assert order['total'] == 7900
    assert len(order['items']) == 2
    assert stock(client) == 2
    assert client.post('/api/orders/confirm', json=data).json() == response.json()
    assert stock(client) == 2
    for _ in range(2):
        assert client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH,
                            json={'status': 'cancelled'}).status_code == 200
    assert stock(client) == 5


def test_changed_price_and_expired_quote(client):
    configure(client)
    data = quoted(client)
    client.patch('/api/owner/menus/latte_hot', auth=AUTH, json={'price': 3000})
    assert client.post('/api/orders/confirm', json=data).status_code == 409
    assert stock(client) == 5
    data = quoted(client)
    with client.app.state.store.connect() as db:
        db.execute("UPDATE quotes SET expires_at='2000-01-01T00:00:00+00:00'")
    assert client.post('/api/orders/confirm', json=data).status_code == 409


def test_quote_bound_to_payload_and_request(client):
    configure(client)
    data = quoted(client)
    assert client.post('/api/orders/confirm', json={**data, 'request_id': str(uuid4())}).status_code == 409
    changed = {**data, 'items': [{'menu_id': 'latte_hot', 'qty': 2, 'option_ids': ['vanilla']}]}
    assert client.post('/api/orders/confirm', json=changed).status_code == 409
    assert stock(client) == 5


def test_stock_across_option_variants_and_invalid_option(client):
    configure(client, stock=2)
    data = payload(items=[{'menu_id': 'latte_hot', 'qty': 2},
                          {'menu_id': 'latte_hot', 'qty': 1, 'option_ids': ['vanilla']}])
    assert client.post('/api/order-quotes', json=data).status_code == 409
    data = payload(items=[{'menu_id': 'ame_hot', 'qty': 1, 'option_ids': ['vanilla']}])
    assert client.post('/api/order-quotes', json=data).status_code == 422
    assert stock(client) == 2


def test_last_stock_concurrent_confirm(client):
    configure(client, stock=1)
    requests = [quoted(client), quoted(client)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda d: client.post('/api/orders/confirm', json=d).status_code, requests))
    assert sorted(results) == [200, 409]
    assert stock(client) == 0


def test_unavailable_after_quote_and_legacy_path_cannot_bypass_stock(client):
    configure(client)
    data = quoted(client)
    client.patch('/api/owner/menus/latte_hot', auth=AUTH, json={'available': False})
    assert client.post('/api/orders/confirm', json=data).status_code == 422
    assert client.post('/api/orders', json=payload(items=[{'menu_id': 'latte_hot', 'qty': 1}])).status_code == 422


def test_owner_auth_and_confirmation_requirements(client):
    assert client.patch('/api/owner/menus/latte_hot', json={'stock': 2}).status_code == 401
    assert client.post('/api/owner/menus/latte_hot/options', json={
        'option_id': 'x', 'name': 'x', 'price': 0}).status_code == 401
    assert client.get('/api/owner/orders').status_code == 401
    assert client.post('/api/orders/confirm', json=payload()).status_code == 422
    assert client.patch('/api/owner/menus/latte_hot', auth=AUTH, json={'stock': -1}).status_code == 422
    assert client.patch('/api/owner/menus/latte_hot', auth=AUTH, json={'price': None}).status_code == 422


def test_snapshot_and_sales_include_option_price(client):
    configure(client)
    order = client.post('/api/orders/confirm', json=quoted(client)).json()['order']
    client.post('/api/owner/menus/latte_hot/options', auth=AUTH,
                json={'option_id': 'vanilla', 'name': '변경', 'price': 1000})
    client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH, json={'payment_status': 'paid'})
    detail = client.get(f"/api/owner/orders/{order['id']}", auth=AUTH).json()
    assert detail['items'][0]['options'][0]['name'] == '바닐라 시럽'
    assert client.get('/api/owner/sales', auth=AUTH).json()['revenue'] == 2800


def test_menu_creation_and_restart_preserves_orders(client):
    body = {'menu_id': 'vanilla_latte', 'name': '바닐라라떼', 'price': 3500, 'stock': 2}
    assert client.post('/api/owner/menus', auth=AUTH, json=body).status_code == 201
    assert client.post('/api/owner/menus', auth=AUTH, json=body).status_code == 409
    data = quoted(client, [{'menu_id': 'vanilla_latte', 'qty': 1}])
    response = client.post('/api/orders/confirm', json=data)
    assert response.status_code == 200
    client.app.state.store.initialize()
    assert client.post('/api/orders/confirm', json=data).json() == response.json()


def test_legacy_migration_preserves_snapshot_and_idempotency(client):
    import hashlib
    import json
    data = payload()
    legacy_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with client.app.state.store.connect() as db:
        db.execute("DROP TABLE order_items")
        db.execute('''CREATE TABLE order_items(order_id INTEGER,menu_id TEXT,name TEXT,
            price INTEGER,qty INTEGER,PRIMARY KEY(order_id,menu_id))''')
        db.execute('''INSERT INTO orders(id,request_id,payload_hash,created_at,order_mode,
            payment_method,total) VALUES (1,?,?,?,'takeout','card',3000)''',
                   (data['request_id'], legacy_hash, '2026-10-06T12:00:00+09:00'))
        db.execute("INSERT INTO order_items VALUES(1,'ame_hot','기존 메뉴',1500,2)")
    # The old payload included the age_group default in its canonical hash.
    data['age_group'] = None
    with client.app.state.store.connect() as db:
        db.execute('UPDATE orders SET payload_hash=?',
                   (hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),))
    client.app.state.store.initialize()
    response = client.post('/api/orders', json=data)
    assert response.status_code == 200, response.text
    assert response.json()['order']['items'][0]['name'] == '기존 메뉴'
