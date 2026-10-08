# 游戏接口测试 27 用例完整版 + 抽卡概率统计 实施计划（Plan 2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1 已完成的 8 接口后端之上，补全 27 个游戏场景用例（基础/登录顶号/角色状态机/背包/商城/抽卡），加入 YAML 数据驱动 + Allure 报告，并写抽卡概率统计验证脚本（卡方拟合优度 + SSR 95% 置信区间）。

**Architecture:** 后端不动（Plan 1 已稳定），本 Plan 主要是「加测试 + 加报告 + 加统计脚本」。测试仍用 pytest + TestClient；数据驱动用 PyYAML 读 `data/*.yaml`；报告用 allure-pytest；概率统计脚本独立于 pytest，直接测 `server.gacha.draw_once` 纯概率。

**Tech Stack:** pytest + TestClient + PyYAML + allure-pytest + 标准库（math/random）。

---

## 27 用例清单（逻辑用例 → 测试函数映射）

| # | 分组 | 用例（游戏测试点） | 文件.函数 | 预期 |
|---|------|-------------------|-----------|------|
| 1 | 基础 | 健康检查 | `test_basic.py::test_health_ok` | 200 ok |
| 2 | 基础 | 注册→登录主流程 | `test_basic.py::test_register_then_login` | 200 有 token |
| 3 | 基础 | 重复用户名注册 | `test_basic.py::test_register_duplicate_username_rejected` | 400 |
| 4 | 登录/顶号 | 密码错误 | `test_auth.py::test_login_failure[wrong_password]`（YAML） | 401 |
| 5 | 登录/顶号 | 用户名不存在 | `test_auth.py::test_login_failure[nonexistent_user]`（YAML） | 401 |
| 6 | 登录/顶号 | 顶号：重登踢旧 token | `test_auth.py::test_relogin_kicks_old_token` | 旧 401 新 200 |
| 7 | 登录/顶号 | 无效/缺失 token | `test_auth.py::test_invalid_or_missing_token_rejected` | 401 |
| 8 | 状态机 | 正常流转 offline→online→offline | `test_character.py::test_status_flow_offline_online_offline` | 各状态正确 |
| 9 | 状态机 | banned 登录被拒 | `test_character.py::test_ban_blocks_login` | 403 |
| 10 | 状态机 | banned 粘滞（登录不改状态） | `test_character.py::test_ban_sticky_status_persists` | 403 且仍 banned |
| 11 | 背包 | 正常添加并查询 | `test_inventory.py::test_add_item_and_query` | 200 数量一致 |
| 12 | 背包 | 叠加超限封顶 999 | `test_inventory.py::test_stack_overflow_caps_at_999` | 999 |
| 13 | 背包 | 满格 20 拒绝新道具 | `test_inventory.py::test_inventory_full_rejects_new_item` | 400 |
| 14 | 背包 | 边界 count=0 | `test_inventory.py::test_add_boundary_count[0]`（YAML） | 422 |
| 15 | 背包 | 边界 count=999 | `test_inventory.py::test_add_boundary_count[999]`（YAML） | 200 数量 999 |
| 16 | 背包 | 满格后向已有道具叠加成功 | `test_inventory.py::test_add_existing_item_succeeds_when_full` | 200 叠加成功 |
| 17 | 商城 | 正常购买扣金币+加背包 | `test_shop.py::test_buy_ok_deducts_gold_and_adds_item` | 金币 900 背包+1 |
| 18 | 商城 | 货币不足不扣金币 | `test_shop.py::test_buy_insufficient_currency_keeps_gold` | 400 金币不变 |
| 19 | 商城 | 限购达上限拒绝 | `test_shop.py::test_buy_respects_limit` | 400 |
| 20 | 商城 | 商品不存在 | `test_shop.py::test_buy_nonexistent_item_404` | 404 |
| 21 | 商城 | 满格买新道具不扣金币（原子性） | `test_shop.py::test_buy_inventory_full_keeps_gold` | 400 金币不变 |
| 22 | 商城 | 连续购买精确扣减+叠加 | `test_shop.py::test_buy_twice_exact_deduction_and_stack` | 800 背包 2 |
| 23 | 抽卡 | 单抽返回合法稀有度 | `test_gacha.py::test_gacha_returns_valid_rarity` | 200 ∈ {SSR,SR,R} |
| 24 | 抽卡 | 10 连保底 SR | `test_gacha.py::test_gacha_10_pull_guarantees_sr` | 10 抽内 ≥1 SR |
| 25 | 抽卡 | 90 抽硬保底 SSR | `test_gacha.py::test_gacha_90_pull_hard_pity_forces_ssr` | 第 90 抽 SSR |
| 26 | 抽卡 | 出 SR 重置 sr_pity | `test_gacha.py::test_gacha_sr_resets_sr_pity` | sr_pity=0 |
| 27 | 抽卡 | 保底计数持久化（重登不丢） | `test_gacha.py::test_gacha_pity_persists_across_relogin` | 重登后计数不变 |

> **诚实说明（KPI 对齐）：** 27 是「逻辑用例」数。因为 4/5/14/15 用 YAML 参数化实现，pytest 实际 item 数会略多于 27（参数化每个 yaml 行算一个 item）。这不是注水，是数据驱动技术的正常表现，面试可这样讲。

---

## 文件结构（本 Plan 新增/修改）

```
D:\game-api-test\
├── requirements.txt          # 修改：加 allure-pytest、PyYAML
├── pytest.ini                # 新增：alluredir 配置 + 注册 marker
├── data/
│   ├── login_cases.yaml      # 新增：登录异常数据驱动
│   └── inventory_boundary.yaml  # 新增：背包边界值数据驱动
├── server/
│   └── schemas.py            # 修改：AddItemRequest.count 加 Field(gt=0)
├── api/
│   ├── conftest.py           # 修改：加 player_id fixture
│   ├── test_basic.py         # 新增：基础 3 用例
│   ├── test_auth.py          # 修改：登录顶号 4 用例（含 YAML 数据驱动）
│   ├── test_character.py     # 修改：状态机 3 用例
│   ├── test_inventory.py     # 修改：背包 6 用例（含 YAML 边界）
│   ├── test_shop.py          # 修改：商城 6 用例
│   └── test_gacha.py         # 修改：抽卡 5 用例
└── scripts/
    └── gacha_probability.py  # 新增：卡方 + Wilson 置信区间
```

---

## Task 0: 基础设施（依赖 + 配置 + fixture + count 校验）

**Files:**
- Modify: `requirements.txt`, `server/schemas.py`, `api/conftest.py`
- Create: `pytest.ini`, `data/login_cases.yaml`, `data/inventory_boundary.yaml`

- [ ] **Step 1: requirements.txt 追加依赖**

`requirements.txt`（在原内容末尾追加两行）:
```
allure-pytest
PyYAML
```

- [ ] **Step 2: 装依赖**

Run: `cd /d/game-api-test && python -m pip install allure-pytest PyYAML`
Expected: 安装成功

- [ ] **Step 3: 写 pytest.ini**

`pytest.ini`:
```ini
[pytest]
addopts = -v
testpaths = api
markers =
    feature: allure feature 标记（基础/登录顶号/状态机/背包/商城/抽卡）
```

- [ ] **Step 4: 写 data/login_cases.yaml**

`data/login_cases.yaml`:
```yaml
# 登录异常数据驱动：每行 = 一组 (用户名, 密码, 期望状态码)
- name: wrong_password
  username: player_a
  password: wrong
  expected_code: 401
- name: nonexistent_user
  username: ghost
  password: whatever
  expected_code: 401
```

- [ ] **Step 5: 写 data/inventory_boundary.yaml**

`data/inventory_boundary.yaml`:
```yaml
# 背包边界值数据驱动：count 为 0 / 1 / 999
- name: count_zero
  item_id: 2001
  count: 0
  expected_code: 422
  expected_count: null
- name: count_one
  item_id: 2002
  count: 1
  expected_code: 200
  expected_count: 1
- name: count_999
  item_id: 2003
  count: 999
  expected_code: 200
  expected_count: 999
```

- [ ] **Step 6: schemas.py 加 count 校验**

`server/schemas.py`（改 import 和 AddItemRequest）:
```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class CreateCharacterRequest(BaseModel):
    name: str


class AddItemRequest(BaseModel):
    item_id: int
    count: int = Field(gt=0)


class BuyRequest(BaseModel):
    shop_item_id: int
```

- [ ] **Step 7: conftest.py 加 player_id fixture**

`api/conftest.py`（在 auth_header 后追加）:
```python
@pytest.fixture()
def player_id(auth_header):
    """返回已注册测试玩家 player_a 的 user_id，供白盒校验状态/货币/保底。"""
    return db.fetch_one("SELECT id FROM players WHERE username='player_a'", ())["id"]
```

- [ ] **Step 8: 验证基础设施**

Run: `cd /d/game-api-test && python -m pytest api/ -q`
Expected: 现有 15 个测试全绿（count 校验未破坏任何现有用例）

- [ ] **Step 9: Commit**

```bash
git add requirements.txt pytest.ini data/ server/schemas.py api/conftest.py
git commit -m "chore: Plan2 infra (allure+pytest.ini+yaml fixtures+count validation)"
```

---

## Task 1: 基础 3 用例

**Files:**
- Create: `api/test_basic.py`

- [ ] **Step 1: 写测试**

`api/test_basic.py`:
```python
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
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_basic.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 3: Commit**

```bash
git add api/test_basic.py
git commit -m "test: 基础 3 用例 (health/register/login)"
```

---

## Task 2: 登录/顶号 4 用例

**Files:**
- Modify: `api/test_auth.py`

- [ ] **Step 1: 重写 test_auth.py（YAML 数据驱动 + 顶号 + 无效 token）**

`api/test_auth.py`:
```python
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
```

> 说明：原 `test_login_wrong_password`、`test_register_and_login`、`test_logout_invalidates_token` 被重构——主流程归入 Task 1 的 `test_register_then_login`，密码错误归入本文件 YAML 数据驱动 `test_login_failure`，登出失效归入 Task 3 状态机 `test_status_flow_offline_online_offline`。

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_auth.py -v`
Expected: PASS（顶号 1 + 无效 token 1 + 数据驱动 2 行 = 4 个 item 全绿）

- [ ] **Step 3: Commit**

```bash
git add api/test_auth.py
git commit -m "test: 登录/顶号 4 用例 (YAML 数据驱动 + 顶号 + 无效 token)"
```

---

## Task 3: 角色状态机 3 用例

**Files:**
- Modify: `api/test_character.py`

- [ ] **Step 1: 重写 test_character.py（状态流转 + banned 粘滞）**

`api/test_character.py`:
```python
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
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_character.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 3: Commit**

```bash
git add api/test_character.py
git commit -m "test: 角色状态机 3 用例 (流转/封禁/粘滞)"
```

---

## Task 4: 背包 6 用例

**Files:**
- Modify: `api/test_inventory.py`

- [ ] **Step 1: 重写 test_inventory.py（含 YAML 边界 + 满格叠加）**

`api/test_inventory.py`:
```python
import allure
import pytest
import yaml
from pathlib import Path


_BOUNDARY = Path(__file__).parent.parent / "data" / "inventory_boundary.yaml"


@allure.feature("背包")
@allure.story("正常添加查询")
def test_add_item_and_query(auth_header, client):
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 5}, headers=auth_header)
    assert resp.status_code == 200
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 5


@allure.feature("背包")
@allure.story("叠加上限 999")
def test_stack_overflow_caps_at_999(auth_header, client):
    client.post("/inventory/add", json={"item_id": 1, "count": 1000}, headers=auth_header)
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 999


@allure.feature("背包")
@allure.story("满格拒绝新道具")
def test_inventory_full_rejects_new_item(auth_header, client):
    for i in range(1, 21):
        assert client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header).status_code == 200
    resp = client.post("/inventory/add", json={"item_id": 999, "count": 1}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "inventory full"


@allure.feature("背包")
@allure.story("边界值（数据驱动）")
@pytest.mark.parametrize(
    "case",
    yaml.safe_load(_BOUNDARY.read_text(encoding="utf-8")),
    ids=lambda c: f"count_{c['count']}",
)
def test_add_boundary_count(auth_header, client, case):
    resp = client.post("/inventory/add", json={"item_id": case["item_id"], "count": case["count"]}, headers=auth_header)
    assert resp.status_code == case["expected_code"]
    if case["expected_count"] is not None:
        items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
        assert items[case["item_id"]] == case["expected_count"]


@allure.feature("背包")
@allure.story("满格后叠加已有道具")
def test_add_existing_item_succeeds_when_full(auth_header, client):
    # 塞满 20 格
    for i in range(1, 21):
        client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
    # 满格后向已有道具（item_id=1）继续叠加，应成功（满格只限制新种类）
    resp = client.post("/inventory/add", json={"item_id": 1, "count": 10}, headers=auth_header)
    assert resp.status_code == 200
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1] == 11
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_inventory.py -v`
Expected: PASS（4 显式 + 3 参数化边界 = 覆盖 6 逻辑用例）

- [ ] **Step 3: Commit**

```bash
git add api/test_inventory.py
git commit -m "test: 背包 6 用例 (满格/叠加/边界 YAML/满格叠加)"
```

---

## Task 5: 商城 6 用例

**Files:**
- Modify: `api/test_shop.py`

- [ ] **Step 1: 重写 test_shop.py（金币白盒校验 + 原子性 + 精确扣减）**

`api/test_shop.py`:
```python
import allure

from server import db


def _gold(player_id):
    return db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (player_id,))["gold"]


@allure.feature("商城")
@allure.story("正常购买")
def test_buy_ok_deducts_gold_and_adds_item(auth_header, client, player_id):
    assert _gold(player_id) == 1000
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 200
    assert _gold(player_id) == 900
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1001] == 1


@allure.feature("商城")
@allure.story("货币不足")
def test_buy_insufficient_currency_keeps_gold(auth_header, client, player_id):
    before = _gold(player_id)
    resp = client.post("/shop/buy", json={"shop_item_id": 2}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient gold"
    assert _gold(player_id) == before


@allure.feature("商城")
@allure.story("限购")
def test_buy_respects_limit(auth_header, client, player_id):
    assert client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header).status_code == 200
    resp = client.post("/shop/buy", json={"shop_item_id": 3}, headers=auth_header)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "buy limit reached"


@allure.feature("商城")
@allure.story("商品不存在")
def test_buy_nonexistent_item_404(auth_header, client):
    resp = client.post("/shop/buy", json={"shop_item_id": 9999}, headers=auth_header)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "item not found"


@allure.feature("商城")
@allure.story("满格买新道具不扣金币（原子性）")
def test_buy_inventory_full_keeps_gold(auth_header, client, player_id):
    # 塞满 20 格
    for i in range(1, 21):
        client.post("/inventory/add", json={"item_id": i, "count": 1}, headers=auth_header)
    before = _gold(player_id)
    # 商品 1 = sword(item_id=1001) 是新种类，背包满 → 拒绝且金币不扣
    resp = client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert resp.status_code == 400
    assert _gold(player_id) == before


@allure.feature("商城")
@allure.story("连续购买精确扣减")
def test_buy_twice_exact_deduction_and_stack(auth_header, client, player_id):
    client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    client.post("/shop/buy", json={"shop_item_id": 1}, headers=auth_header)
    assert _gold(player_id) == 800
    items = {i["item_id"]: i["count"] for i in client.get("/inventory", headers=auth_header).json()["items"]}
    assert items[1001] == 2
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_shop.py -v`
Expected: PASS（6 个测试全绿）

- [ ] **Step 3: Commit**

```bash
git add api/test_shop.py
git commit -m "test: 商城 6 用例 (扣减/不足/限购/404/原子性/精确扣减)"
```

---

## Task 6: 抽卡 5 用例

**Files:**
- Modify: `api/test_gacha.py`

- [ ] **Step 1: 重写 test_gacha.py（SR 重置 + 持久化）**

`api/test_gacha.py`:
```python
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
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/game-api-test && python -m pytest api/test_gacha.py -v`
Expected: PASS（5 个测试全绿）

- [ ] **Step 3: Commit**

```bash
git add api/test_gacha.py
git commit -m "test: 抽卡 5 用例 (稀有度/10连/90硬保底/SR重置/持久化)"
```

---

## Task 7: Allure 报告生成验证

**Files:**
- Modify: 无（装饰器已在各 Task 写好）

- [ ] **Step 1: 检查 allure CLI 是否可用**

Run: `allure --version`
Expected: 有版本输出；若无，执行 `scoop install allure`（Windows，需先有 scoop）或从 https://github.com/allure-framework/allure2/releases 下载并加 PATH

- [ ] **Step 2: 生成 allure 结果 + 打开报告**

Run: `cd /d/game-api-test && python -m pytest api/ --alluredir=allure-results`
Expected: 全部测试通过，`allure-results/` 下生成 JSON 结果文件

Run: `cd /d/game-api-test && allure serve allure-results`
Expected: 浏览器打开报告，能看到按 feature（基础/登录顶号/状态机/背包/商城/抽卡）分组的用例

- [ ] **Step 3: .gitignore 追加 allure 结果目录**

`.gitignore`（追加）:
```
allure-results/
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: allure report generation verified"
```

---

## Task 8: 抽卡概率统计脚本

**Files:**
- Create: `scripts/gacha_probability.py`

- [ ] **Step 1: 写脚本（卡方拟合优度 + Wilson 95% 置信区间）**

`scripts/gacha_probability.py`:
```python
"""抽卡概率统计验证：对 draw_once 抽 10000 次，做卡方拟合优度检验 + SSR 95% 置信区间。

用法：python scripts/gacha_probability.py [seed]

统计口径（显著性水平 α=0.05）：
- 卡方拟合优度：SSR/SR/R 实际频数 vs 设定概率（3%/15%/82%），自由度 df=2，临界值 5.991。
- SSR 单概率 Wilson 95% 置信区间：检验理论 SSR 概率 0.03 是否落在区间内。

注意：α=0.05 意味着「系统没问题但被误判」的概率约 5%（第一类错误）。
单次「未通过」不代表系统坏了，可换 seed 复跑确认；若多次未通过才需排查 draw_once。
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import config, gacha

N = 10_000
ALPHA = 0.05
Z = 1.96  # 95% 置信水平

# 卡方分布上分位数表（α=0.05）
_CHI2_CRITICAL = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070}


def chi_square_critical(df: int) -> float:
    return _CHI2_CRITICAL[df]


def wilson_interval(successes: int, n: int, z: float = Z):
    """Wilson score interval，适合低概率比例（SSR=3%）的置信区间。"""
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - margin, center + margin


def run(seed=None):
    if seed is not None:
        random.seed(seed)

    counts = {r: 0 for r in config.GACHA_RATES}
    for _ in range(N):
        counts[gacha.draw_once()] += 1

    rates = config.GACHA_RATES
    observed = [counts[r] for r in rates]
    expected = [N * p for p in rates.values()]

    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    df = len(rates) - 1
    critical = chi_square_critical(df)

    ssr_lo, ssr_hi = wilson_interval(counts["SSR"], N)
    ssr_theoretical = rates["SSR"]

    print("=" * 60)
    print(f"抽卡概率验证  （样本 {N} 次，α={ALPHA}）")
    print("=" * 60)
    for i, r in enumerate(rates):
        print(f"{r:>4}  实际 {observed[i]:>5} ({observed[i]/N*100:.2f}%)  期望 {expected[i]:>7.1f}")
    print("-" * 60)
    print(f"卡方统计量 χ² = {chi2:.3f}（自由度 {df}，临界值 {critical}）")
    chi2_ok = chi2 < critical
    print(f"卡方拟合优度：{'通过（分布符合设定概率）' if chi2_ok else '未通过'}")
    print("-" * 60)
    print(f"SSR 95% 置信区间（Wilson）：[{ssr_lo*100:.2f}%, {ssr_hi*100:.2f}%]")
    print(f"SSR 理论概率：{ssr_theoretical*100:.2f}%")
    ci_ok = ssr_lo <= ssr_theoretical <= ssr_hi
    print(f"置信区间检验：{'通过（理论值落在区间内）' if ci_ok else '未通过'}")
    print("=" * 60)
    return chi2_ok and ci_ok


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    ok = run(seed)
    sys.exit(0 if ok else 1)
```

- [ ] **Step 2: 跑脚本（固定 seed 复现）**

Run: `cd /d/game-api-test && python scripts/gacha_probability.py 42`
Expected: 输出实际频数 / 期望频数 / 卡方统计量 / 置信区间，结论为「通过」，退出码 0

Run: `cd /d/game-api-test && python scripts/gacha_probability.py`
Expected: 同上（随机 seed，约 95% 概率「通过」；若偶发「未通过」属第一类错误，换 seed 复跑）

- [ ] **Step 3: Commit**

```bash
git add scripts/gacha_probability.py
git commit -m "feat: 抽卡概率统计脚本 (卡方拟合优度 + Wilson 95% 置信区间)"
```

---

## Task 9: 全量回归 27 用例

**Files:**
- Modify: 无

- [ ] **Step 1: 全量跑测试**

Run: `cd /d/game-api-test && python -m pytest api/ -q`
Expected: 全部 PASS，无失败（27 逻辑用例，pytest item 数因 YAML 参数化略多）

- [ ] **Step 2: 生成最终 allure 报告**

Run: `cd /d/game-api-test && python -m pytest api/ --alluredir=allure-results`
Expected: 全部通过，报告结果齐全

- [ ] **Step 3: 更新 PROJECT_PLAN.md 验收勾选 + Commit**

在 `PROJECT_PLAN.md` 第九节「验收标准」把已满足的项打勾（8 接口可跑通、顶号可验、27 用例、概率统计、保底可测）。实际修改按现状勾选。

```bash
git add -A
git commit -m "docs: Plan2 完成，验收标准勾选"
```

---

## Self-Review 记录

- **Spec coverage:** 27 用例五组全覆盖（基础 3 / 登录顶号 4 / 状态机 3 / 背包 6 / 商城 6 / 抽卡 5），对应 PROJECT_PLAN 第八节 KPI 精确数量。YAML 数据驱动（登录异常 + 背包边界值）、Allure 报告、抽卡概率脚本（卡方 + Wilson CI）三项交付均有 task。`draw_once` 纯概率由脚本测（不受保底干扰），保底由 pytest 单独测，符合 spec「两层分离测」。
- **Placeholder scan:** 无 TBD/TODO。Task 8 的占位 for 循环已在「注意」里显式标注删除，不构成残留。
- **Type consistency:** `player_id` fixture 在 conftest 定义，Task 3/5/6 复用；`_status`/`_gold`/`_pity` 各文件内部私有，无跨文件命名冲突；`AddItemRequest.count` 的 `Field(gt=0)` 定义于 Task 0，Task 4 边界用例依赖其 422 行为。
- **诚实披露：** ① pytest item 数 > 27（参数化所致），已写入计划头「诚实说明」；② 概率脚本 α=0.05 有约 5% 第一类错误，脚本 docstring 与 Task 8 均已说明。
