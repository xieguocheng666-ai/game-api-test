# B 项目加固：抽卡补全 + 购买幂等（含 C 弱网方案联动）

> 2026-10-08 定。触发：写 C 弱网方案时发现 B 项目两处事实——① buy 无幂等（弱网重复扣款）② gacha 不扣货币/不写背包（与文档不符）。
> 已确认两个决定：**抽卡「补全代码（扣货币+写背包）」**；**购买幂等「先测出 bug 再补修复」**。

## 目标

1. gacha 补全「扣货币 + 写背包」（事务），让文档说辞变真实。
2. buy 补幂等（Idempotency-Key），凑齐「发现 → 根因 → 修复 → 复验」故事。
3. 联动更新 C 弱网方案（Task 3 抽卡用例 + Task 5 报告故事）。

## 背景事实（已核实）

- **buy 无幂等**：`server/main.py:78-118` 有事务但无幂等键，弱网重试重复扣款。
- **gacha 无扣款**：`server/gacha.py:12-37` `gacha_pull` 只更新保底，不扣 gold、不写背包；`main.py:141-144` `/gacha` 只返回 rarity。
- **文档不一致**：`PROJECT_PLAN.md:88`（货币边界）、`:91`（扣货币→写背包）。
- **dead field**：`currencies.diamond`（`db.py:35`）全项目未用，本次不动它。
- **竞态（次要）**：buy 扣款 `main.py:101` 无 `WHERE gold>=price`，并发可超扣负数，本次顺手修。

## 设计 1：抽卡补全（B 项目）

**`config.py` 新增**：
- `GACHA_COST = 10`（每抽扣 10 gold，register 已发 1000）
- `GACHA_ITEMS = {"SSR": 2001, "SR": 2002, "R": 2003}`（稀有度 → 背包道具 id）

**`gacha.py`**：
- `draw_once()` 保持纯函数不动（`scripts/gacha_probability.py` 直接依赖）。
- `gacha_pull(player_id)` 改成**单事务**：查/扣 gold → 掷稀有度（draw_once + 保底）→ 更新保底 → 产出道具写背包（`ON DUPLICATE KEY` 叠加封顶 999）。金币不足抛 `InsufficientGold`（自定义异常，gacha.py 内定义，不 import FastAPI）。
- `main.py` `/gacha` 捕获 `InsufficientGold` → 400 `insufficient gold`。

**测试**：现有 5 个抽卡用例不破（GACHA_COST=10，90 抽硬保底花 900 gold，1000 起步够）。新增：货币边界（刚好够 1 抽 / 差 1 不够 / 刚好够 10 连）、金币不足 400 且保底不推进、扣款+背包+保底原子性。

**文档**：`PROJECT_PLAN.md:88/91` 从虚变实，补抽卡成本与产出说明。

## 设计 2：购买幂等（B 项目）

**`db.py` 新增表** `idempotency_keys`（`idempotency_key VARCHAR(64) PK + player_id + 时间戳`，FK players）。

**`api/conftest.py`** `_TABLES` 最前面加 `idempotency_keys`（它是 players 子表，先删）。

**`main.py` `/shop/buy`** 加可选请求头 `Idempotency-Key`，事务第一步 `INSERT idempotency_keys` 作闸门：
- 首次 key → INSERT 成功 → 继续扣款/加背包/记购买 → commit
- 重试同 key → `pymysql.err.IntegrityError`（唯一约束冲突）→ 回滚，返回 `{"ok": true, "duplicate": true}`，不重复扣款

**顺带 1 行修复**：扣款 SQL `gold=gold-%s` → `gold=gold-%s WHERE gold>=%s`（`main.py:101`），关掉并发超扣竞态。

**测试**：新增幂等用例（同 key 重试只扣一次；无 key 行为不变）。

## 设计 3：C 方案联动（D:\game-perf-test）

- `docs/superpowers/plans/2026-10-08-game-perf-test-plan.md` Task 3 Step 4：抽卡用例从「测保底推进」换成「测抽卡重复扣款」（抽卡补全后也扣货币）。
- 新增「幂等复验」用例：带 `Idempotency-Key` 重试只扣一次。
- Task 5 报告故事：弱网下「购买 + 抽卡」都重复扣款 → 根因无幂等 → Idempotency-Key 修复 → 复验。

## 执行顺序

1. B：抽卡补全（config + gacha.py + main.py + test_gacha.py + PROJECT_PLAN.md）
2. C 弱网第一阶段：在「抽卡已补全、幂等未加」代码上复现购买/抽卡重复扣款（bug 演示，需 Fiddler 手动）
3. B：购买幂等（db.py + main.py + conftest.py + test_shop.py）
4. C 弱网第二阶段：带 Idempotency-Key 复验不重复扣（需 Fiddler 手动）
5. C 报告收尾 + 更新 B `PROJECT_PLAN.md` / 记忆 `game_api_test_project.md`

## 关键事实速查

- 跑测试：`cd /d/game-api-test && python -m pytest`
- `_TABLES` 位置：`api/conftest.py:8-15`（外键依赖顺序，子表在前）
- register 发 gold=1000：`main.py:25`
- seed 商品：id=1 sword(price 100, item 1001, 不限购)、id=2 gems(999999)、id=3 ticket(10, limit 1)
- 现有 27 逻辑用例 / pytest 28 条；`draw_once` 必须保持纯函数
- 幂等标准：`Idempotency-Key` 请求头 + 唯一约束 + 事务内去重（IETF 草案，Stripe/Adyen 同款）
