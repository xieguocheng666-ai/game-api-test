import pytest
from fastapi.testclient import TestClient

from server import auth, db
from server.main import app

# 按外键依赖顺序排列：先删子表再删父表，保证用例可重复执行（幂等）。
_TABLES = (
    "purchase_records",
    "gacha_pity",
    "inventory",
    "currencies",
    "characters",
    "players",
)


@pytest.fixture()
def client():
    db.init_db()
    for table in _TABLES:
        db.execute(f"DELETE FROM {table}", ())
    auth._redis.flushdb()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_header(client):
    username = "player_a"
    password = "pass123"
    client.post("/register", json={"username": username, "password": password})
    resp = client.post("/login", json={"username": username, "password": password})
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
