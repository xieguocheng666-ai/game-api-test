import allure
import pytest
import yaml
from pathlib import Path


_DATA = Path(__file__).parent.parent / "data" / "login_cases.yaml"


@allure.feature("登录/顶号")
@allure.story("登录异常（数据驱动）")
@pytest.mark.parametrize(
    "case",
    yaml.safe_load(_DATA.read_text(encoding="utf-8")),
    ids=lambda c: c["name"],
)
def test_login_failure(client, case):
    # 先注册一个真实玩家 player_a，保证 wrong_password 有可对比对象
    client.post("/register", json={"username": "player_a", "password": "pass123"})
    resp = client.post("/login", json={"username": case["username"], "password": case["password"]})
    assert resp.status_code == case["expected_code"]


@allure.feature("登录/顶号")
@allure.story("顶号登录")
def test_relogin_kicks_old_token(client):
    client.post("/register", json={"username": "u3", "password": "p3"})
    t1 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    t2 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t1}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "kicked by new login"
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t2}"})
    assert resp.status_code == 200


@allure.feature("登录/顶号")
@allure.story("无效或缺失 token")
def test_invalid_or_missing_token_rejected(client):
    # 缺失 Authorization header
    resp = client.get("/inventory")
    assert resp.status_code == 401
    # 伪造 token
    resp = client.get("/inventory", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
