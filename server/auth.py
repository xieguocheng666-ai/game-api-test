import hashlib
import os
import time

import jwt
import redis

from . import config

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
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + config.JWT_EXPIRE_SECONDS,
        "jti": os.urandom(16).hex(),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> int:
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    return int(payload["sub"])


def save_login(user_id: int, token: str):
    _redis.set(f"login_token:{user_id}", token)


def is_latest_token(user_id: int, token: str) -> bool:
    latest = _redis.get(f"login_token:{user_id}")
    return latest is not None and latest == token


def remove_login(user_id: int):
    _redis.delete(f"login_token:{user_id}")
