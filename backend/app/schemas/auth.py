from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    is_active: bool
    is_super_admin: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MessageResponse(BaseModel):
    message: str
