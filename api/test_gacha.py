def test_gacha_returns_valid_rarity(auth_header, client):
    resp = client.post("/gacha", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["rarity"] in {"SSR", "SR", "R"}


def test_gacha_10_pull_guarantees_sr(auth_header, client):
    rarities = []
    for _ in range(10):
        rarities.append(client.post("/gacha", headers=auth_header).json()["rarity"])
    assert any(r in ("SR", "SSR") for r in rarities)
