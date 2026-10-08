import allure

from server import db


def _gold(player_id):
    return db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"]


@allure.feature("商城")
@allure.story("正常购买")
def test_buy_ok_deducts_gold_and_adds_item(auth_header, client, player_id):
    assert _gold(player_id) == 1000
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 200
    assert _gold(player_id) == 900
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1001] == 1


@allure.feature("商城")
@allure.story("货币不足")
def test_buy_insufficient_currency_keeps_gold(auth_header, client, player_id):
    before = _gold(player_id)
    resp = client.post("/shop/buy", json={"shop_item_id": 2}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient gold"
    assert _gold(player_id) == before


@allure.feature("商城")
@allure.story("限购")
def test_buy_respects_limit(auth_header, client, player_id):
    assert client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header).status_code == 200
    resp = client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "buy limit reached"


@allure.feature("商城")
@allure.story("商品不存在")
def test_buy_nonexistent_item_404(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 9999}, headers=auth_header)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "item not found"


@allure.feature("商城")
@allure.story("满格买新道具不扣金币（原子性）")
def test_buy_inventory_full_keeps_gold(auth_header, client, player_id):
    # 塞满 20 格
    for i in range(1, 21):
        client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
    before = _gold(player_id)
    # 商品 1 = sword(item_id=1001) 是新种类，背包满 → 拒绝且金币不扣
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 400
    assert _gold(player_id) == before


@allure.feature("商城")
@allure.story("连续购买精确扣减")
def test_buy_twice_exact_deduction_and_stack(auth_header, client, player_id):
    client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert _gold(player_id) == 800
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1001] == 2
