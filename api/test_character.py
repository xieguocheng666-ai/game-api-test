def test_create_character(auth_header, client):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "offline"


def test_ban_blocks_login(auth_header, client):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    char_id = resp.json()["id"]
    client.post(f"/characters/{char_id}/ban", headers=auth_header)
    resp = client.post("/login", json={"username": "player_a", "password": "pass123"})
    assert resp.status_code == 403
