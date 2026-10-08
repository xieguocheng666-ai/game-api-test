import allure
import pytest
import yaml
from pathlib import Path


_BOUNDARY = Path(__file__).parent.parent / "data" / "inventory_boundary.yaml"


@allure.feature("背包")
@allure.story("正常添加查询")
def test_add_item_and_query(auth_header, client):
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 5}, headers=auth_header)
    assert resp.status_code == 200
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 5


@allure.feature("背包")
@allure.story("叠加上限 999")
def test_stack_overflow_caps_at_999(auth_header, client):
    client.post("/inventory/add", json={"item_id": 1, "count": 1000}, headers=auth_header)
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 999


@allure.feature("背包")
@allure.story("满格拒绝新道具")
def test_inventory_full_rejects_new_item(auth_header, client):
    for i in range(1, 21):
        assert client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header).status_code == 200
    resp = client.post("/inventory/add", json={"item_id": 999, "count": 1}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "inventory full"


@allure.feature("背包")
@allure.story("边界值（数据驱动）")
@pytest.mark.parametrize(
    "case",
    yaml.safe_load(_BOUNDARY.read_text(encoding="utf-8")),
    ids=lambda c: f"count_{c['count']}",
)
def test_add_boundary_count(auth_header, client, case):
    resp = client.post("/inventory/add", json={"item_id": case["item_id"], "count": case["count"]}, headers=auth_header)
    assert resp.status_code == case["expected_code"]
    if case["expected_count"] is not None:
        items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
        assert items[case["item_id"]] == case["expected_count"]


@allure.feature("背包")
@allure.story("满格后叠加已有道具")
def test_add_existing_item_succeeds_when_full(auth_header, client):
    # 塞满 20 格
    for i in range(1, 21):
        client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
    # 满格后向已有道具（item_id=1）继续叠加，应成功（满格只限制新种类）
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 10}, headers=auth_header)
    assert resp.status_code == 200
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 11
