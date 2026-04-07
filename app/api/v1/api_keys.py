from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.services import api_key_service
from app.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyResponse,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
)
from app.schemas.auth import MessageResponse
from app.models.user import User

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new API key.

    ⚠️ The full key is shown only once in this response. Save it securely!
    """
    # Limit API keys per user
    count = api_key_service.count_api_keys_by_user(db, current_user.id)
    if count >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 API keys per user",
        )

    api_key = api_key_service.create_api_key(db, request.name, current_user.id)
    return api_key


@router.get("/", response_model=ApiKeyListResponse)
async def list_api_keys(
    skip: int = 0,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all API keys for the current user."""
    keys = api_key_service.get_api_keys_by_user(db, current_user.id, skip, limit)
    total = api_key_service.count_api_keys_by_user(db, current_user.id)
    return ApiKeyListResponse(api_keys=keys, total=total)


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    request: ApiKeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an API key's name."""
    api_key = api_key_service.get_api_key_by_id(db, key_id, current_user.id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    updated_key = api_key_service.update_api_key(db, api_key, request.name)
    return updated_key


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke (deactivate) an API key."""
    api_key = api_key_service.get_api_key_by_id(db, key_id, current_user.id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key_service.delete_api_key(db, api_key)
    return MessageResponse(message="API key deleted successfully")
