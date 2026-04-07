from pydantic import BaseModel, ConfigDict
from datetime import datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    full_name: str | None = None
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
