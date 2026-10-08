import allure
import pytest

from server import config
from server import db
from server import gacha


def _pity(player_id):
    return db.fetch_one("SELECT ssr_pity, sr_pity FROM gacha_pity WHERE player_id=%s", (player_id,))


@allure.feature("抽卡")
@allure.story("合法稀有度")
def test_gacha_returns_valid_rarity(auth_header, client):
    resp = client.post("/gacha", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["rarity"] in {"SSR", "SR", "R"}


@allure.feature("抽卡")
@allure.story("10 连保底 SR")
def test_gacha_10_pull_guarantees_sr(auth_header, client):
    rarities = [client.post("/gacha", headers=auth_header).json()["rarity"] for _ in range(10)]
    assert any(r in ("SR", "SSR") for r in rarities)


@allure.feature("抽卡")
@allure.story("90 抽硬保底 SSR")
def test_gacha_90_pull_hard_pity_forces_ssr(auth_header, client, monkeypatch):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")
    rarities = [client.post("/gacha", headers=auth_header).json()["rarity"] for _ in range(90)]
    assert rarities[-1] == "SSR"


@allure.feature("抽卡")
@allure.story("出 SR 重置 sr_pity")
def test_gacha_sr_resets_sr_pity(auth_header, client, player_id, monkeypatch):
    results = iter(["SR", "R", "R"])
    monkeypatch.setattr(gacha, "draw_once", lambda: next(results))
    r1 = client.post("/gacha", headers=auth_header).json()["rarity"]
    assert r1 == "SR"
    # 出 SR 后 sr_pity 归零
    assert _pity(player_id)["sr_pity"] == 0


@allure.feature("抽卡")
@allure.story("保底计数持久化")
def test_gacha_pity_persists_across_relogin(auth_header, client, player_id, monkeypatch):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")
    for _ in range(5):
        client.post("/gacha", headers=auth_header)
    assert _pity(player_id)["ssr_pity"] == 5
    # 重新登录（顶号），保底进度不应丢
    client.post("/login", json={"username": "player_a", "password": "pass123"})
    assert _pity(player_id)["ssr_pity"] == 5
    assert _pity(player_id)["sr_pity"] == 5


@allure.feature("抽卡")
@allure.story("扣金币 + 写背包 + 保底推进")
def test_gacha_deducts_gold_and_writes_backpack(auth_header, client, player_id, monkeypatch):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")
    gold0 = db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"]
    resp = client.post("/gacha", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["rarity"] == "R"
    assert db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"] == gold0 - config.GACHA_COST
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[config.GACHA_ITEMS["R"]] == 1
    assert _pity(player_id)["ssr_pity"] == 1
    assert _pity(player_id)["sr_pity"] == 1


@allure.feature("抽卡")
@allure.story("金币不足拒绝且保底不推进")
def test_gacha_insufficient_gold_rejected(auth_header, client, player_id):
    db.execute("UPDATE currencies SET gold=%s WHERE player_id=%s", (config.GACHA_COST - 1, player_id))
    resp = client.post("/gacha", headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient gold"
    assert db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"] == config.GACHA_COST - 1
    assert _pity(player_id) is None


@allure.feature("抽卡")
@allure.story("货币边界（差1不够/刚好够1抽/刚好够10连）")
@pytest.mark.parametrize("gold, pulls, ok", [
    (config.GACHA_COST - 1, 1, False),
    (config.GACHA_COST, 1, True),
    (config.GACHA_COST * 10, 10, True),
])
def test_gacha_currency_boundary(auth_header, client, player_id, monkeypatch, gold, pulls, ok):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")
    db.execute("UPDATE currencies SET gold=%s WHERE player_id=%s", (gold, player_id))
    statuses = [client.post("/gacha", headers=auth_header).status_code for _ in range(pulls)]
    assert all(s == (200 if ok else 400) for s in statuses)
    final = db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"]
    assert final == (0 if ok else gold)


@allure.feature("抽卡")
@allure.story("幂等键防重复扣货币")
def test_gacha_idempotency_key_prevents_duplicate_charge(auth_header, client, player_id, monkeypatch):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")
    gold0 = db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"]
    headers = {**auth_header, "Idempotency-Key": "gacha-once"}
    r1 = client.post("/gacha", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["rarity"] == "R"
    assert db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"] == gold0 - config.GACHA_COST
    r2 = client.post("/gacha", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == {"duplicate": True}
    assert db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"] == gold0 - config.GACHA_COST
    assert _pity(player_id)["ssr_pity"] == 1
