from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from src.models.user import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    email:      str
    full_name:  str
    role:       UserRole
    is_active:  bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserRead
