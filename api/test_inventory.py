def test_add_item_and_query(auth_header, client):
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 5}, headers=auth_header)
    assert resp.status_code == 200
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1] == 5


def test_stack_overflow_caps_at_999(auth_header, client):
    client.post("/inventory/add", json={"item_id": 1, "count": 1000}, headers=auth_header)
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1] == 999


def test_inventory_full_rejects_new_item(auth_header, client):
    for i in range(1, 21):
        resp = client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
        assert resp.status_code == 200
    resp = client.post("/inventory/add", json={"item_id": 999, "count": 1}, headers=auth_header)
    assert resp.status_code == 400
