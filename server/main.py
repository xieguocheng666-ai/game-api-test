from fastapi import FastAPI, Depends, HTTPException, Header

from . import db
from . import auth
from .schemas import LoginRequest, LoginResponse, RegisterRequest, CreateCharacterRequest

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
