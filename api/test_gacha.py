import allure

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
