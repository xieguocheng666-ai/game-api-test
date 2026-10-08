import random

from pymysql.err import IntegrityError

from . import config
from . import db


class InsufficientGold(Exception):
    """金币不足，无法抽卡。"""


class DuplicateRequest(Exception):
    """幂等键重复，本次请求此前已处理。"""


def draw_once() -> str:
    """纯概率抽卡，无保底。供概率统计验证使用。"""
    return random.choices(list(config.GACHA_RATES), weights=list(config.GACHA_RATES.values()))[0]


def gacha_pull(player_id: int, idempotency_key: str = None) -> str:
    """带保底的抽卡（单事务）：扣金币 → 掷稀有度 → 更新保底 → 产出道具入背包。

    90 抽硬保底 SSR，10 连保底 SR；金币不足抛 InsufficientGold；幂等键重复抛 DuplicateRequest。
    """
    conn = db.get_conn()
    duplicate = False
    try:
        with conn.cursor() as cur:
            if idempotency_key:
                try:
                    cur.execute(
                        "INSERT INTO idempotency_keys (idempotency_key, player_id) VALUES (%s, %s)",
                        (idempotency_key, player_id),
                    )
                except IntegrityError:
                    duplicate = True
            if not duplicate:
                cur.execute("SELECT gold FROM currencies WHERE player_id=%s FOR UPDATE", (player_id,))
                gold_row = cur.fetchone()
                if not gold_row or gold_row["gold"] < config.GACHA_COST:
                    raise InsufficientGold()

                cur.execute(
                    "UPDATE currencies SET gold=gold-%s WHERE player_id=%s",
                    (config.GACHA_COST, player_id),
                )

                cur.execute("SELECT ssr_pity, sr_pity FROM gacha_pity WHERE player_id=%s FOR UPDATE", (player_id,))
                pity = cur.fetchone()
                if not pity:
                    cur.execute("INSERT INTO gacha_pity (player_id) VALUES (%s)", (player_id,))
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

                cur.execute(
                    "UPDATE gacha_pity SET ssr_pity=%s, sr_pity=%s WHERE player_id=%s",
                    (ssr_pity, sr_pity, player_id),
                )

                item_id = config.GACHA_ITEMS[result]
                cur.execute(
                    "INSERT INTO inventory (player_id, item_id, count) VALUES (%s, %s, 1) "
                    "ON DUPLICATE KEY UPDATE count=LEAST(count+1, %s)",
                    (player_id, item_id, config.ITEM_STACK_LIMIT),
                )
        if duplicate:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if duplicate:
        raise DuplicateRequest()
    return result
