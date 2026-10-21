import csv
import io

from test_api import AUTH, client, payload


def rows(response):
    assert response.status_code == 200, response.text
    assert response.content.startswith(b'\xef\xbb\xbf')
    assert response.headers['content-type'].startswith('text/csv')
    assert response.headers['cache-control'] == 'no-store'
    return list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))


def test_order_csv_snapshots_escaping_and_filter(client):
    name = '=수식,"이름"\n다음줄'
    client.patch('/api/owner/menus/ame_hot', auth=AUTH, json={'name': name})
    client.post('/api/orders', json=payload())
    result = client.get('/api/owner/orders/export.csv', auth=AUTH)
    data = rows(result)
    assert len(data) == 2
    assert data[1][7] == "'" + name
    assert data[1][8:11] == ['1500', '2', '3000']
    assert len(rows(client.get('/api/owner/orders/export.csv?status=completed', auth=AUTH))) == 1
    assert 'attachment;' in result.headers['content-disposition']


def test_hourly_csv_matches_json(client):
    order = client.post('/api/orders', json=payload()).json()['order']
    client.patch(f"/api/owner/orders/{order['id']}", auth=AUTH, json={'payment_status':'paid'})
    report = client.get('/api/owner/sales/hourly?menu_id=ame_hot', auth=AUTH).json()
    data = rows(client.get('/api/owner/sales/hourly/export.csv?menu_id=ame_hot', auth=AUTH))
    assert len(data) == 25
    assert sum(int(row[-1]) for row in data[1:]) == report['totals']['revenue'] == 3000
    for h, row in zip(report['hours'], data[1:]):
        assert list(map(int, row[4:])) == [h[k] for k in
            ['order_count','paid_order_count','ordered_quantity','sold_quantity','revenue']]


def test_csv_auth_and_invalid_queries(client):
    for path in ['/api/owner/orders/export.csv', '/api/owner/sales/hourly/export.csv']:
        assert client.get(path).status_code == 401
        assert client.get(path + '?start=2026-10-21&end=2026-10-20', auth=AUTH).status_code == 422
    assert client.get('/api/owner/sales/hourly/export.csv?start_hour=5&end_hour=4', auth=AUTH).status_code == 422


def test_export_limit_is_explicit_not_silent_truncation(client):
    order = client.post('/api/orders', json=payload()).json()['order']
    with client.app.state.store.connect() as db:
        db.executemany('INSERT INTO order_items VALUES(?,?,?,?,?,?,?)',
            [(order['id'], n, 'ame_hot', '커피', 1500, 1, '[]') for n in range(1,10001)])
    response = client.get('/api/owner/orders/export.csv', auth=AUTH)
    assert response.status_code == 422 and '10,000' in response.json()['detail']
