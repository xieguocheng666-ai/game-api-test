from fastapi import FastAPI, Depends, HTTPException, Header

from . import db
from . import auth
from . import config
from . import gacha
from .schemas import LoginRequest, LoginResponse, RegisterRequest, CreateCharacterRequest, AddItemRequest, BuyRequest

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
    db.execute("INSERT INTO currencies (player_id, gold) VALUES (%s, 1000)", (player["id"],))
    return {"id": player["id"]}


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    player = db.fetch_one("SELECT id, password_hash FROM players WHERE username=%s", (req.username,))
    if not player or not auth.verify_password(req.password, player["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    char = db.fetch_one("SELECT status FROM characters WHERE player_id=%s", (player["id"],))
    if char and char["status"] == "banned":
        raise HTTPException(status_code=403, detail="account banned")
    db.execute("UPDATE characters SET status='online' WHERE player_id=%s", (player["id"],))
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


@app.post("/inventory/add")
def add_item(req: AddItemRequest, user_id: int = Depends(get_current_user)):
    existing = db.fetch_one("SELECT count FROM inventory WHERE player_id=%s AND item_id=%s", (user_id, req.item_id))
    if existing:
        new_count = min(existing["count"] + req.count, config.ITEM_STACK_LIMIT)
        db.execute("UPDATE inventory SET count=%s WHERE player_id=%s AND item_id=%s", (new_count, user_id, req.item_id))
    else:
        slots = db.fetch_one("SELECT COUNT(*) AS c FROM inventory WHERE player_id=%s", (user_id,))["c"]
        if slots >= config.INVENTORY_SLOT_LIMIT:
            raise HTTPException(status_code=400, detail="inventory full")
        db.execute(
            "INSERT INTO inventory (player_id, item_id, count) VALUES (%s, %s, %s)",
            (user_id, req.item_id, min(req.count, config.ITEM_STACK_LIMIT)),
        )
    return {"item_id": req.item_id}


@app.post("/shop/buy")
def buy(req: BuyRequest, user_id: int = Depends(get_current_user)):
    item = db.fetch_one("SELECT * FROM shop_items WHERE id=%s", (req.shop_item_id,))
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    bought = db.fetch_one(
        "SELECT count FROM purchase_records WHERE player_id=%s AND item_id=%s",
        (user_id, item["item_id"]),
    )
    bought_count = bought["count"] if bought else 0
    if item["buy_limit"] > 0 and bought_count >= item["buy_limit"]:
        raise HTTPException(status_code=400, detail="buy limit reached")
    currency = db.fetch_one("SELECT gold FROM currencies WHERE player_id=%s", (user_id,))
    if currency["gold"] < item["price"]:
        raise HTTPException(status_code=400, detail="insufficient gold")
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


@app.post("/gacha")
def pull(user_id: int = Depends(get_current_user)):
    rarity = gacha.gacha_pull(user_id)
    return {"rarity": rarity}


@app.post("/logout")
def logout(user_id: int = Depends(get_current_user)):
    auth.remove_login(user_id)
    db.execute("UPDATE characters SET status='offline' WHERE player_id=%s", (user_id,))
    return {"ok": True}
