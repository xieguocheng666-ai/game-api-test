def test_buy_ok(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 200
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1001] == 1


def test_buy_insufficient_currency(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 2}, headers=auth_header)
    assert resp.status_code == 400


def test_buy_respects_limit(auth_header, client):
    client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    resp = client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    assert resp.status_code == 400
