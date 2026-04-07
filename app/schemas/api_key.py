from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyUpdateRequest(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeyCreatedResponse(BaseModel):
    """Response when creating a new API key - includes the full key (shown only once)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key: str  # Full key, shown only at creation
    key_prefix: str
    is_active: bool
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyResponse]
    total: int
