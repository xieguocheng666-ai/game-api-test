import allure

from server import db


def _status(player_id):
    return db.fetch_one("SELECT status FROM characters WHERE player_id=%s", (player_id,))["status"]


def _login(client, username="player_a", password="pass123"):
    return client.post("/login", json={"username": username, "password": password}).json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@allure.feature("角色状态机")
@allure.story("正常流转 offline→online→offline")
def test_status_flow_offline_online_offline(auth_header, client, player_id):
    # 建角色：默认 offline
    client.post("/characters", json={"name": "hero"}, headers=auth_header)
    assert _status(player_id) == "offline"
    # 登录 → online
    token = _login(client)
    assert _status(player_id) == "online"
    # 登出 → offline，且 token 失效
    client.post("/logout", headers=_auth(token))
    assert _status(player_id) == "offline"
    assert client.get("/inventory", headers=_auth(token)).status_code == 401


@allure.feature("角色状态机")
@allure.story("封禁角色登录被拒")
def test_ban_blocks_login(auth_header, client, player_id):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    char_id = resp.json()["id"]
    client.post(f"/characters/{char_id}/ban", headers=auth_header)
    resp = client.post("/login", json={"username": "player_a", "password": "pass123"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "account banned"


@allure.feature("角色状态机")
@allure.story("封禁状态粘滞")
def test_ban_sticky_status_persists(auth_header, client, player_id):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    char_id = resp.json()["id"]
    client.post(f"/characters/{char_id}/ban", headers=auth_header)
    assert _status(player_id) == "banned"
    # 被封后登录仍被拒，且状态不被 login 改成 online（sticky）
    resp = client.post("/login", json={"username": "player_a", "password": "pass123"})
    assert resp.status_code == 403
    assert _status(player_id) == "banned"
