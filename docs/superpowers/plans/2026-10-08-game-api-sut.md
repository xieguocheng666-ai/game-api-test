# 游戏后端 SUT 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自写一个「像真游戏」的 FastAPI 后端（登录/顶号/角色状态机/背包/商城/抽卡保底），作为接口自动化测试的被测系统。

**Architecture:** FastAPI 单应用，路由集中在 `server/main.py`；数据访问集中在 `server/db.py`（PyMySQL 原生 SQL + 连接池）；鉴权 `server/auth.py`（PyJWT 签发 + Redis 存 `user_id→token` 实现顶号）；抽卡 `server/gacha.py`（底层 `draw_once` 纯概率 + 上层 `gacha_pull` 保底）。MySQL 存领域数据（角色状态/背包/商城/保底计数），Redis 只存会话 token。

**Tech Stack:** Python 3.11 + FastAPI + uvicorn + PyMySQL + PyJWT + redis-py + python-dotenv + pytest + TestClient。

---

## 文件结构

```
D:\game-api-test\
├── requirements.txt
├── .env.example          # 配置模板
├── .env                  # 本地配置（gitignore）
├── .gitignore
├── server/
│   ├── __init__.py
│   ├── config.py         # 读 .env，集中配置
│   ├── db.py             # MySQL 连接 + 建表 + 数据访问
│   ├── auth.py           # 密码哈希 + JWT 签发/校验 + Redis 顶号
│   ├── gacha.py          # draw_once + gacha_pull 保底逻辑
│   ├── schemas.py        # Pydantic 请求/响应模型
│   └── main.py           # FastAPI app + 8 路由
├── api/
│   ├── __init__.py
│   ├── conftest.py       # TestClient fixture + 数据重置
│   ├── test_auth.py
│   ├── test_character.py
│   ├── test_inventory.py
│   ├── test_shop.py
│   └── test_gacha.py
└── scripts/
    └── gacha_probability.py   # Plan 2 再写
```

**实现决策（写死，避免反复）：**
- **一个玩家一个角色**：`characters.player_id` 加唯一约束。多角色对测试点无增益，反而增加复杂度。状态机直接绑定玩家，与顶号干净联动。
- 密码哈希用 **PBKDF2**（标准库 `hashlib`，复用 ShopHub 做法，不引第三方）。
- 数据库 `autocommit=False`，写操作显式 `commit`，购买用事务保证原子性。
- 顶号 Key：`login_token:{user_id}`，值为当前最新 token。鉴权比对「Redis 存的」与「请求携带的」是否一致。
- 保底计数：`gacha_pity` 表（player_id 唯一），`ssr_pity` / `sr_pity` 两个字段。

---

## Task 0: 项目骨架 + 环境就绪

**Files:**
- Create: `requirements.txt`, `.env.example`, `.gitignore`, `server/__init__.py`, `server/main.py`（最小 app）

- [ ] **Step 1: 写依赖清单**

`requirements.txt`:
```
fastapi
uvicorn[standard]
pymysql
PyJWT
redis
python-dotenv
pytest
httpx
```

`.env.example`:
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=game_test

REDIS_HOST=127.0.0.1
REDIS_PORT=6379

JWT_SECRET=dev-secret-change-me
JWT_EXPIRE_SECONDS=3600
```

`.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
```

`server/__init__.py`（空文件）:
```python
```

`server/main.py`（最小骨架，后续 Task 逐个加路由）:
```python
from fastapi import FastAPI

app = FastAPI(title="Game API Test SUT")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 安装依赖**

Run: `cd /d/game-api-test && python -m pip install -r requirements.txt`
Expected: 全部安装成功，无报错

- [ ] **Step 3: 启动 Docker Desktop（Redis 依赖）**

Run: `"/c/Program Files/Docker/Docker/Docker Desktop.exe" > /dev/null 2>&1 &`
然后等引擎就绪（30s~1min），验证：
Run: `docker ps`
Expected: 能列出容器（不再报 daemon 连接错误）

- [ ] **Step 4: 起 Redis 容器**

Run: `docker run -d --name game-test-redis -p 6379:6379 redis:7`
Expected: 返回容器 ID。验证 `docker ps | grep game-test-redis` 显示 Up 状态

- [ ] **Step 5: 建 MySQL 数据库**

Run: `mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS game_test DEFAULT CHARACTER SET utf8mb4;"`
（密码从 ShopHub 项目 `D:\my-test-framework\.env` 复用；若不同，询问用户）
Expected: 无报错；`mysql -u root -p -e "SHOW DATABASES;"` 能看到 `game_test`

- [ ] **Step 6: 配置 .env + git init**

复制 `.env.example` 为 `.env`，填入真实 `DB_PASSWORD`（同 Step 5 的密码）。
Run: `cd /d/game-api-test && git init && git add -A && git commit -m "chore: project skeleton + deps"`
Expected: 完成首次提交

---

## Task 1: 配置层 + 数据库层（建表 + 数据访问）

**Files:**
- Create: `server/config.py`, `server/db.py`

- [ ] **Step 1: 写 config.py**

`server/config.py`:
```python
import os

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "game_test")

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "3600"))

# 游戏规则常量
INVENTORY_SLOT_LIMIT = 20      # 背包格子数上限（不同道具种类数）
ITEM_STACK_LIMIT = 999         # 单种道具叠加上限
GACHA_SSR_PITY = 90            # SSR 硬保底
GACHA_SR_PITY = 10             # SR 10 连保底
GACHA_RATES = {"SSR": 0.03, "SR": 0.15, "R": 0.82}
```

- [ ] **Step 2: 写 db.py（连接 + 建表）**

`server/db.py`:
```python
import pymysql
from pymysql.cursors import DictCursor

import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS characters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    player_id INT NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    level INT NOT NULL DEFAULT 1,
    status ENUM('online','offline','banned') NOT NULL DEFAULT 'offline',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS inventory (
    player_id INT NOT NULL,
    item_id INT NOT NULL,
    count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, item_id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS currencies (
    player_id INT PRIMARY KEY,
    gold INT NOT NULL DEFAULT 0,
    diamond INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS shop_items (
    id INT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    price INT NOT NULL,
    item_id INT NOT NULL,
    item_count INT NOT NULL,
    buy_limit INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS purchase_records (
    player_id INT NOT NULL,
    item_id INT NOT NULL,
    count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, item_id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS gacha_pity (
    player_id INT PRIMARY KEY,
    ssr_pity INT NOT NULL DEFAULT 0,
    sr_pity INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(id)
);
"""


def get_conn():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=DictCursor,
        autocommit=False,
    )


def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: 写 db.py 数据访问函数（追加到文件末尾）**

`server/db.py`（追加）:
```python
def fetch_one(sql, args):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()


def fetch_all(sql, args):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, args):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def execute_many(sql, arg_seq):
    """在一个事务里执行多条 SQL，全部成功才提交（用于购买的原子性）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for args in arg_seq:
                cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: 验证建表**

Run: `cd /d/game-api-test && python -c "from server import db; db.init_db(); print('tables created')"`
Expected: 输出 `tables created`，无异常

- [ ] **Step 5: Commit**

```bash
git add server/config.py server/db.py
git commit -m "feat: config layer + db schema + data access"
```

---

## Task 2: 鉴权（密码哈希 + JWT + Redis 顶号 + 登出）

**Files:**
- Create: `server/auth.py`, `server/schemas.py`, `api/__init__.py`, `api/conftest.py`, `api/test_auth.py`
- Modify: `server/main.py`

- [ ] **Step 1: 写 schemas.py（Pydantic 模型）**

`server/schemas.py`:
```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class RegisterRequest(BaseModel):
    username: str
    password: str
```

- [ ] **Step 2: 写 auth.py（密码哈希 + JWT + Redis 顶号）**

`server/auth.py`:
```python
import hashlib
import os
import time

import jwt
import redis

import config

_redis = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split("$")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return dk.hex() == dk_hex


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + config.JWT_EXPIRE_SECONDS}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> int:
    """返回 user_id；token 过期/无效抛 jwt 异常。"""
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    return int(payload["sub"])


def save_login(user_id: int, token: str):
    """顶号核心：覆盖旧 token，旧 token 随之失效。"""
    _redis.set(f"login_token:{user_id}", token)


def is_latest_token(user_id: int, token: str) -> bool:
    """鉴权：比对 Redis 里最新 token 与请求携带 token。不一致 = 被顶号。"""
    latest = _redis.get(f"login_token:{user_id}")
    return latest is not None and latest == token


def remove_login(user_id: int):
    _redis.delete(f"login_token:{user_id}")
```

- [ ] **Step 3: 写 conftest.py（TestClient + 数据重置 fixture）**

`api/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from server import db
from server.main import app


@pytest.fixture()
def client():
    db.init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_header(client):
    """注册并登录一个测试玩家，返回带 token 的 header。"""
    username = "player_a"
    password = "pass123"
    client.post("/register", json={"username": username, "password": password})
    resp = client.post("/login", json={"username": username, "password": password})
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 4: 写失败的接口测试（test_auth.py）**

`api/test_auth.py`:
```python
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
    # 顶号：第二次登录后，第一次的 token 失效
    client.post("/register", json={"username": "u3", "password": "p3"})
    t1 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    t2 = client.post("/login", json={"username": "u3", "password": "p3"}).json()["token"]
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t1}"})
    assert resp.status_code == 401
    resp = client.get("/inventory", headers={"Authorization": f"Bearer {t2}"})
    assert resp.status_code == 200
```

- [ ] **Step 5: 跑测试确认失败**

Run: `cd /d/game-api-test && python -m pytest api/test_auth.py -v`
Expected: FAIL——`/register`、`/login`、`/inventory` 路由不存在，返回 404

- [ ] **Step 6: 实现 /register 和 /login 路由**

`server/main.py`（替换为）:
```python
from fastapi import FastAPI, Depends, HTTPException, Header

import db
import auth
from schemas import LoginRequest, LoginResponse, RegisterRequest

app = FastAPI(title="Game API Test SUT")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(req: RegisterRequest):
    existing = db.fetch_one("SELECT id FROM players WHERE username=%s", (req.username,))
    if existing:
        raise HTTPException(status_code=400, detail="username exists")
    pwd_hash = auth.hash_password(req.password)
    db.execute("INSERT INTO players (username, password_hash) VALUES (%s, %s)", (req.username, pwd_hash))
    player = db.fetch_one("SELECT id FROM players WHERE username=%s", (req.username,))
    db.execute("INSERT INTO currencies (player_id) VALUES (%s)", (player["id"],))
    return {"id": player["id"]}


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    player = db.fetch_one("SELECT id, password_hash FROM players WHERE username=%s", (req.username,))
    if not player or not auth.verify_password(req.password, player["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = auth.create_token(player["id"])
    auth.save_login(player["id"], token)
    return {"token": token}


def get_current_user(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.split(" ", 1)[1]
    try:
        user_id = auth.decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="token expired or invalid")
    if not auth.is_latest_token(user_id, token):
        raise HTTPException(status_code=401, detail="kicked by new login")
    return user_id


@app.get("/inventory")
def get_inventory(user_id: int = Depends(get_current_user)):
    return {"items": db.fetch_all("SELECT item_id, count FROM inventory WHERE player_id=%s", (user_id,))}
```

- [ ] **Step 7: 跑测试确认通过**

Run: `cd /d/game-api-test && python -m pytest api/test_auth.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 8: Commit**

```bash
git add server/auth.py server/schemas.py server/main.py api/
git commit -m "feat: register + login with JWT + redis 顶号"
```

---

## Task 3: 角色（创角 + 封禁 + 状态机）

**Files:**
- Create: `api/test_character.py`
- Modify: `server/main.py`, `server/schemas.py`

- [ ] **Step 1: 写失败的测试**

`api/test_character.py`:
```python
def test_create_character(auth_header, client):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "offline"


def test_ban_blocks_login(auth_header, client):
    resp = client.post("/characters", json={"name": "hero"}, headers=auth_header)
    char_id = resp.json()["id"]
    client.post(f"/characters/{char_id}/ban", headers=auth_header)
    # 被 ban 后无法登录（注册+登录流程重做，因为 auth_header 是 player_a）
    resp = client.post("/login", json={"username": "player_a", "password": "pass123"})
    assert resp.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/game-api-test && python -m pytest api/test_character.py -v`
Expected: FAIL——`/characters` 路由 404

- [ ] **Step 3: 实现创角 + 封禁路由（并让 login 检查 banned）**

`server/schemas.py`（追加）:
```python
class CreateCharacterRequest(BaseModel):
    name: str
```

`server/main.py`（追加路由；login 补状态检查）:
```python
@app.post("/characters")
def create_character(req: CreateCharacterRequest, user_id: int = Depends(get_current_user)):
    existing = db.fetch_one("SELECT id FROM characters WHERE player_id=%s", (user_id,))
    if existing:
        raise HTTPException(status_code=400, detail="character exists")
    db.execute(
        "INSERT INTO characters (player_id, name) VALUES (%s, %s)",
        (user_id, req.name),
    )
    char = db.fetch_one("SELECT id, name, level, status FROM characters WHERE player_id=%s", (user_id,))
    return char


@app.post("/characters/{char_id}/ban")
def ban_character(char_id: int, user_id: int = Depends(get_current_user)):
    db.execute("UPDATE characters SET status='banned' WHERE id=%s AND player_id=%s", (char_id, user_id))
    return {"status": "banned"}
```

`server/main.py` 的 `login` 里，在签发 token 前插入角色状态检查：
```python
    char = db.fetch_one("SELECT status FROM characters WHERE player_id=%s", (player["id"],))
    if char and char["status"] == "banned":
        raise HTTPException(status_code=403, detail="account banned")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/game-api-test && python -m pytest api/test_character.py -v`
Expected: PASS（2 个测试全绿）

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/schemas.py api/test_character.py
git commit -m "feat: character create + ban (状态机)"
```

---

## Task 4: 背包（查背包 + 加道具，满格/叠加）

**Files:**
- Create: `api/test_inventory.py`
- Modify: `server/main.py`

- [ ] **Step 1: 写失败的测试**

`api/test_inventory.py`:
```python
def test_add_item_and_query(auth_header, client):
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 5}, headers=auth_header)
    assert resp.status_code == 200
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1] == 5


def test_stack_overflow_caps_at_999(auth_header, client):
    client.post("/inventory/add", json={"item_id": 1, "count": 1000}, headers=auth_header)
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1] == 999


def test_inventory_full_rejects_new_item(auth_header, client):
    for i in range(1, 21):  # 塞满 20 格
        resp = client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
        assert resp.status_code == 200
    resp = client.post("/inventory/add", json={"item_id": 999, "count": 1}, headers=auth_header)
    assert resp.status_code == 400
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/game-api-test && python -m pytest api/test_inventory.py -v`
Expected: FAIL——`/inventory/add` 路由 404

- [ ] **Step 3: 实现加道具路由**

`server/main.py`（追加）:
```python
@app.post("/inventory/add")
def add_item(item_id: int, count: int, user_id: int = Depends(get_current_user)):
    existing = db.fetch_one("SELECT count FROM inventory WHERE player_id=%s AND item_id=%s", (user_id, item_id))
    if existing:
        new_count = min(existing["count"] + count, config.ITEM_STACK_LIMIT)
        db.execute("UPDATE inventory SET count=%s WHERE player_id=%s AND item_id=%s", (new_count, user_id, item_id))
    else:
        slots = db.fetch_one("SELECT COUNT(*) AS c FROM inventory WHERE player_id=%s", (user_id,))["c"]
        if slots >= config.INVENTORY_SLOT_LIMIT:
            raise HTTPException(status_code=400, detail="inventory full")
        db.execute(
            "INSERT INTO inventory (player_id, item_id, count) VALUES (%s, %s, %s)",
            (user_id, item_id, min(count, config.ITEM_STACK_LIMIT)),
        )
    return {"item_id": item_id}
```

（`main.py` 顶部补 `import config`）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/game-api-test && python -m pytest api/test_inventory.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 5: Commit**

```bash
git add server/main.py api/test_inventory.py
git commit -m "feat: inventory add with 满格/叠加"
```

---

## Task 5: 商城（购买原子性 + 限购）

**Files:**
- Create: `api/test_shop.py`
- Modify: `server/main.py`

- [ ] **Step 1: 写失败的测试**

`api/test_shop.py`:
```python
def test_buy_ok(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 200
    # 金币从 1000 扣到 900（商品价 100），背包多了 item 1001
    resp = client.get("/inventory", headers=auth_header)
    items = {i["item_id"]: i["count"] for i in resp.json()["items"]}
    assert items[1001] == 1


def test_buy_insufficient_currency(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 2}, headers=auth_header)
    assert resp.status_code == 400  # 商品 2 价 999999，金币不够


def test_buy_respects_limit(auth_header, client):
    client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    resp = client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    assert resp.status_code == 400  # 商品 3 限购 1 次
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/game-api-test && python -m pytest api/test_shop.py -v`
Expected: FAIL——`/shop/buy` 路由 404

- [ ] **Step 3: 实现购买路由（事务原子性）**

`server/main.py`（追加）:
```python
@app.post("/shop/buy")
def buy(shop_item_id: int, user_id: int = Depends(get_current_user)):
    item = db.fetch_one("SELECT * FROM shop_items WHERE id=%s", (shop_item_id,))
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    # 限购检查
    bought = db.fetch_one(
        "SELECT count FROM purchase_records WHERE player_id=%s AND item_id=%s",
        (user_id, item["item_id"]),
    )
    bought_count = bought["count"] if bought else 0
    if bought_count >= item["buy_limit"]:
        raise HTTPException(status_code=400, detail="buy limit reached")
    # 货币检查
    currency = db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (user_id,))
    if currency["gold"] < item["price"]:
        raise HTTPException(status_code=400, detail="insufficient gold")
    # 原子性：扣货币 + 加背包 + 记限购，三步在一个事务里
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE currencies SET gold=gold-%s WHERE player_id=%s", (item["price"], user_id))
            cur.execute(
                "INSERT INTO inventory (player_id, item_id, count) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE count=LEAST(count+%s, %s)",
                (user_id, item["item_id"], item["item_count"], item["item_count"], config.ITEM_STACK_LIMIT),
            )
            cur.execute(
                "INSERT INTO purchase_records (player_id, item_id, count) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE count=count+%s",
                (user_id, item["item_id"], 1, 1),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True}
```

- [ ] **Step 4: 造种子数据（商品 + 初始金币）**

Run: `cd /d/game-api-test && python -c "from server import db; db.init_db(); db.execute('INSERT IGNORE INTO shop_items (id,name,price,item_id,item_count,buy_limit) VALUES (1,\"sword\",100,1001,1,0),(2,\"gems\",999999,1002,1,0),(3,\"ticket\",10,1003,1,1)'); print('seeded')"`
Expected: 输出 `seeded`

`server/db.py` 的 `init_db` 里也补种默认商品（追加到 SCHEMA 后，或单独函数）。追加到 `db.py`:
```python
def seed_shop():
    execute("INSERT IGNORE INTO shop_items (id,name,price,item_id,item_count,buy_limit) "
            "VALUES (1,'sword',100,1001,1,0),(2,'gems',999999,1002,1,0),(3,'ticket',10,1003,1,1)", ())
```

并让 conftest 的 `client` fixture 里，注册时给玩家初始 1000 金币（改 register 逻辑或 fixture）。在 `main.py` 的 register 里，`INSERT INTO currencies (player_id, gold) VALUES (%s, 1000)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/game-api-test && python -m pytest api/test_shop.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/db.py api/test_shop.py
git commit -m "feat: shop buy with 事务原子性 + 限购"
```

---

## Task 6: 抽卡（draw_once 纯概率 + gacha_pull 保底）

**Files:**
- Create: `server/gacha.py`, `api/test_gacha.py`
- Modify: `server/main.py`

- [ ] **Step 1: 写 gacha.py（纯概率 + 保底）**

`server/gacha.py`:
```python
import random

import config


def draw_once() -> str:
    """纯概率抽卡，无保底。供概率统计验证使用。"""
    return random.choices(list(config.GACHA_RATES), weights=list(config.GACHA_RATES.values()))[0]


def gacha_pull(player_id: int) -> str:
    """带保底的抽卡：90 抽硬保底 SSR，10 连保底 SR。"""
    from server import db  # 局部 import 避免循环

    pity = db.fetch_one("SELECT ssr_pity, sr_pity FROM gacha_pity WHERE player_id=%s", (player_id,))
    if not pity:
        db.execute("INSERT INTO gacha_pity (player_id) VALUES (%s)", (player_id,))
        ssr_pity = sr_pity = 0
    else:
        ssr_pity, sr_pity = pity["ssr_pity"], pity["sr_pity"]

    ssr_pity += 1
    sr_pity += 1

    if ssr_pity >= config.GACHA_SSR_PITY:
        result = "SSR"
    elif sr_pity >= config.GACHA_SR_PITY:
        result = "SR"
    else:
        result = draw_once()

    if result == "SSR":
        ssr_pity, sr_pity = 0, 0
    elif result == "SR":
        sr_pity = 0

    db.execute("UPDATE gacha_pity SET ssr_pity=%s, sr_pity=%s WHERE player_id=%s", (ssr_pity, sr_pity, player_id))
    return result
```

- [ ] **Step 2: 写失败的测试**

`api/test_gacha.py`:
```python
def test_gacha_returns_valid_rarity(auth_header, client):
    resp = client.post("/gacha", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["rarity"] in {"SSR", "SR", "R"}


def test_gacha_10_pull_guarantees_sr(auth_header, client):
    # 连续 10 抽，至少 1 个 SR 或更好（第 10 抽必非 R）
    rarities = []
    for _ in range(10):
        rarities.append(client.post("/gacha", headers=auth_header).json()["rarity"])
    assert any(r in ("SR", "SSR") for r in rarities)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd /d/game-api-test && python -m pytest api/test_gacha.py -v`
Expected: FAIL——`/gacha` 路由 404

- [ ] **Step 4: 实现抽卡路由**

`server/main.py`（追加）:
```python
from server import gacha

@app.post("/gacha")
def gacha_pull(user_id: int = Depends(get_current_user)):
    rarity = gacha.gacha_pull(user_id)
    return {"rarity": rarity}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/game-api-test && python -m pytest api/test_gacha.py -v`
Expected: PASS（2 个测试全绿）

- [ ] **Step 6: Commit**

```bash
git add server/gacha.py server/main.py api/test_gacha.py
git commit -m "feat: gacha draw_once + 保底 gacha_pull"
```

---

## Task 7: 全量回归 + 登出

**Files:**
- Modify: `server/main.py`, `api/test_auth.py`

- [ ] **Step 1: 实现登出（角色 offline + 删 Redis）**

`server/main.py`（追加）:
```python
@app.post("/logout")
def logout(user_id: int = Depends(get_current_user)):
    auth.remove_login(user_id)
    db.execute("UPDATE characters SET status='offline' WHERE player_id=%s", (user_id,))
    return {"ok": True}
```

- [ ] **Step 2: 全量跑通所有测试**

Run: `cd /d/game-api-test && python -m pytest api/ -v`
Expected: 全部 PASS（当前约 16 个测试全绿）

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: logout + full regression pass"
```

---

## Self-Review 记录

- **Spec coverage:** 8 接口全部有 task——/login(T2)、/logout(T7)、/characters+ban(T3)、/inventory+add(T4)、/shop/buy(T5)、/gacha(T6)、/register(T2，为测试铺路)。领域模型 7 张表在 T1 建齐。顶号(T2)、角色状态机(T3)、背包满格/叠加(T4)、商城原子性/限购(T5)、抽卡概率+保底(T6) 全部覆盖。
- **Placeholder scan:** 无 TBD/TODO；每个代码步骤都有完整代码。
- **Type consistency:** `db.fetch_one/fetch_all/execute`、`auth.create_token/save_login/is_latest_token/remove_login`、`gacha.draw_once/gacha_pull`、`get_current_user` 在前后 Task 命名一致；`config.ITEM_STACK_LIMIT/INVENTORY_SLOT_LIMIT/GACHA_SSR_PITY/GACHA_SR_PITY/GACHA_RATES` 定义于 Task 1，使用于 Task 4/6。

**后续（Plan 2）：** 27 用例完整版（含边界/异常/数据驱动/Allure）+ 抽卡概率统计脚本（卡方 + 置信区间）。本 Plan 的 TDD 测试是基础冒烟，Plan 2 会扩展场景并补统计验证。
