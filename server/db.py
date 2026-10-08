import pymysql
from pymysql.cursors import DictCursor

from . import config

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
    seed_shop()


def seed_shop():
    execute(
        "INSERT IGNORE INTO shop_items (id, name, price, item_id, item_count, buy_limit) VALUES "
        "(1,'sword',100,1001,1,0),(2,'gems',999999,1002,1,0),(3,'ticket',10,1003,1,1)",
        (),
    )


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
