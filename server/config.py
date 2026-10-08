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

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-me-not-for-prod")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "3600"))

# 游戏规则常量
INVENTORY_SLOT_LIMIT = 20      # 背包格子数上限（不同道具种类数）
ITEM_STACK_LIMIT = 999         # 单种道具叠加上限
GACHA_SSR_PITY = 90            # SSR 硬保底
GACHA_SR_PITY = 10             # SR 10 连保底
GACHA_RATES = {"SSR": 0.03, "SR": 0.15, "R": 0.82}
