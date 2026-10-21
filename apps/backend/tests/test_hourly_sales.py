from test_api import AUTH, client, payload
from test_ordering import configure, quoted

URL = '/api/owner/sales/hourly?start=2026-10-06&end=2026-10-06'


def place(client, items, when, paid=False, cancelled=False, options=False):
    data = quoted(client, items) if options else payload(items=items)
    order = client.post('/api/orders/confirm' if options else '/api/orders', json=data).json()['order']
    with client.app.state.store.connect() as db:
        db.execute('UPDATE orders SET created_at=? WHERE id=?', (when, order['id']))
    if paid:
        client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH, json={'payment_status': 'paid'})
    if cancelled:
        client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH, json={'status': 'cancelled'})


def test_hourly_counts_options_and_payment(client):
    configure(client)
    place(client, [{'menu_id':'latte_hot','qty':2,'option_ids':['vanilla']},
                   {'menu_id':'latte_hot','qty':1}, {'menu_id':'ame_hot','qty':1}],
          '2026-10-06T14:00:00+09:00', paid=True, options=True)
    place(client, [{'menu_id':'ame_hot','qty':2}], '2026-10-06T14:59:59+09:00')
    place(client, [{'menu_id':'ame_hot','qty':9}], '2026-10-06T14:10:00+09:00', cancelled=True)
    result = client.get(URL, auth=AUTH).json()
    assert len(result['hours']) == 24
    assert result['totals'] == dict(order_count=2, paid_order_count=1, ordered_quantity=6, sold_quantity=4, revenue=9400)
    hour = result['hours'][14]
    assert hour['order_count'] == 2
    assert sum(m['order_count'] for m in hour['menus']) == 3  # Menu counts overlap.
    latte = next(m for m in hour['menus'] if m['menu_id'] == 'latte_hot')
    assert latte['order_count'] == 1 and latte['sold_quantity'] == 3 and latte['revenue'] == 7900
    filtered = client.get(URL + '&menu_id=latte_hot&start_hour=14&end_hour=15', auth=AUTH).json()
    assert len(filtered['hours']) == 1
    assert filtered['totals']['revenue'] == 7900
    assert filtered['totals']['order_count'] == 1


def test_hourly_timezone_and_date_boundaries(client):
    for when in ['2026-10-05T14:59:59+00:00', '2026-10-05T15:00:00+00:00',
                 '2026-10-06T14:59:59+00:00', '2026-10-06T15:00:00+00:00']:
        place(client, [{'menu_id':'ame_hot','qty':1}], when, paid=True)
    data = client.get(URL, auth=AUTH).json()
    assert data['totals']['order_count'] == 2
    assert data['hours'][0]['order_count'] == data['hours'][23]['order_count'] == 1
    assert data['hours'][1]['revenue'] == 0


def test_hourly_empty_auth_and_validation(client):
    assert client.get(URL).status_code == 401
    for query in ['&start_hour=12&end_hour=12', '&start_hour=23&end_hour=2',
                  '&start_hour=-1', '&end_hour=25', '&menu_id=']:
        assert client.get(URL + query, auth=AUTH).status_code == 422
    result = client.get(URL + '&menu_id=missing', auth=AUTH).json()
    assert result['totals']['order_count'] == 0
    assert all(not h['menus'] for h in result['hours'])
