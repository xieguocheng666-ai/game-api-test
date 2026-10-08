import allure


@allure.feature("基础")
@allure.story("健康检查")
def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@allure.feature("基础")
@allure.story("注册登录主流程")
def test_register_then_login(client):
    resp = client.post("/register", json={"username": "basic_u", "password": "p1"})
    assert resp.status_code == 200
    assert "id" in resp.json()
    resp = client.post("/login", json={"username": "basic_u", "password": "p1"})
    assert resp.status_code == 200
    assert "token" in resp.json()


@allure.feature("基础")
@allure.story("重复注册")
def test_register_duplicate_username_rejected(client):
    client.post("/register", json={"username": "dup_u", "password": "p1"})
    resp = client.post("/register", json={"username": "dup_u", "password": "p2"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "username exists"
