# 游戏接口测试项目 · 踩坑与解决复盘

> 这份文档是「面试弹药」——把项目从 0 到完成（Plan 1 后端 + Plan 2 测试）过程中踩过的每个坑，按「现象 → 排查思路 → 根因 → 解决 → 面试怎么答」整理好。
>
> **怎么用**：面试前扫一遍小标题，被问到「这个项目踩过什么坑 / 遇到什么难题」时，挑 2~3 个和你岗位最相关的讲。每个坑都配了「面试怎么答」，是可以直接说出口的话术，不是网上抄的通用回答。

---

## 目录

- [一、Python 导入机制](#一python-导入机制)
- [二、FastAPI 参数与校验](#二fastapi-参数与校验)
- [三、顶号 + JWT 鉴权](#三顶号--jwt-鉴权)
- [四、业务逻辑 bug（最有含金量）](#四业务逻辑-bug最有含金量)
- [五、测试设计](#五测试设计)
- [六、概率统计验证](#六概率统计验证)
- [七、工程环境](#七工程环境)

---

## 一、Python 导入机制

### 坑 1：包内相对导入 vs 绝对导入

**现象**：`server/config.py` 写好后，`server/db.py` 里写 `import config`，运行报 `ModuleNotFoundError: No module named 'config'`。

**排查思路**：`config.py` 明明和 `db.py` 在同一个 `server/` 目录下，为什么找不到？定位到 `server/` 是一个「包」（有 `__init__.py`），包内模块互相引用不能用顶层导入。

**根因**：`import config` 是去 `sys.path`（模块搜索路径）里找一个**顶层**叫 `config` 的模块；而这里的 `config.py` 是 `server` 包**内部**的模块，两者不是一个东西。

**解决**：`server/` 包内一律用相对导入 `from . import config`（`.` 表示「当前包」）。

**面试怎么答**：
> 项目里 `server/` 是一个 Python 包，内部模块互相引用要用相对导入（`from . import config`）。一开始我写了绝对导入 `import config`，报 ModuleNotFoundError。原因是绝对导入去 sys.path 顶层找，而 config 是包内模块。改成相对导入后，还避免了将来和一个叫 `config` 的第三方库或顶层同名模块冲突。

---

### 坑 2：脚本直接运行找不到项目包

**现象**：写抽卡概率统计脚本 `scripts/gacha_probability.py`，里面 `from server import config, gacha`，运行 `python scripts/gacha_probability.py` 报 `ModuleNotFoundError: No module named 'server'`。

**排查思路**：`server` 明明在项目根目录，为什么脚本里 import 不到？

**根因**：直接运行一个脚本文件时，Python 把**脚本所在的目录**（`scripts/`）加到 `sys.path[0]`，而不是当前工作目录（项目根）。所以 `server` 包不在搜索路径里。

**解决**：脚本开头加一行，把项目根目录塞进搜索路径：
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

**面试怎么答**：
> 这个脚本不在包内，而是独立脚本。直接 `python scripts/xxx.py` 时，Python 只把脚本所在目录加进 sys.path，找不到项目根下的 `server` 包。我用 `Path(__file__).resolve().parent.parent` 定位到项目根再 `sys.path.insert`，脚本就能独立跑，不依赖从哪个目录启动。

---

## 二、FastAPI 参数与校验

### 坑 3：POST body 的裸标量被当成 query 参数

**现象**：接口 `def add_item(item_id: int, count: int)`，前端用 JSON body 传 `{"item_id": 1, "count": 5}`，结果参数收不到 / 被当成了 URL 上的 query 参数。

**根因**：FastAPI 的参数来源规则——**简单类型**（`int`、`str`、`bool` 等）默认从 query string 读；**复合类型**（Pydantic 模型）才从 request body 读。裸标量写参数，FastAPI 会去 query 里找。

**解决**：POST 带 body 的接口统一用 Pydantic 模型接收，例如：
```python
class AddItemRequest(BaseModel):
    item_id: int
    count: int

@app.post("/inventory/add")
def add_item(req: AddItemRequest, ...): ...
```

**面试怎么答**：
> FastAPI 里简单类型参数默认来自 query，只有 Pydantic 模型才从 body 解析。一开始我图省事直接写裸标量参数，结果 body 里的字段收不到。改成 Pydantic 模型后，不仅参数来源对了，还顺便拿到了自动校验和类型检查。

---

### 坑 4：参数校验（422）和业务错误（400）要分开

**现象**：背包加道具要测边界值，其中 `count=0` 该怎么处理、返回什么状态码？

**根因/解决**：这里有一个测试岗必懂的区分——
- **参数校验**（格式不对、范围不对）→ 交给 Pydantic，用 `Field(gt=0)`，违规自动返回 **422**（FastAPI 的标准校验错误码）；
- **业务规则**（比如「金币不足」「背包满格」）→ 在接口逻辑里 `raise HTTPException(status_code=400, ...)`，返回 **400**。

```python
class AddItemRequest(BaseModel):
    item_id: int
    count: int = Field(gt=0)   # count <= 0 自动 422，不用手写判断
```

**面试怎么答**：
> 我特意把「参数校验」和「业务错误」分开处理。参数本身不合法（比如 count=0）用 Pydantic 的 Field 约束，FastAPI 自动返回 422；业务规则（比如金币不够）在接口里显式 raise 400。这样状态码语义清晰，422 代表「请求就没构造对」，400 代表「请求合法但业务不通过」。这也是接口测试里判断边界用例预期结果的一个依据。

---

## 三、顶号 + JWT 鉴权

### 坑 5：同一秒生成的 JWT 完全相同，顶号失效

**现象**：测试「顶号登录」（同一账号在设备 B 登录后，设备 A 的旧 token 应立即失效）时，发现同一秒内连续两次登录，签出来的 token 一模一样，旧 token 没被踢掉。

**排查思路**：顶号的核心是「Redis 里存当前最新 token，请求来时比对」。如果新旧 token 相同，比对永远相等，顶号就失效了。为什么 token 会相同？

**根因**：JWT 是「确定性编码」——payload 一样，签名结果就一样。原来的 payload 只有 `sub`（用户 id）和 `exp`（过期时间）。同一秒内两次登录，`sub` 相同、`exp` 相同（时间戳粒度到秒），于是两个 token 完全一样。

**解决**：payload 里加一个 `jti`（JWT ID，一段随机串），保证每次签发的 token 全局唯一：
```python
payload = {
    "sub": str(user_id),
    "exp": int(time.time()) + config.JWT_EXPIRE_SECONDS,
    "jti": os.urandom(16).hex(),   # 随机，保证唯一
}
```

**面试怎么答**：
> 顶号实现里，我把「当前最新 token」存在 Redis，鉴权时拿请求带的 token 和 Redis 里的比对，不一致就判为被顶号。开发时踩了个坑：同一秒内两次登录，JWT 的 payload 只有 sub 和 exp，时间戳到秒，两个 token 完全一样，顶号就失效了。解决是给 payload 加 jti（一段随机串），保证每次 token 唯一。这也体现了 JWT 的一个特性——它本身不含服务端状态，唯一性和「当前是否有效」要靠额外手段保证。

---

### 坑 6：JWT 密钥太短触发安全警告

**现象**：启动时 PyJWT 打印 `InsecureKeyLengthWarning`（密钥长度不安全警告）。

**根因**：JWT 用 HS256 算法（HMAC-SHA256）签名，HS256 要求密钥至少 **256 位 = 32 字节**。原来的密钥只有 20 个字符，不满足长度要求。

**解决**：把密钥换成 36 字符的随机串（并写进 `.env`，不硬编码进代码）。

**面试怎么答**：
> HS256 签名算法对密钥长度有要求，至少 32 字节，否则会被 PyJWT 判为弱密钥。我把密钥加长到 36 字符，并且放进 .env 环境变量、不提交进代码仓库。这涉及一个安全意识：JWT 的密钥就是「验签的钥匙」，泄露了别人就能伪造 token。

---

### 坑 7：角色状态和顶号 token 为什么要分两个存储（设计决策）

**现象/问题**：角色状态（online/offline/banned）和顶号 token，都跟「登录会话」相关，是存一起还是分开？

**排查思路**：想清楚两者的**生命周期**不同——
- **角色状态**是玩家资产的一部分，封禁（banned）是**持久**的，掉线重登、服务器重启都不能丢；
- **顶号 token**是**会话**，本来就是临时的，丢了让用户重登即可，且 Redis 的 TTL 天然适合。

**解决**：角色状态存 MySQL（持久），顶号 token 存 Redis（会话，带过期时间）。

**面试怎么答**：
> 我把「角色状态机」和「顶号」分开设计：角色状态（尤其是封禁）是持久数据，必须存数据库，不能因为会话过期就丢失；顶号 token 是会话数据，存 Redis、带 TTL 自动过期。这样封禁是「粘性」的——就算 Redis 里的 token 没了，数据库里 banned 状态还在，重登还是被拒。这也是游戏测试里一个常考点：封禁为什么不能因为「重新登录」就被解除。

---

## 四、业务逻辑 bug（最有含金量）

> 这三个 bug 是 final review 阶段挖出来的，最能体现「测试思维」——尤其是前两个，都是「看着功能正常、但边界/异常分支有洞」。

### 坑 8：buy 接口绕过背包格子限制

**现象**：背包满 20 格后，通过商城买一个**新种类**的道具，居然还能买进去，背包变成了 21 格，突破了格子上限。

**排查思路**：对比了两条「往背包加道具」的路径——`/inventory/add`（测试用加道具）有满格检查，但 `/shop/buy` 是**另一条独立代码路径**，它只检查了货币和限购，**漏了满格检查**。

**根因**：加道具这个逻辑在两条路径里各自实现了一遍，buy 路径漏了「背包满格」这个前置校验。

**解决**：在 buy 的事务开始前，补上满格检查（只对「新种类道具」需要检查，已有道具是叠加不占新格子）。

**面试怎么答**：
> 这是我最有收获的一个 bug。背包满格是 20 格上限，`/inventory/add` 有检查，但 `/shop/buy` 是另一条代码路径，漏了这个前置校验，导致满格后还能通过购买突破上限。它让我意识到：功能相似的两条路径要专门做「一致性检查」，测试不能只测主流程，要测「满格后购买」这种交叉场景。后面我专门补了一个用例：塞满 20 格后再买新道具，断言返回 400 且金币不被扣。

---

### 坑 9：被封禁角色 logout 后被「自我解封」（banned 不粘滞）

**现象**：角色被封禁（banned）后，一旦触发 logout，状态被改回 offline，等于**解封了**。

**排查思路**：查 logout 的 SQL，发现是**无条件**改状态：
```sql
-- 修复前（错误）：无条件把状态改成 offline
UPDATE characters SET status='offline' WHERE player_id=%s;
```

**根因**：logout 没区分「正常在线下线」和「被封禁」。banned 是一个「粘性状态」，普通下线操作不该覆盖它。

**解决**：加条件，只在 `online` 时才改成 offline：
```sql
-- 修复后：只把 online 改成 offline，banned 保持不变
UPDATE characters SET status='offline' WHERE player_id=%s AND status='online';
```

**面试怎么答**：
> 状态机设计里，banned（封禁）必须是一个「粘性」状态——一旦封禁，普通的登出、下线都不能把它洗掉。一开始 logout 的 SQL 是无条件 `SET status='offline'`，导致被封角色一下线就被解封。我改成 `WHERE status='online'`，只有正常在线才转 offline。这个 bug 对应的测试点就是「封禁状态粘滞」：封禁后即使尝试重新登录，状态也必须还是 banned。

---

### 坑 10：`buy_limit=0` 哨兵值判断边界

**现象**：商城有「限购」字段 `buy_limit`，约定 `0` 表示**不限购**。但判断写成了 `if bought >= buy_limit`，导致不限购的商品第一次购买就被判为「达到限购次数」拒绝。

**根因**：`0` 在这里是一个**哨兵值**（特殊含义：不限购），但判断条件没有显式处理这个特殊值，把 `0` 当成了「上限 0 次」。

**解决**：显式区分：
```python
if item["buy_limit"] > 0 and bought_count >= item["buy_limit"]:
    raise HTTPException(status_code=400, detail="buy limit reached")
```

**面试怎么答**：
> 限购字段我用了 `0` 表示「不限购」这个哨兵值。一开始判断写成 `bought >= buy_limit`，结果不限购的商品（buy_limit=0）第一次买就被误判为达到上限。改成 `buy_limit > 0 and bought >= buy_limit`，显式排除哨兵值。这提醒我：用特殊值表达「无限/默认」时，判断条件一定要显式处理，否则边界用例必挂。

---

## 五、测试设计

### 坑 11：`pytest` 和 `python -m pytest` 的导入差异

**现象**：直接敲 `pytest` 时，`server` 包导入失败；敲 `python -m pytest` 就正常。

**根因**：`python -m pytest` 会把**当前工作目录**加进 `sys.path`，所以 `server` 包能被导入；而 `pytest` 命令（直接执行脚本）的路径行为不同，可能找不到包。

**解决**：项目统一用 `python -m pytest` 跑测试。

**面试怎么答**：
> 一个小坑：直接 `pytest` 可能因为项目包不在 sys.path 里而导入失败，用 `python -m pytest` 会把当前目录加进搜索路径，保证 `server` 包可导入。团队里统一约定好运行方式，能避免「在我机器上能跑、你机器上不能跑」的扯皮。

---

### 坑 12：conftest 清表要按外键依赖顺序

**现象**：测试重复跑，因为上一轮的数据残留导致断言失败；或者清表时报外键约束错误。

**根因**：项目有 7 张表，其中多张有外键关系（子表引用父表）。清表时如果先删父表，会违反外键约束（子表还引用着它）。

**解决**：conftest 的 `client` fixture 里，按**外键依赖顺序**（先子表后父表）清 6 张数据表 + Redis flushdb。注意 `shop_items`（商品配置）是种子数据，**不清理**，因为它是配置不是测试产生的脏数据。

```python
_TABLES = (
    "purchase_records", "gacha_pity", "inventory",
    "currencies", "characters", "players",   # 先子表后父表
)
```

**面试怎么答**：
> 接口测试要保证用例可重复执行（幂等），我在 conftest 的 fixture 里做数据清理。有个细节：清表要按外键依赖顺序，先删子表再删父表，否则报外键约束错误；而 shop_items 这种配置数据不清，只清测试产生的脏数据。测试数据隔离是接口自动化能否稳定跑的前提。

---

### 坑 13：用 monkeypatch 把「概率」变成「确定」来测保底

**现象**：抽卡保底逻辑（90 抽硬保底 SSR、出 SR 重置计数）是概率相关的，怎么稳定地测、不 flaky（偶发失败）？

**排查思路**：保底逻辑依赖底层 `draw_once()` 的随机结果。如果直接用真实随机，测「第 90 抽必出 SSR」会极不稳定。

**根因/解决**：测试里用 `monkeypatch` 把 `draw_once` 替换成**固定返回值**（比如永远返回 "R"），把随机源「桩」掉，让保底逻辑变成确定性的，再断言。

```python
def test_gacha_90_pull_hard_pity_forces_ssr(auth_header, client, monkeypatch):
    monkeypatch.setattr(gacha, "draw_once", lambda: "R")   # 强制永远抽 R
    rarities = [client.post("/gacha", ...).json()["rarity"] for _ in range(90)]
    assert rarities[-1] == "SSR"   # 前 89 抽都 R，第 90 抽被硬保底强制 SSR
```

**面试怎么答**：
> 测抽卡保底时，我不能用真实随机，否则断言不稳定。做法是用 monkeypatch 把底层 `draw_once` 桩成固定返回「R」，这样「前 89 抽都是 R，第 90 抽强制 SSR」就变成确定性场景，可以精确断言。这体现了测试里「隔离随机源」的思路：把不确定的部分桩掉，才能稳定验证确定的那部分逻辑。

---

### 坑 14：数据驱动让「用例数」和「pytest 条数」不一致（27 vs 28）

**现象**：项目号称 27 个用例，但 pytest 实际跑出 28 条。

**根因**：背包边界值用例用了 YAML 数据驱动 + `pytest.mark.parametrize`，一个测试函数会按 YAML 里的每一行展开成多条。YAML 里边界值写了 3 行（count=0/1/999），而「逻辑用例」只对应其中 2 个场景编号，多出来 1 行，所以 pytest 条数比逻辑用例数多 1。

**解决**：**诚实**说明口径——27 是「逻辑用例」数（按游戏场景划分），参数化展开后 pytest 条数略多，这是数据驱动技术的正常表现，不是注水。

**面试怎么答**：
> 我用 YAML + pytest 的 parametrize 做数据驱动，把「登录异常」「背包边界值」这类「同一逻辑、不同数据」的用例抽出来，用表格驱动，避免写一堆几乎一样的测试函数。这里有个口径要讲清楚：我对外说 27 个用例是「逻辑用例」数，参数化展开后 pytest 实际条数会多一点，这是数据驱动的正常现象。面试讲量化结果时，口径诚实很重要——宁可说清楚，不夸大。

---

## 六、概率统计验证

### 坑 15：抽卡概率怎么「科学地」验证（卡方 + 置信区间）

**问题**：抽卡 SSR 概率设定是 3%，怎么验证「实现出来的概率」真的符合 3%，而不是凭感觉？

**设计**：把抽卡拆成两层，概率层单独验证——
- **底层 `draw_once()`**：纯概率（SSR 3% / SR 15% / R 82%），**无保底**，专门用来做统计验证（不受保底干扰）；
- **上层 `gacha_pull()`**：带保底（90 抽硬保底 SSR + 10 连保底 SR），单独测保底逻辑。

对 `draw_once()` 抽 **10000 次**，做两件事（显著性水平 α=0.05）：
1. **卡方拟合优度检验**：实际 SSR/SR/R 频数 vs 理论概率，算卡方统计量，和临界值比（自由度 df=2，临界值 5.991）；
2. **SSR 单概率 95% 置信区间**（Wilson 区间）：看理论概率 3% 是否落在实测频率的置信区间内。

**为什么抽 10000 次**：SSR 概率很低（3%），样本太少置信区间会宽到无法判定；10000 次期望 SSR≈300 次，卡方检验才有足够检验力。

**关于 α=0.05 的诚实点**：显著性水平 0.05 意味着「系统没问题、但被误判为有问题」的概率约 5%（第一类错误）。所以单次「未通过」不代表系统有 bug，可换随机种子复跑确认；多次未通过才要查实现。

实测结果（seed=42）：SSR 275 次（2.75%），卡方 χ²=4.291 < 5.991，SSR 95% CI = [2.45%, 3.09%] 包含 3.00%，两项检验都通过。

**面试怎么答**：
> 这是对打笔试里「伤害浮动到底是 bug 还是随机数」这类题。我的做法是：概率层和保底层分开测。底层纯概率函数抽 10000 次，用卡方拟合优度检验整体分布是否符合设定概率，再用 Wilson 95% 置信区间单独验证 SSR 的 3% 概率是否落在实测区间内。样本量选 10000 是因为 SSR 概率低、小样本置信区间太宽没法判定。另外我会诚实说明：α=0.05 有约 5% 的误判率，单次不过不代表有 bug，要复跑确认。

---

### 坑 16：Windows 中文控制台编码崩溃（GBK vs UTF-8）

**现象**：概率脚本里 print 了一个 `χ²`（希腊字母 chi + 上标 2），在 Windows 上直接运行抛 `UnicodeEncodeError`，脚本退出码 1。

**排查思路**：脚本逻辑没问题，是打印那行崩的，定位到 `χ²` 这个字符。

**根因**：Windows 中文系统默认控制台编码是 **GBK（cp936）**，GBK 不含希腊字母 `χ`；Python 的 stdout 默认跟随系统编码，编码这个字符就抛异常。

**解决**：两招——
1. 脚本 `__main__` 里强制 stdout 用 UTF-8：`sys.stdout.reconfigure(encoding="utf-8")`；
2. 数学符号用 ASCII 写（`χ²` → `chi2`），双保险。

```python
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # 兼容 Windows GBK 控制台
```

**面试怎么答**：
> 写跨平台脚本时踩了个编码坑：Windows 中文系统默认是 GBK 编码，脚本里 print 希腊字母 χ² 直接抛 UnicodeEncodeError。我用 `sys.stdout.reconfigure(encoding="utf-8")` 强制 UTF-8 输出，再顺手把符号 ASCII 化（chi2），保证脚本在任何控制台都不崩。这个坑很小，但体现跨平台健壮性意识——Windows 中文环境里 GBK/UTF-8 的编码问题是高频地雷。

---

## 七、工程环境

### 坑 17：git 首次提交缺少身份配置

**现象**：第一次 `git commit` 报错，提示缺少 `user.name` / `user.email`。

**解决**：配置本地 git 身份（`git config user.name / user.email`），只对本仓库生效，不动全局配置。

**面试怎么答**：
> 环境层面的小坑，不算技术难点，但说明新仓库初始化要先把 git 身份配好，否则第一个 commit 就会卡住。

---

### 坑 18：allure-pytest 装完还不够，报告渲染要单独的 CLI

**现象**：`pip install allure-pytest` 装好了，但 `allure serve` 命令找不到。

**根因**：这是两个东西——
- **allure-pytest**：pytest 插件，负责把测试结果**生成**成 JSON 结果文件（`--alluredir`）；
- **allure CLI**：独立的命令行工具，负责把 JSON 结果**渲染**成网页报告（`allure serve` / `allure generate`）。

只装 pip 包只能生成结果文件，渲染报告还需要单独装 allure 命令行工具。

**解决**：`pip install allure-pytest` + 单独装 allure CLI（Windows 可用 scoop 或下载官方 release 加 PATH）。

**面试怎么答**：
> Allure 报告有两层：allure-pytest 负责生成结果，allure CLI 负责渲染成网页。很多人只装了 pip 包就跑 `allure serve`，会找不到命令。这个区分清楚了，报告就顺了。接口自动化里报告是「测试结果可视化」的一环，Allure 的 feature/story 分组能按功能模块组织用例，比裸的 pytest 输出清晰很多。

---

## 附：项目整体信息（面试可报）

- **技术栈**：FastAPI + uvicorn（被测系统）、PyMySQL（MySQL 8.0 原生 SQL）、PyJWT + Redis（顶号）、pytest + TestClient（接口测试）、PyYAML（数据驱动）、Allure（报告）。
- **规模**：8 个核心接口 + 7 张表；27 个逻辑用例（pytest 28 条，含参数化展开），全部通过；抽卡概率统计脚本 10000 样本。
- **提交**：22 个 commit，全程 TDD + 分阶段提交。
- **项目亮点**（面试主打的游戏场景）：顶号登录、角色状态机（含封禁粘滞）、背包满格与叠加上限、商城限购与购买原子性、抽卡概率验证（卡方 + 置信区间）与保底机制。
