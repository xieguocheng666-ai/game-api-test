import random

from . import config
from . import db


def draw_once() -> str:
    """纯概率抽卡，无保底。供概率统计验证使用。"""
    return random.choices(list(config.GACHA_RATES), weights=list(config.GACHA_RATES.values()))[0]


def gacha_pull(player_id: int) -> str:
    """带保底的抽卡：90 抽硬保底 SSR，10 连保底 SR。"""
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
