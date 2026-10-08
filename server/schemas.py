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
