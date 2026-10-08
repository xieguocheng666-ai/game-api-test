def test_register_and_login(client):
    resp = client.post("/register", json={"username": "u1", "password": "p1"})
    assert resp.status_code == 200
    resp = client.post("/login", json={"username": "u1", "password": "p1"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password(client):
    client.post("/register", json={"username": "u2", "password": "right"})
    resp = client.post("/login", json={"username": "u2", "password": "wrong"})
    assert resp.status_code == 401


def test_relogin_kicks_old_token(client):
    client.post("/register", json={"username": "u3", "password": "p3"})
    t1 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    t2 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t1}"})
    assert resp.status_code == 401
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t2}"})
    assert resp.status_code == 200
